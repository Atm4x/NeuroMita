use std::{fmt, sync::Arc};

use thiserror::Error;
use uuid::Uuid;

use crate::{
    character::CharacterId,
    generation::{GenerationError, GenerationPreset},
    timeline::{ContextAnchor, ContextPosition, EventId},
    voice::{AudioArtifact, VoiceError, VoicePlan},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct RequestId(pub Uuid);

impl RequestId {
    pub(crate) fn new() -> Self {
        Self(Uuid::new_v4())
    }
}
impl fmt::Display for RequestId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RequestSource {
    Presenter,
    Client(Uuid),
}

#[derive(Debug, Error)]
pub enum InputError {
    #[error("message must not be empty")]
    Empty,
    #[error("message exceeds 64 KiB")]
    TooLarge,
}

#[derive(Debug, Clone)]
pub struct UserInput {
    event_id: EventId,
    text: Arc<str>,
}

impl UserInput {
    pub fn new(text: String) -> Result<Self, InputError> {
        if text.trim().is_empty() {
            return Err(InputError::Empty);
        }
        if text.len() > 64 * 1024 {
            return Err(InputError::TooLarge);
        }
        Ok(Self {
            event_id: EventId::new(),
            text: Arc::from(text),
        })
    }
    pub fn event_id(&self) -> EventId {
        self.event_id
    }
    pub fn text(&self) -> &Arc<str> {
        &self.text
    }
}

pub trait Message: Send + Sync + fmt::Debug {
    fn character_id(&self) -> CharacterId;
    fn preset(&self) -> &GenerationPreset;
    fn input(&self) -> &UserInput;
    fn source(&self) -> RequestSource;
    fn intent(&self) -> TurnIntent;
    fn voice(&self) -> &VoicePlan;
    fn at(&self) -> ContextPosition;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TurnIntent {
    Reply,
    React(EventId),
    Initiate,
}

#[derive(Debug)]
pub struct ReplyRequest {
    character_id: CharacterId,
    preset: GenerationPreset,
    input: UserInput,
    source: RequestSource,
    voice: VoicePlan,
    at: ContextPosition,
}

impl ReplyRequest {
    pub fn new(
        character_id: CharacterId,
        preset: GenerationPreset,
        input: UserInput,
        source: RequestSource,
    ) -> Self {
        Self {
            character_id,
            preset,
            input,
            source,
            voice: VoicePlan::Disabled,
            at: ContextPosition::Latest,
        }
    }
    pub fn with_voice(mut self, voice: VoicePlan) -> Self {
        self.voice = voice;
        self
    }
    pub fn at(mut self, at: ContextPosition) -> Self {
        self.at = at;
        self
    }
}

impl Message for ReplyRequest {
    fn character_id(&self) -> CharacterId {
        self.character_id
    }
    fn preset(&self) -> &GenerationPreset {
        &self.preset
    }
    fn input(&self) -> &UserInput {
        &self.input
    }
    fn source(&self) -> RequestSource {
        self.source
    }
    fn intent(&self) -> TurnIntent {
        TurnIntent::Reply
    }
    fn voice(&self) -> &VoicePlan {
        &self.voice
    }
    fn at(&self) -> ContextPosition {
        self.at
    }
}

#[derive(Debug)]
pub struct ReactRequest {
    message: ReplyRequest,
    event: EventId,
}
impl ReactRequest {
    pub fn new(
        character: CharacterId,
        preset: GenerationPreset,
        event: EventId,
        instruction: UserInput,
        source: RequestSource,
    ) -> Self {
        Self {
            message: ReplyRequest::new(character, preset, instruction, source),
            event,
        }
    }
    pub fn with_voice(mut self, voice: VoicePlan) -> Self {
        self.message = self.message.with_voice(voice);
        self
    }
    pub fn at(mut self, at: ContextPosition) -> Self {
        self.message = self.message.at(at);
        self
    }
}
impl Message for ReactRequest {
    fn character_id(&self) -> CharacterId {
        self.message.character_id()
    }
    fn preset(&self) -> &GenerationPreset {
        self.message.preset()
    }
    fn input(&self) -> &UserInput {
        self.message.input()
    }
    fn source(&self) -> RequestSource {
        self.message.source()
    }
    fn intent(&self) -> TurnIntent {
        TurnIntent::React(self.event)
    }
    fn voice(&self) -> &VoicePlan {
        self.message.voice()
    }
    fn at(&self) -> ContextPosition {
        Message::at(&self.message)
    }
}

#[derive(Debug)]
pub struct InitiateRequest {
    message: ReplyRequest,
}
impl InitiateRequest {
    pub fn new(
        character: CharacterId,
        preset: GenerationPreset,
        instruction: UserInput,
        source: RequestSource,
    ) -> Self {
        Self {
            message: ReplyRequest::new(character, preset, instruction, source),
        }
    }
    pub fn with_voice(mut self, voice: VoicePlan) -> Self {
        self.message = self.message.with_voice(voice);
        self
    }
    pub fn at(mut self, at: ContextPosition) -> Self {
        self.message = self.message.at(at);
        self
    }
}
impl Message for InitiateRequest {
    fn character_id(&self) -> CharacterId {
        self.message.character_id()
    }
    fn preset(&self) -> &GenerationPreset {
        self.message.preset()
    }
    fn input(&self) -> &UserInput {
        self.message.input()
    }
    fn source(&self) -> RequestSource {
        self.message.source()
    }
    fn intent(&self) -> TurnIntent {
        TurnIntent::Initiate
    }
    fn voice(&self) -> &VoicePlan {
        self.message.voice()
    }
    fn at(&self) -> ContextPosition {
        Message::at(&self.message)
    }
}

#[derive(Debug, Clone)]
pub struct RequestMetadata {
    pub id: RequestId,
    pub character_id: CharacterId,
    pub source: RequestSource,
    pub intent: TurnIntent,
}

#[derive(Debug, Clone)]
pub struct AcceptedResponse {
    pub text: Arc<str>,
    pub event_id: EventId,
    pub context: ContextAnchor,
    pub audio: Option<AudioArtifact>,
}

#[derive(Debug, Clone)]
pub enum RequestOutcome {
    Success(AcceptedResponse),
    TextGenerationFailed(GenerationError),
    VoiceGenerationFailed {
        response: AcceptedResponse,
        error: VoiceError,
    },
    InternalError(InternalFailure),
}

#[derive(Debug, Clone)]
pub struct InternalFailure {
    pub message: Arc<str>,
    pub partial_text: Option<Arc<str>>,
}
impl fmt::Display for InternalFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.message.fmt(f)
    }
}
impl From<Arc<str>> for InternalFailure {
    fn from(message: Arc<str>) -> Self {
        Self {
            message,
            partial_text: None,
        }
    }
}

#[derive(Debug, Clone)]
pub enum ProcessingStage {
    GeneratingText,
    GeneratingVoice { text: Arc<str> },
}

#[derive(Debug, Clone)]
pub enum RequestState {
    Pending,
    Processing(ProcessingStage),
    Finished(RequestOutcome),
    Cancelled,
}

impl RequestState {
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Finished(_) | Self::Cancelled)
    }
}

#[derive(Debug, Clone)]
pub struct RequestSnapshot {
    pub metadata: RequestMetadata,
    pub revision: u64,
    pub state: RequestState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EffectPhase {
    Working,
    Accepting,
    Applied,
    Discarded,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CancelResult {
    Cancelled,
    Requested,
    TooLate,
    AlreadyFinished,
}

#[derive(Debug, Error)]
pub enum SubmitError {
    #[error("ChatApi is not initialized")]
    Uninitialized,
    #[error("application is stopping")]
    Stopped,
    #[error("request queue is full")]
    QueueFull,
    #[error("request queue is closed")]
    QueueClosed,
    #[error("character is unavailable")]
    CharacterUnavailable,
}

#[derive(Debug, Error)]
pub enum ObserveError {
    #[error("request observation closed before completion")]
    ClosedBeforeCompletion,
}
