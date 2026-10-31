pub mod gemini;
mod provider;

pub use provider::{
    GenerationError, GenerationProvider, GenerationRequest, ProposedResponse, ProviderFuture,
    ResponseGenerator,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ProviderKind {
    Gemini,
}

#[derive(Debug, Clone)]
pub enum ProviderTemplate {
    Gemini(gemini::GeminiTemplate),
}

impl ProviderTemplate {
    pub fn kind(&self) -> ProviderKind {
        match self {
            Self::Gemini(_) => ProviderKind::Gemini,
        }
    }
}

#[derive(Debug, Clone)]
pub struct GenerationPreset {
    template: ProviderTemplate,
}

impl GenerationPreset {
    pub fn new(template: ProviderTemplate) -> Self {
        Self { template }
    }
    pub fn template(&self) -> &ProviderTemplate {
        &self.template
    }
}
