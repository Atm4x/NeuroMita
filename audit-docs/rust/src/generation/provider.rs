use std::{collections::HashMap, future::Future, pin::Pin, sync::Arc};

use thiserror::Error;

use super::{GenerationPreset, ProviderKind, ProviderTemplate};
use crate::character::{CharacterContext, ResponseEffect};

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum GenerationError {
    #[error("provider is not registered: {0:?}")]
    Unavailable(ProviderKind),
    #[error("provider is registered twice: {0:?}")]
    Duplicate(ProviderKind),
    #[error("transport error: {0}")]
    Transport(String),
    #[error("provider returned HTTP {0}")]
    Http(u16),
    #[error("invalid provider response: {0}")]
    Response(String),
}

pub struct GenerationRequest {
    pub context: CharacterContext,
    pub preset: GenerationPreset,
}

#[derive(Debug, Clone)]
pub struct ProposedResponse {
    pub text: Arc<str>,
    pub effects: Vec<ResponseEffect>,
}

pub type ProviderFuture<'a> =
    Pin<Box<dyn Future<Output = Result<Arc<str>, GenerationError>> + Send + 'a>>;

pub trait GenerationProvider: Send + Sync {
    fn kind(&self) -> ProviderKind;
    fn generate(&self, context: CharacterContext, template: ProviderTemplate)
    -> ProviderFuture<'_>;
}

pub struct ResponseGenerator {
    providers: HashMap<ProviderKind, Arc<dyn GenerationProvider>>,
}

impl ResponseGenerator {
    pub fn new(
        providers: impl IntoIterator<Item = Arc<dyn GenerationProvider>>,
    ) -> Result<Self, GenerationError> {
        let mut registered = HashMap::new();
        for provider in providers {
            let kind = provider.kind();
            if registered.insert(kind, provider).is_some() {
                return Err(GenerationError::Duplicate(kind));
            }
        }
        Ok(Self {
            providers: registered,
        })
    }

    pub async fn generate(
        &self,
        request: GenerationRequest,
    ) -> Result<ProposedResponse, GenerationError> {
        let template = request.preset.template().clone();
        let kind = template.kind();
        let provider = self
            .providers
            .get(&kind)
            .ok_or(GenerationError::Unavailable(kind))?;
        let text = provider.generate(request.context, template).await?;
        if text.trim().is_empty() {
            return Err(GenerationError::Response(
                "provider returned empty text".into(),
            ));
        }
        Ok(ProposedResponse {
            text,
            effects: vec![ResponseEffect::RecordAcceptedReply],
        })
    }
}
