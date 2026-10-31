use std::{
    collections::VecDeque,
    io,
    net::SocketAddr,
    num::NonZeroUsize,
    sync::{Arc, Mutex},
};

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    net::{TcpListener, TcpStream, tcp::OwnedReadHalf},
    sync::{mpsc, watch},
    task::JoinSet,
};
use tokio_util::sync::CancellationToken;
use uuid::Uuid;

use crate::{
    api::ChatApi,
    character::CharacterId,
    generation::GenerationPreset,
    lifecycle::Lifecycle,
    request::{
        ProcessingStage, ReplyRequest, RequestHandle, RequestId, RequestOutcome, RequestSnapshot,
        RequestSource, RequestState, UserInput,
    },
    settings::{SettingsApi, VoiceSettings, Volume},
    voice::{VoiceOptions, VoicePlan},
};

pub struct ServerConfig {
    pub bind: SocketAddr,
    pub test_character: CharacterId,
    pub preset: GenerationPreset,
    pub max_clients: NonZeroUsize,
    pub outbound_capacity: NonZeroUsize,
    pub max_command_bytes: NonZeroUsize,
    pub receipt_capacity: NonZeroUsize,
}

impl ServerConfig {
    pub fn test_protocol(
        bind: SocketAddr,
        test_character: CharacterId,
        preset: GenerationPreset,
    ) -> Self {
        Self {
            bind,
            test_character,
            preset,
            max_clients: NonZeroUsize::new(16).expect("positive"),
            outbound_capacity: NonZeroUsize::new(64).expect("positive"),
            max_command_bytes: NonZeroUsize::new(65536).expect("positive"),
            receipt_capacity: NonZeroUsize::new(128).expect("positive"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ServerSnapshot {
    pub running: bool,
    pub connected_clients: usize,
    pub accepted_connections: u64,
    pub last_error: Option<Arc<str>>,
}

struct ServerState {
    snapshot: Mutex<ServerSnapshot>,
    updates: watch::Sender<Arc<ServerSnapshot>>,
}
impl ServerState {
    fn change(&self, edit: impl FnOnce(&mut ServerSnapshot)) {
        let mut snapshot = self.snapshot.lock().expect("server state poisoned");
        edit(&mut snapshot);
        self.updates.send_replace(Arc::new(snapshot.clone()));
    }
}

#[derive(Clone)]
pub struct ServerHandle {
    address: SocketAddr,
    state: Arc<ServerState>,
}
impl ServerHandle {
    pub fn address(&self) -> SocketAddr {
        self.address
    }
    pub fn snapshot(&self) -> Arc<ServerSnapshot> {
        Arc::clone(&self.state.updates.borrow())
    }
    pub fn observe(&self) -> watch::Receiver<Arc<ServerSnapshot>> {
        self.state.updates.subscribe()
    }
}

pub struct ServerLifecycle {
    listener: TcpListener,
    config: Arc<ServerConfig>,
    state: Arc<ServerState>,
}
impl ServerLifecycle {
    pub async fn bind(config: ServerConfig) -> io::Result<(Self, ServerHandle)> {
        let listener = TcpListener::bind(config.bind).await?;
        let address = listener.local_addr()?;
        let snapshot = ServerSnapshot {
            running: false,
            connected_clients: 0,
            accepted_connections: 0,
            last_error: None,
        };
        let (updates, _) = watch::channel(Arc::new(snapshot.clone()));
        let state = Arc::new(ServerState {
            snapshot: Mutex::new(snapshot),
            updates,
        });
        Ok((
            Self {
                listener,
                config: Arc::new(config),
                state: Arc::clone(&state),
            },
            ServerHandle { address, state },
        ))
    }
}

impl Lifecycle for ServerLifecycle {
    type Error = io::Error;
    async fn run(self, stop: CancellationToken) -> io::Result<()> {
        let clients_stop = CancellationToken::new();
        let mut clients = JoinSet::new();
        self.state.change(|state| state.running = true);
        let mut failure = None;
        loop {
            tokio::select! {
                biased;
                _ = stop.cancelled() => break,
                connected = self.listener.accept() => {
                    match connected {
                        Ok((stream, _)) => {
                            if clients.len() >= self.config.max_clients.get() { drop(stream); continue; }
                            self.state.change(|state| { state.connected_clients += 1; state.accepted_connections += 1; });
                            let state = Arc::clone(&self.state);
                            let config = Arc::clone(&self.config);
                            let stop = clients_stop.clone();
                            clients.spawn(async move {
                                let _connected = Connected(state);
                                client(stream, config, stop).await
                            });
                        }
                        Err(error) => { failure = Some(error); break; }
                    }
                }
                result = clients.join_next(), if !clients.is_empty() => {
                    match result {
                        Some(Ok(Err(error))) => self.state.change(|state| state.last_error = Some(Arc::from(error.to_string()))),
                        Some(Err(error)) => self.state.change(|state| state.last_error = Some(Arc::from(error.to_string()))),
                        _ => {}
                    }
                }
            }
        }
        clients_stop.cancel();
        while clients.join_next().await.is_some() {}
        self.state.change(|state| state.running = false);
        match failure {
            Some(error) => Err(error),
            None => Ok(()),
        }
    }
}

struct Connected(Arc<ServerState>);
impl Drop for Connected {
    fn drop(&mut self) {
        self.0
            .change(|state| state.connected_clients = state.connected_clients.saturating_sub(1));
    }
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "command", rename_all = "snake_case", deny_unknown_fields)]
enum Command {
    Test,
    Reply {
        character: CharacterId,
        text: String,
    },
    Cancel {
        request_id: Uuid,
    },
    Settings,
    SetVolume {
        value: Volume,
    },
}

#[derive(Deserialize)]
struct Envelope {
    command_id: Uuid,
    #[serde(flatten)]
    command: Command,
}

struct Receipt {
    command_id: Uuid,
    fingerprint: String,
    handle: RequestHandle,
}

async fn send(
    outbound: &mpsc::Sender<Value>,
    value: Value,
    stop: &CancellationToken,
) -> io::Result<()> {
    tokio::select! {
        biased;
        _ = stop.cancelled() => Err(io::Error::new(io::ErrorKind::Interrupted, "connection stopping")),
        sent = outbound.send(value) => sent.map_err(|_| io::Error::new(io::ErrorKind::BrokenPipe, "client writer closed")),
    }
}

async fn read_command(
    reader: &mut BufReader<OwnedReadHalf>,
    limit: usize,
) -> io::Result<Option<String>> {
    let mut result = Vec::new();
    loop {
        let buffer = reader.fill_buf().await?;
        if buffer.is_empty() {
            return if result.is_empty() {
                Ok(None)
            } else {
                Err(io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    "incomplete command",
                ))
            };
        }
        let newline = buffer.iter().position(|byte| *byte == b'\n');
        let count = newline.map_or(buffer.len(), |index| index + 1);
        if result.len() + count > limit {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "command too long",
            ));
        }
        result.extend_from_slice(&buffer[..count]);
        reader.consume(count);
        if newline.is_some() {
            let text = String::from_utf8(result)
                .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "command is not UTF-8"))?;
            return Ok(Some(text.trim_end_matches(['\r', '\n']).to_owned()));
        }
    }
}

async fn client(
    stream: TcpStream,
    config: Arc<ServerConfig>,
    parent_stop: CancellationToken,
) -> io::Result<()> {
    let stop = parent_stop.child_token();
    let client_id = Uuid::new_v4();
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read);
    let (outbound, mut messages) = mpsc::channel::<Value>(config.outbound_capacity.get());
    let writer_stop = stop.clone();
    let writer = tokio::spawn(async move {
        let _writer_guard = writer_stop.clone().drop_guard();
        loop {
            let message = tokio::select! { biased; _ = writer_stop.cancelled() => break, message = messages.recv() => match message { Some(message) => message, None => break } };
            let mut bytes = serde_json::to_vec(&message).map_err(io::Error::other)?;
            bytes.push(b'\n');
            tokio::select! { biased; _ = writer_stop.cancelled() => break, result = write.write_all(&bytes) => result? }
        }
        Ok::<(), io::Error>(())
    });
    let mut observers = JoinSet::new();
    let mut receipts: VecDeque<Receipt> = VecDeque::new();
    let result = async {
        send(&outbound, json!({"type":"connected","client_id":client_id}), &stop).await?;
        let mut settings = SettingsApi::observe().map_err(io::Error::other)?;
        let settings_send = outbound.clone();
        let settings_stop = stop.clone();
        observers.spawn(async move {
            loop {
                let snapshot = Arc::clone(&settings.borrow_and_update());
                let message = json!({"type":"settings","revision":snapshot.revision,"settings":snapshot.values});
                if send(&settings_send, message, &settings_stop).await.is_err() { break; }
                tokio::select! { biased; _ = settings_stop.cancelled() => break, changed = settings.changed() => if changed.is_err() { break; } }
            }
        });
        loop {
            while let Some(result) = observers.try_join_next() {
                result.map_err(io::Error::other)?;
            }
            let line = tokio::select! {
                biased;
                _ = stop.cancelled() => break,
                line = read_command(&mut reader, config.max_command_bytes.get()) => match line? { Some(line) => line, None => break },
            };
            let envelope = if line == "test" { Ok(Envelope { command_id: Uuid::new_v4(), command: Command::Test }) } else { serde_json::from_str::<Envelope>(&line) };
            let envelope = match envelope {
                Ok(envelope) => envelope,
                Err(error) => { send(&outbound, json!({"type":"error","error":error.to_string()}), &stop).await?; continue; }
            };
            let fingerprint = serde_json::to_string(&envelope.command).map_err(io::Error::other)?;
            if let Some(receipt) = receipts.iter().find(|receipt| receipt.command_id == envelope.command_id) {
                if receipt.fingerprint != fingerprint {
                    send(&outbound, json!({"type":"error","command_id":envelope.command_id,"error":"command ID reused for different intent"}), &stop).await?;
                } else {
                    send(&outbound, json!({"type":"accepted","command_id":envelope.command_id,"request_id":receipt.handle.id().0,"replayed":true}), &stop).await?;
                    send(&outbound, status(&receipt.handle.snapshot()), &stop).await?;
                }
                continue;
            }
            match envelope.command {
                Command::Test | Command::Reply { .. } => {
                    if receipts.len() >= config.receipt_capacity.get() {
                        if receipts.front().is_some_and(|receipt| receipt.handle.snapshot().state.is_terminal()) { receipts.pop_front(); }
                        else { send(&outbound, json!({"type":"error","error":"too many tracked requests"}), &stop).await?; continue; }
                    }
                    let (character, text) = match envelope.command {
                        Command::Test => (config.test_character, "test".to_owned()),
                        Command::Reply { character, text } => (character, text),
                        _ => unreachable!(),
                    };
                    let voice = SettingsApi::snapshot::<VoiceSettings>().map_err(io::Error::other)?.value;
                    let voice = if voice.in_game { VoicePlan::Synthesize(VoiceOptions { voice: voice.voice, volume: voice.volume }) } else { VoicePlan::Disabled };
                    let request = UserInput::new(text).map(|input| ReplyRequest::new(character, config.preset.clone(), input, RequestSource::Client(client_id)).with_voice(voice));
                    let handle = match request.map_err(|error| error.to_string()).and_then(|request| ChatApi::reply(request).map_err(|error| error.to_string())) {
                        Ok(handle) => handle,
                        Err(error) => { send(&outbound, json!({"type":"error","command_id":envelope.command_id,"error":error}), &stop).await?; continue; }
                    };
                    send(&outbound, json!({"type":"accepted","command_id":envelope.command_id,"request_id":handle.id().0,"replayed":false}), &stop).await?;
                    receipts.push_back(Receipt { command_id: envelope.command_id, fingerprint, handle: handle.clone() });
                    let outbound = outbound.clone();
                    let stop = stop.clone();
                    observers.spawn(async move {
                        let mut observer = handle.observe();
                        loop {
                            let snapshot = tokio::select! { biased; _ = stop.cancelled() => break, snapshot = observer.next() => match snapshot { Ok(Some(snapshot)) => snapshot, _ => break } };
                            if send(&outbound, status(&snapshot), &stop).await.is_err() { break; }
                        }
                    });
                }
                Command::Cancel { request_id } => {
                    let response = match receipts.iter().find(|receipt| receipt.handle.id() == RequestId(request_id)) {
                        Some(receipt) => json!({"type":"cancel","request_id":request_id,"result":format!("{:?}", receipt.handle.cancel())}),
                        None => json!({"type":"error","error":"request does not belong to this connection"}),
                    };
                    send(&outbound, response, &stop).await?;
                }
                Command::Settings => {
                    let snapshot = SettingsApi::snapshot_all().map_err(io::Error::other)?;
                    send(&outbound, json!({"type":"settings","revision":snapshot.revision,"settings":snapshot.values}), &stop).await?;
                }
                Command::SetVolume { value } => {
                    let result = SettingsApi::edit::<VoiceSettings>(|voice| voice.volume = value);
                    let response = match result { Ok(snapshot) => json!({"type":"settings_applied","revision":snapshot.revision}), Err(error) => json!({"type":"error","error":error.to_string()}) };
                    send(&outbound, response, &stop).await?;
                }
            }
        }
        Ok(())
    }.await;
    stop.cancel();
    observers.abort_all();
    while observers.join_next().await.is_some() {}
    drop(outbound);
    let written = writer.await.map_err(io::Error::other)?;
    result.and(written)
}

pub fn status(snapshot: &RequestSnapshot) -> Value {
    let mut message = json!({"type":"request_status","request_id":snapshot.metadata.id.0,"character":snapshot.metadata.character_id.to_string(),"revision":snapshot.revision});
    match &snapshot.state {
        RequestState::Pending => message["state"] = json!("pending"),
        RequestState::Processing(stage) => {
            message["state"] = json!("processing");
            match stage {
                ProcessingStage::GeneratingText => message["stage"] = json!("text"),
                ProcessingStage::GeneratingVoice { text } => {
                    message["stage"] = json!("voice");
                    message["text"] = json!(text);
                }
            }
        }
        RequestState::Cancelled => message["state"] = json!("cancelled"),
        RequestState::Finished(outcome) => {
            message["state"] = json!("finished");
            match outcome {
                RequestOutcome::Success(response) => {
                    message["outcome"] = json!("success");
                    message["text"] = json!(response.text);
                    message["event_id"] = json!(response.event_id);
                    if let Some(audio) = &response.audio {
                        message["audio"] = json!({"format":"wave","bytes":audio.bytes.as_ref()});
                    }
                }
                RequestOutcome::VoiceGenerationFailed { response, error } => {
                    message["outcome"] = json!("voice_error");
                    message["text"] = json!(response.text);
                    message["error"] = json!(error.to_string());
                }
                RequestOutcome::TextGenerationFailed(error) => {
                    message["outcome"] = json!("text_error");
                    message["error"] = json!(error.to_string());
                }
                RequestOutcome::InternalError(error) => {
                    message["outcome"] = json!("internal_error");
                    message["error"] = json!(error.message);
                    message["partial_text"] = json!(error.partial_text);
                }
            }
        }
    }
    message
}
