use std::{num::NonZeroUsize, sync::Arc, time::Duration};

use neuromita::{
    api::ChatApi,
    app::{ApplicationConfig, ApplicationLifecycle, RuntimeLimits},
    character::CharacterId,
    generation::{
        GenerationPreset, GenerationProvider, ProviderTemplate, ResponseGenerator,
        gemini::{GeminiProvider, GeminiTemplate, GenerationSettings},
    },
    presentation::ChatPresenter,
    request::{
        CancelResult, ReplyRequest, RequestHandle, RequestId, RequestOutcome, RequestSource,
        RequestState, SubmitError, UserInput,
    },
    timeline::EventContent,
};
use serde_json::{Value, json};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    sync::{mpsc, oneshot},
    task::{JoinHandle, JoinSet},
    time::timeout,
};
use tokio_util::sync::CancellationToken;
use uuid::Uuid;

#[derive(Debug)]
struct Call {
    path: String,
    body: Value,
    respond: oneshot::Sender<Reply>,
}

#[derive(Debug)]
enum Reply {
    Text(&'static str),
    Status(u16),
}

struct GeminiServer {
    endpoint: String,
    calls: mpsc::UnboundedReceiver<Call>,
    stop: CancellationToken,
    task: JoinHandle<()>,
}

impl GeminiServer {
    async fn start() -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let endpoint = format!("http://{}/v1beta/", listener.local_addr().unwrap());
        let (send, calls) = mpsc::unbounded_channel();
        let stop = CancellationToken::new();
        let server_stop = stop.clone();
        let task = tokio::spawn(async move {
            let mut clients = JoinSet::new();
            loop {
                tokio::select! {
                    _ = server_stop.cancelled() => break,
                    connection = listener.accept() => {
                        let (stream, _) = connection.unwrap();
                        clients.spawn(serve(stream, send.clone()));
                    }
                    result = clients.join_next(), if !clients.is_empty() => {
                        result.unwrap().unwrap();
                    }
                }
            }
            clients.abort_all();
            while clients.join_next().await.is_some() {}
        });
        Self {
            endpoint,
            calls,
            stop,
            task,
        }
    }

    async fn next(&mut self) -> Call {
        timeout(Duration::from_secs(10), self.calls.recv())
            .await
            .unwrap()
            .unwrap()
    }
    async fn shutdown(self) {
        self.stop.cancel();
        self.task.await.unwrap();
    }
}

async fn serve(mut stream: TcpStream, calls: mpsc::UnboundedSender<Call>) {
    let mut bytes = Vec::new();
    let boundary;
    loop {
        let mut chunk = [0; 4096];
        let count = stream.read(&mut chunk).await.unwrap();
        if count == 0 {
            return;
        }
        bytes.extend_from_slice(&chunk[..count]);
        if let Some(index) = bytes.windows(4).position(|part| part == b"\r\n\r\n") {
            boundary = index + 4;
            break;
        }
        assert!(bytes.len() < 64 * 1024);
    }
    let header = std::str::from_utf8(&bytes[..boundary]).unwrap();
    let path = header.lines().next().unwrap().to_owned();
    let size: usize = header
        .lines()
        .find_map(|line| {
            let (name, value) = line.split_once(':')?;
            name.eq_ignore_ascii_case("content-length")
                .then(|| value.trim().parse().unwrap())
        })
        .unwrap();
    assert!(!header.to_ascii_lowercase().contains("x-goog-api-key:"));
    assert!(!header.to_ascii_lowercase().contains("authorization:"));
    assert!(path.contains(":generateContent?key=test-key "));
    while bytes.len() < boundary + size {
        let mut chunk = [0; 4096];
        let count = stream.read(&mut chunk).await.unwrap();
        if count == 0 {
            return;
        }
        bytes.extend_from_slice(&chunk[..count]);
    }
    let body = serde_json::from_slice(&bytes[boundary..boundary + size]).unwrap();
    let (respond, response) = oneshot::channel();
    calls
        .send(Call {
            path,
            body,
            respond,
        })
        .unwrap();
    let Ok(response) = response.await else {
        return;
    };
    let (status, body) = match response {
        Reply::Text(text) => (200, json!({"candidates":[{"content":{"role":"model","parts":[{"text":"private reasoning","thought":true},{"text":text}]},"finishReason":"STOP"}]}).to_string()),
        Reply::Status(status) => (status, "{}".to_owned()),
    };
    let response = format!(
        "HTTP/1.1 {status} Result\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes()).await;
}

fn preset(endpoint: &str) -> GenerationPreset {
    let settings = GenerationSettings::new(0.7, 512, Duration::from_secs(10)).unwrap();
    GenerationPreset::new(ProviderTemplate::Gemini(
        GeminiTemplate::new(endpoint, "test-model", "test-key", settings).unwrap(),
    ))
}

fn limits() -> RuntimeLimits {
    RuntimeLimits {
        request_queue: NonZeroUsize::new(2).unwrap(),
        discovery_buffer: NonZeroUsize::new(32).unwrap(),
        character_commands: NonZeroUsize::new(16).unwrap(),
        presenter_updates: NonZeroUsize::new(32).unwrap(),
        retained_finished: NonZeroUsize::new(20).unwrap(),
    }
}

struct CheckedProvider(GeminiProvider);

impl GenerationProvider for CheckedProvider {
    fn kind(&self) -> neuromita::generation::ProviderKind {
        neuromita::generation::ProviderKind::Gemini
    }

    fn generate(
        &self,
        context: neuromita::character::CharacterContext,
        template: ProviderTemplate,
    ) -> neuromita::generation::ProviderFuture<'_> {
        Box::pin(async move {
            assert_ne!(
                &*context.current_input, "panic provider",
                "injected provider panic"
            );
            self.0.generate(context, template).await
        })
    }
}

async fn finished(handle: &RequestHandle) -> Arc<neuromita::request::RequestSnapshot> {
    timeout(Duration::from_secs(10), handle.wait())
        .await
        .unwrap()
        .unwrap()
}

async fn shown(presenter: &ChatPresenter, id: RequestId, terminal: bool) {
    timeout(Duration::from_secs(10), async {
        let mut model = presenter.observe();
        loop {
            let present = {
                model.borrow_and_update().requests.iter().any(|row| {
                    row.metadata.id == id && (!terminal || row.snapshot.state.is_terminal())
                })
            };
            if present {
                return;
            }
            model.changed().await.unwrap();
        }
    })
    .await
    .unwrap();
}

fn user_texts(body: &Value) -> Vec<&str> {
    body["contents"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|item| item["role"] == "user")
        .map(|item| item["parts"][0]["text"].as_str().unwrap())
        .collect()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn presenter_to_provider_observation_cancellation_and_commit() {
    assert!(matches!(
        ChatApi::observe_requests(),
        Err(SubmitError::Uninitialized)
    ));
    let mut server = GeminiServer::start().await;
    let preset = preset(&server.endpoint);
    let provider: Arc<dyn GenerationProvider> =
        Arc::new(CheckedProvider(GeminiProvider::new().unwrap()));
    let config = ApplicationConfig::minimal(
        preset.clone(),
        ResponseGenerator::new([provider]).unwrap(),
        limits(),
        "127.0.0.1:0".parse().unwrap(),
    );
    let app = ApplicationLifecycle::start(config).await.unwrap();
    let presenter = &app.presenter().chat;
    assert!(presenter.reply(CharacterId::Mita, " ".into()).is_err());

    let first = presenter.reply(CharacterId::Mita, "first".into()).unwrap();
    let first_call = server.next().await;
    assert_eq!(
        first_call.path,
        "POST /v1beta/models/test-model:generateContent?key=test-key HTTP/1.1"
    );
    assert_eq!(user_texts(&first_call.body), ["first"]);
    assert_eq!(first_call.body["generationConfig"]["candidateCount"], 1);
    assert!(
        first_call.body["systemInstruction"]["parts"][0]["text"]
            .as_str()
            .unwrap()
            .contains("Мита")
    );

    let queued = presenter
        .reply(CharacterId::Mita, "never starts".into())
        .unwrap();
    let running_cancel = presenter
        .reply(CharacterId::Mita, "cancel during generation".into())
        .unwrap();
    assert!(matches!(
        presenter.reply(CharacterId::Mita, "queue overflow".into()),
        Err(neuromita::presentation::PresenterError::Submit(
            SubmitError::QueueFull
        ))
    ));
    assert_eq!(queued.cancel(), CancelResult::Cancelled);
    assert!(matches!(
        finished(&queued).await.state,
        RequestState::Cancelled
    ));
    assert_eq!(
        app.character(CharacterId::Mita)
            .unwrap()
            .state()
            .await
            .unwrap()
            .accepted_replies,
        0
    );

    let external = ChatApi::reply(ReplyRequest::new(
        CharacterId::KindMita,
        preset.clone(),
        UserInput::new("external client".into()).unwrap(),
        RequestSource::Client(Uuid::new_v4()),
    ))
    .unwrap();
    let external_call = server.next().await;
    assert_eq!(user_texts(&external_call.body), ["external client"]);
    shown(presenter, external.id(), false).await;
    external_call
        .respond
        .send(Reply::Text("kind reply"))
        .unwrap();
    assert!(matches!(
        finished(&external).await.state,
        RequestState::Finished(RequestOutcome::Success(_))
    ));
    shown(presenter, external.id(), true).await;
    assert!(matches!(
        first.snapshot().state,
        RequestState::Processing(_)
    ));

    first_call.respond.send(Reply::Text("first reply")).unwrap();
    let first_result = finished(&first).await;
    match &first_result.state {
        RequestState::Finished(RequestOutcome::Success(response)) => {
            assert_eq!(&*response.text, "first reply")
        }
        state => panic!("unexpected state: {state:?}"),
    }
    assert!(matches!(first.cancel(), CancelResult::AlreadyFinished));
    let mut late_observer = first.observe();
    assert!(
        late_observer
            .next()
            .await
            .unwrap()
            .unwrap()
            .state
            .is_terminal()
    );
    assert!(late_observer.next().await.unwrap().is_none());

    let cancelled_call = server.next().await;
    assert_eq!(
        user_texts(&cancelled_call.body),
        ["first", "cancel during generation"]
    );
    assert_eq!(cancelled_call.body["contents"][1]["role"], "model");
    assert_eq!(
        cancelled_call.body["contents"][1]["parts"][0]["text"],
        "first reply"
    );
    assert_eq!(running_cancel.cancel(), CancelResult::Requested);
    assert!(matches!(
        finished(&running_cancel).await.state,
        RequestState::Cancelled
    ));
    let _ = cancelled_call
        .respond
        .send(Reply::Text("must not be accepted"));
    assert_eq!(
        app.character(CharacterId::Mita)
            .unwrap()
            .state()
            .await
            .unwrap()
            .accepted_replies,
        1
    );

    let failed = presenter
        .reply(CharacterId::Mita, "HTTP failure".into())
        .unwrap();
    server
        .next()
        .await
        .respond
        .send(Reply::Status(503))
        .unwrap();
    assert!(matches!(
        finished(&failed).await.state,
        RequestState::Finished(RequestOutcome::TextGenerationFailed(_))
    ));

    let panicked = presenter
        .reply(CharacterId::Mita, "panic provider".into())
        .unwrap();
    assert!(matches!(
        finished(&panicked).await.state,
        RequestState::Finished(RequestOutcome::InternalError(_))
    ));

    let next = presenter
        .reply(CharacterId::Mita, "after failure".into())
        .unwrap();
    let next_call = server.next().await;
    assert!(!next_call.body.to_string().contains("must not be accepted"));
    assert!(!next_call.body.to_string().contains("never starts"));
    next_call.respond.send(Reply::Text("second reply")).unwrap();
    assert!(matches!(
        finished(&next).await.state,
        RequestState::Finished(RequestOutcome::Success(_))
    ));
    shown(presenter, next.id(), true).await;
    assert_eq!(
        app.character(CharacterId::Mita)
            .unwrap()
            .state()
            .await
            .unwrap()
            .accepted_replies,
        2
    );
    let events = app.timeline();
    let replies: Vec<_> = events
        .iter()
        .filter(|event| matches!(event.content, EventContent::CharacterReply { .. }))
        .collect();
    assert_eq!(replies.len(), 3);
    assert!(
        replies
            .iter()
            .any(|event| event.request_id == Some(first.id()))
    );
    assert!(
        !events
            .iter()
            .any(|event| event.request_id == Some(queued.id()))
    );

    let interrupted = presenter
        .reply(CharacterId::Mita, "stop application".into())
        .unwrap();
    let stopped_call = server.next().await;
    let pending = presenter
        .reply(CharacterId::Mita, "stop pending".into())
        .unwrap();
    app.shutdown().await.unwrap();
    assert!(matches!(
        finished(&interrupted).await.state,
        RequestState::Cancelled
    ));
    assert!(matches!(
        finished(&pending).await.state,
        RequestState::Cancelled
    ));
    drop(stopped_call);
    assert!(matches!(
        ChatApi::observe_requests(),
        Err(SubmitError::Stopped)
    ));
    server.shutdown().await;
}
