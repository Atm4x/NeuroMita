use super::{EffectPhase, RequestMetadata, RequestState, UserInput};
use crate::{character::CharacterContext, voice::VoicePlan};
use std::sync::Arc;

#[derive(Debug, Clone)]
pub struct RequestTransition {
    pub revision: u64,
    pub phase: EffectPhase,
    pub state: RequestState,
}
#[derive(Debug, Clone)]
pub struct RequestTrace {
    pub metadata: RequestMetadata,
    pub input: UserInput,
    pub preset_description: String,
    pub voice: VoicePlan,
    pub context: Option<CharacterContext>,
    pub generated_text: Option<Arc<str>>,
    pub transitions: Vec<RequestTransition>,
}
