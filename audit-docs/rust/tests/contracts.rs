use std::{
    num::NonZeroUsize,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};

use neuromita::{
    api::{CharacterApi, ChatApi},
    app::{ApplicationConfig, ApplicationLifecycle, RuntimeLimits},
    character::{CharacterContext, CharacterId},
    generation::{
        GenerationError, GenerationPreset, GenerationProvider, ProviderFuture, ProviderKind,
        ProviderTemplate, ResponseGenerator,
        gemini::{GeminiTemplate, GenerationSettings},
    },
    presentation::ChatPresenter,
    request::{
        CancelResult, EffectPhase, RequestHandle, RequestId, RequestOutcome, RequestState,
        UserInput,
    },
    settings::{
        AppSettings, CaptureSettings, JsonSettingsRepository, SettingsApi, SettingsConfig,
        SettingsError, SettingsRepository, SettingsSource, StoredSettings, VoiceSettings, Volume,
    },
    timeline::{ContextPosition, EventContent},
    voice::{AudioArtifact, AudioFormat, VoiceError, VoiceFuture, VoiceOptions, VoiceProvider},
};
use serde_json::{Value, json};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    net::{TcpStream, tcp::OwnedReadHalf},
    sync::{mpsc, oneshot},
    time::timeout,
};
use uuid::Uuid;

struct GenerationCall {
    context: CharacterContext,
    reply: oneshot::Sender<Result<Arc<str>, GenerationError>>,
}
struct ControlledGeneration(mpsc::UnboundedSender<GenerationCall>);
impl GenerationProvider for ControlledGeneration {
    fn kind(&self) -> ProviderKind {
        ProviderKind::Gemini
    }
    fn generate(
        &self,
        context: CharacterContext,
        _template: ProviderTemplate,
    ) -> ProviderFuture<'_> {
        Box::pin(async move {
            let (reply, receive) = oneshot::channel();
            self.0
                .send(GenerationCall { context, reply })
                .map_err(|_| GenerationError::Transport("fixture stopped".into()))?;
            receive
                .await
                .map_err(|_| GenerationError::Transport("fixture response dropped".into()))?
        })
    }
}

struct VoiceCall {
    text: Arc<str>,
    options: VoiceOptions,
    reply: oneshot::Sender<Result<AudioArtifact, VoiceError>>,
}
struct ControlledVoice(mpsc::UnboundedSender<VoiceCall>);
impl VoiceProvider for ControlledVoice {
    fn synthesize(&self, text: Arc<str>, options: VoiceOptions) -> VoiceFuture<'_> {
        Box::pin(async move {
            assert_ne!(options.voice, "panic", "injected voice provider panic");
            let (reply, receive) = oneshot::channel();
            self.0
                .send(VoiceCall {
                    text,
                    options,
                    reply,
                })
                .map_err(|_| VoiceError::Unavailable)?;
            receive.await.map_err(|_| VoiceError::Unavailable)?
        })
    }
}

struct Storage {
    json: JsonSettingsRepository,
    fail: AtomicBool,
}
impl SettingsRepository for Storage {
    fn load(&self) -> Result<StoredSettings, SettingsError> {
        self.json.load()
    }
    fn save(&self, value: &StoredSettings) -> Result<(), SettingsError> {
        if self.fail.load(Ordering::Acquire) {
            return Err(SettingsError::Storage("injected disk failure".into()));
        }
        self.json.save(value)
    }
}
struct TestFile(PathBuf);
impl Drop for TestFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

async fn next<T>(receive: &mut mpsc::UnboundedReceiver<T>) -> T {
    timeout(Duration::from_secs(5), receive.recv())
        .await
        .unwrap()
        .unwrap()
}
async fn done(handle: &RequestHandle) -> Arc<neuromita::request::RequestSnapshot> {
    timeout(Duration::from_secs(5), handle.wait())
        .await
        .unwrap()
        .unwrap()
}
async fn shown(presenter: &ChatPresenter, id: RequestId, terminal: bool) {
    timeout(Duration::from_secs(5), async {
        let mut observer = presenter.observe();
        loop {
            if observer
                .borrow_and_update()
                .requests
                .iter()
                .any(|row| row.metadata.id == id && (!terminal || row.snapshot.state.is_terminal()))
            {
                return;
            }
            observer.changed().await.unwrap();
        }
    })
    .await
    .unwrap();
}

async fn frame(reader: &mut BufReader<OwnedReadHalf>, predicate: impl Fn(&Value) -> bool) -> Value {
    timeout(Duration::from_secs(5), async {
        loop {
            let mut line = String::new();
            assert_ne!(
                reader.read_line(&mut line).await.unwrap(),
                0,
                "connection closed"
            );
            let value: Value = serde_json::from_str(&line).unwrap();
            if predicate(&value) {
                return value;
            }
        }
    })
    .await
    .unwrap()
}

fn limits() -> RuntimeLimits {
    RuntimeLimits {
        request_queue: NonZeroUsize::new(8).unwrap(),
        discovery_buffer: NonZeroUsize::new(128).unwrap(),
        character_commands: NonZeroUsize::new(32).unwrap(),
        presenter_updates: NonZeroUsize::new(128).unwrap(),
        retained_finished: NonZeroUsize::new(50).unwrap(),
    }
}

fn generator(sender: mpsc::UnboundedSender<GenerationCall>) -> ResponseGenerator {
    let provider: Arc<dyn GenerationProvider> = Arc::new(ControlledGeneration(sender));
    ResponseGenerator::new([provider]).unwrap()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn complete_minimal_contracts() {
    let template = GeminiTemplate::google(
        "fixture-model",
        "fixture-secret-key",
        GenerationSettings::new(0.7, 128, Duration::from_secs(5)).unwrap(),
    )
    .unwrap();
    let preset = GenerationPreset::new(ProviderTemplate::Gemini(template));
    let (generated, mut generations) = mpsc::unbounded_channel();
    let (voiced, mut voices) = mpsc::unbounded_channel();
    let file =
        TestFile(std::env::temp_dir().join(format!("neuromita-settings-{}.json", Uuid::new_v4())));
    let storage = Arc::new(Storage {
        json: JsonSettingsRepository::new(file.0.clone()),
        fail: AtomicBool::new(false),
    });

    std::fs::write(
        &file.0,
        br#"{"schema_version":1,"revision":0,"settings":{}}"#,
    )
    .unwrap();
    let mut invalid = ApplicationConfig::minimal(
        preset.clone(),
        generator(generated.clone()),
        limits(),
        "127.0.0.1:0".parse().unwrap(),
    );
    invalid.settings = SettingsConfig {
        source: SettingsSource::Stored,
        repository: storage.clone(),
    };
    assert!(ApplicationLifecycle::start(invalid).await.is_err());
    storage
        .save(&StoredSettings {
            schema_version: 1,
            revision: 7,
            settings: AppSettings::initial_profile(),
        })
        .unwrap();
    let mut config = ApplicationConfig::minimal(
        preset.clone(),
        generator(generated.clone()),
        limits(),
        "127.0.0.1:0".parse().unwrap(),
    );
    config.voice = Arc::new(ControlledVoice(voiced));
    config.settings = SettingsConfig {
        source: SettingsSource::Stored,
        repository: storage.clone(),
    };
    let app = ApplicationLifecycle::start(config).await.unwrap();
    assert_eq!(
        SettingsApi::snapshot::<VoiceSettings>().unwrap().revision,
        7
    );
    let presenter = app.presenter();

    let mut volume = presenter.settings.voice.volume.observe();
    assert_eq!(volume.next().await.unwrap().get(), 80);
    let before = SettingsApi::snapshot::<VoiceSettings>().unwrap();
    presenter
        .settings
        .voice
        .volume
        .set(Volume::new(42).unwrap())
        .unwrap();
    assert_eq!(
        timeout(Duration::from_secs(2), volume.next())
            .await
            .unwrap()
            .unwrap()
            .get(),
        42
    );
    assert_eq!(
        SettingsApi::snapshot::<VoiceSettings>().unwrap().revision,
        before.revision + 1
    );
    assert!(matches!(
        SettingsApi::replace(before.revision, before.value),
        Err(SettingsError::Conflict { .. })
    ));
    assert!(Volume::new(101).is_err());
    let mut capture = SettingsApi::snapshot::<CaptureSettings>().unwrap();
    capture.value.jpeg_quality = 0;
    assert!(SettingsApi::replace(capture.revision, capture.value).is_err());
    assert_eq!(
        SettingsApi::snapshot::<CaptureSettings>()
            .unwrap()
            .value
            .jpeg_quality,
        80
    );
    SettingsApi::flush().await.unwrap();
    assert_eq!(storage.load().unwrap().settings.voice.volume.get(), 42);

    storage.fail.store(true, Ordering::Release);
    presenter
        .settings
        .voice
        .volume
        .set(Volume::new(43).unwrap())
        .unwrap();
    assert!(matches!(
        SettingsApi::flush().await,
        Err(SettingsError::Storage(_))
    ));
    assert_eq!(presenter.settings.voice.volume.get().get(), 43);
    storage.fail.store(false, Ordering::Release);
    SettingsApi::retry_save().unwrap();
    SettingsApi::flush().await.unwrap();

    let origin = app.at();
    let observation = presenter
        .characters
        .observe(
            CharacterId::Mita,
            UserInput::new("the lamp is blue".into()).unwrap(),
        )
        .await
        .unwrap();
    let observed_at = app.at_event(observation).unwrap();
    let reaction = presenter
        .chat
        .react(CharacterId::Mita, observation, "react to the lamp".into())
        .unwrap();
    let call = next(&mut generations).await;
    assert!(
        call.context
            .history
            .events
            .iter()
            .any(|event| event.id == observation)
    );
    call.reply.send(Ok(Arc::from("blue lamp"))).unwrap();
    assert!(matches!(
        done(&reaction).await.state,
        RequestState::Finished(RequestOutcome::Success(_))
    ));
    assert!(
        presenter
            .characters
            .context(CharacterId::Mita, origin)
            .await
            .unwrap()
            .history
            .events
            .is_empty()
    );
    let old = presenter
        .characters
        .context(CharacterId::Mita, observed_at)
        .await
        .unwrap();
    assert_eq!(old.state.accepted_replies, 0);
    assert_eq!(old.history.events.len(), 1);
    assert!(
        presenter
            .characters
            .context(CharacterId::KindMita, observed_at)
            .await
            .unwrap()
            .history
            .events
            .is_empty()
    );

    let unknown = presenter
        .chat
        .react(CharacterId::KindMita, observation, "unknown".into())
        .unwrap();
    assert!(matches!(
        done(&unknown).await.state,
        RequestState::Finished(RequestOutcome::InternalError(_))
    ));
    assert!(generations.try_recv().is_err());

    let empty = presenter
        .chat
        .reply(CharacterId::Mita, "provider returns empty text".into())
        .unwrap();
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("   ")))
        .unwrap();
    assert!(matches!(
        done(&empty).await.state,
        RequestState::Finished(RequestOutcome::TextGenerationFailed(_))
    ));

    let initiative = presenter
        .chat
        .initiate(CharacterId::KindMita, "say hello".into())
        .unwrap();
    let call = next(&mut generations).await;
    assert!(call.context.history.events.is_empty());
    call.reply.send(Ok(Arc::from("hello"))).unwrap();
    assert!(matches!(
        done(&initiative).await.state,
        RequestState::Finished(RequestOutcome::Success(_))
    ));

    let historical = presenter
        .chat
        .reply_at(
            CharacterId::Mita,
            "historical request".into(),
            ContextPosition::At(origin),
        )
        .unwrap();
    let call = next(&mut generations).await;
    assert!(call.context.history.events.is_empty());
    assert_eq!(call.context.state.accepted_replies, 0);
    call.reply.send(Ok(Arc::from("historical answer"))).unwrap();
    assert!(
        matches!(&done(&historical).await.state, RequestState::Finished(RequestOutcome::InternalError(failure)) if failure.partial_text.as_deref() == Some("historical answer"))
    );
    assert_eq!(
        presenter
            .characters
            .state(CharacterId::Mita)
            .await
            .unwrap()
            .accepted_replies,
        1
    );

    presenter.settings.voice.in_launcher.set(true).unwrap();
    let speaking = presenter
        .chat
        .reply(CharacterId::Mita, "with voice".into())
        .unwrap();
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("spoken answer")))
        .unwrap();
    let speech = next(&mut voices).await;
    assert_eq!(&*speech.text, "spoken answer");
    assert_eq!(speech.options.volume.get(), 43);
    assert!(matches!(
        speaking.snapshot().state,
        RequestState::Processing(neuromita::request::ProcessingStage::GeneratingVoice { .. })
    ));
    assert_eq!(
        presenter
            .characters
            .state(CharacterId::Mita)
            .await
            .unwrap()
            .accepted_replies,
        1
    );
    speech
        .reply
        .send(Ok(AudioArtifact {
            format: AudioFormat::Wave,
            bytes: Arc::from(&b"RIFF-test-fixture"[..]),
        }))
        .unwrap();
    let response = done(&speaking).await;
    assert!(
        matches!(&response.state, RequestState::Finished(RequestOutcome::Success(response)) if response.audio.is_some())
    );

    let partial = presenter
        .chat
        .reply(CharacterId::Mita, "voice fails".into())
        .unwrap();
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("working text")))
        .unwrap();
    next(&mut voices)
        .await
        .reply
        .send(Err(VoiceError::Generation("fixture failure".into())))
        .unwrap();
    assert!(
        matches!(&done(&partial).await.state, RequestState::Finished(RequestOutcome::VoiceGenerationFailed { response, .. }) if &*response.text == "working text")
    );
    assert_eq!(
        presenter
            .characters
            .state(CharacterId::Mita)
            .await
            .unwrap()
            .accepted_replies,
        3
    );

    let cancelled = presenter
        .chat
        .reply(CharacterId::Mita, "cancel voice".into())
        .unwrap();
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("not accepted")))
        .unwrap();
    let speech = next(&mut voices).await;
    assert_eq!(cancelled.cancel(), CancelResult::Requested);
    assert!(matches!(
        done(&cancelled).await.state,
        RequestState::Cancelled
    ));
    drop(speech);
    assert_eq!(
        presenter
            .characters
            .state(CharacterId::Mita)
            .await
            .unwrap()
            .accepted_replies,
        3
    );
    assert!(
        !app.timeline()
            .iter()
            .any(|event| event.request_id == Some(cancelled.id())
                && matches!(event.content, EventContent::CharacterReply { .. }))
    );
    let trace = ChatApi::trace(cancelled.id()).unwrap().unwrap();
    assert_eq!(trace.generated_text.as_deref(), Some("not accepted"));
    assert!(trace.context.is_some());
    assert!(!trace.preset_description.contains("fixture-secret-key"));
    assert!(
        trace
            .transitions
            .iter()
            .any(|change| change.phase == EffectPhase::Discarded)
    );
    let trace = ChatApi::trace(speaking.id()).unwrap().unwrap();
    assert!(
        trace
            .transitions
            .iter()
            .any(|change| change.phase == EffectPhase::Accepting)
    );
    assert!(
        trace
            .transitions
            .iter()
            .any(|change| change.phase == EffectPhase::Applied)
    );
    presenter.settings.voice.voice.set("panic".into()).unwrap();
    let voice_panic = presenter
        .chat
        .reply(CharacterId::Mita, "unexpected voice failure".into())
        .unwrap();
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("retained partial")))
        .unwrap();
    assert!(
        matches!(&done(&voice_panic).await.state, RequestState::Finished(RequestOutcome::InternalError(failure)) if failure.partial_text.as_deref() == Some("retained partial"))
    );
    assert_eq!(
        presenter
            .characters
            .state(CharacterId::Mita)
            .await
            .unwrap()
            .accepted_replies,
        3
    );
    presenter
        .settings
        .voice
        .voice
        .set("default".into())
        .unwrap();
    presenter.settings.voice.in_launcher.set(false).unwrap();

    let stream = TcpStream::connect(app.server().address()).await.unwrap();
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read);
    frame(&mut reader, |value| value["type"] == "connected").await;
    frame(&mut reader, |value| value["type"] == "settings").await;
    write.write_all(b"test\n").await.unwrap();
    let accepted = frame(&mut reader, |value| value["type"] == "accepted").await;
    let id = RequestId(Uuid::parse_str(accepted["request_id"].as_str().unwrap()).unwrap());
    let call = next(&mut generations).await;
    assert_eq!(&*call.context.current_input, "test");
    shown(&presenter.chat, id, false).await;
    call.reply.send(Ok(Arc::from("network answer"))).unwrap();
    let completed = frame(&mut reader, |value| {
        value["type"] == "request_status" && value["state"] == "finished"
    })
    .await;
    assert_eq!(completed["text"], "network answer");
    shown(&presenter.chat, id, true).await;

    let command_id = Uuid::new_v4();
    let command = format!("{}\n", json!({"command_id":command_id,"command":"test"}));
    write.write_all(command.as_bytes()).await.unwrap();
    let original = frame(&mut reader, |value| value["type"] == "accepted").await;
    let call = next(&mut generations).await;
    write.write_all(command.as_bytes()).await.unwrap();
    let repeated = frame(&mut reader, |value| value["type"] == "accepted").await;
    assert_eq!(original["request_id"], repeated["request_id"]);
    assert_eq!(repeated["replayed"], true);
    assert!(generations.try_recv().is_err());
    call.reply.send(Ok(Arc::from("one execution"))).unwrap();
    frame(&mut reader, |value| {
        value["type"] == "request_status" && value["state"] == "finished"
    })
    .await;

    let command = format!(
        "{}\n",
        json!({"command_id":Uuid::new_v4(),"command":"set_volume","value":55})
    );
    write.write_all(command.as_bytes()).await.unwrap();
    frame(&mut reader, |value| value["type"] == "settings_applied").await;
    assert_eq!(
        timeout(Duration::from_secs(2), volume.next())
            .await
            .unwrap()
            .unwrap()
            .get(),
        55
    );

    let command = format!(
        "{}\n",
        json!({"command_id":Uuid::new_v4(),"command":"test"})
    );
    let split = command.len() / 2;
    write.write_all(&command.as_bytes()[..split]).await.unwrap();
    presenter
        .settings
        .voice
        .volume
        .set(Volume::new(56).unwrap())
        .unwrap();
    frame(&mut reader, |value| {
        value["type"] == "settings" && value["settings"]["voice"]["volume"] == 56
    })
    .await;
    write.write_all(&command.as_bytes()[split..]).await.unwrap();
    frame(&mut reader, |value| value["type"] == "accepted").await;
    next(&mut generations)
        .await
        .reply
        .send(Ok(Arc::from("fragmented command")))
        .unwrap();
    frame(&mut reader, |value| {
        value["type"] == "request_status" && value["state"] == "finished"
    })
    .await;

    let address = app.server().address();
    let state = app.server().observe();
    SettingsApi::flush().await.unwrap();
    app.shutdown().await.unwrap();
    assert!(!state.borrow().running);
    assert_eq!(state.borrow().connected_clients, 0);
    assert!(TcpStream::connect(address).await.is_err());
    assert!(matches!(
        SettingsApi::snapshot::<VoiceSettings>(),
        Err(SettingsError::Stopped)
    ));
    assert!(matches!(volume.next().await, Err(SettingsError::Stopped)));
    assert!(
        CharacterApi::get(CharacterId::Mita)
            .unwrap()
            .state()
            .await
            .is_err()
    );
    assert_eq!(storage.load().unwrap().settings.voice.volume.get(), 56);
    drop(write);
}
