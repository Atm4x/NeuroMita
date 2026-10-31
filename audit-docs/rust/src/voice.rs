use std::{future::Future, pin::Pin, sync::Arc};

use thiserror::Error;

use crate::settings::Volume;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VoiceOptions {
    pub voice: String,
    pub volume: Volume,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VoicePlan {
    Disabled,
    Synthesize(VoiceOptions),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AudioFormat {
    Wave,
}

#[derive(Debug, Clone)]
pub struct AudioArtifact {
    pub format: AudioFormat,
    pub bytes: Arc<[u8]>,
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum VoiceError {
    #[error("voice engine is not configured")]
    Unavailable,
    #[error("voice generation failed: {0}")]
    Generation(String),
}

pub type VoiceFuture<'a> =
    Pin<Box<dyn Future<Output = Result<AudioArtifact, VoiceError>> + Send + 'a>>;
pub trait VoiceProvider: Send + Sync {
    fn synthesize(&self, text: Arc<str>, options: VoiceOptions) -> VoiceFuture<'_>;
}

pub struct UnavailableVoiceProvider;
impl VoiceProvider for UnavailableVoiceProvider {
    fn synthesize(&self, _text: Arc<str>, _options: VoiceOptions) -> VoiceFuture<'_> {
        Box::pin(async { Err(VoiceError::Unavailable) })
    }
}
