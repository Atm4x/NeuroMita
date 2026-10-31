use std::{fmt, sync::Arc, time::Duration};

use reqwest::Url;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum PresetError {
    #[error("model must be a nonempty Gemini model identifier")]
    Model,
    #[error("API key must be nonempty without whitespace or control characters")]
    ApiKey,
    #[error("endpoint must be HTTPS, or loopback HTTP, without credentials, query or fragment")]
    Endpoint,
    #[error("temperature must be finite and between 0 and 2")]
    Temperature,
    #[error("output token limit and timeout must be positive")]
    Limits,
}

#[derive(Debug, Clone)]
pub struct GenerationSettings {
    temperature: f32,
    max_output_tokens: u32,
    timeout: Duration,
}

impl GenerationSettings {
    pub fn new(
        temperature: f32,
        max_output_tokens: u32,
        timeout: Duration,
    ) -> Result<Self, PresetError> {
        if !temperature.is_finite() || !(0.0..=2.0).contains(&temperature) {
            return Err(PresetError::Temperature);
        }
        if max_output_tokens == 0 || timeout.is_zero() {
            return Err(PresetError::Limits);
        }
        Ok(Self {
            temperature,
            max_output_tokens,
            timeout,
        })
    }

    pub fn temperature(&self) -> f32 {
        self.temperature
    }
    pub fn max_output_tokens(&self) -> u32 {
        self.max_output_tokens
    }
    pub fn timeout(&self) -> Duration {
        self.timeout
    }
}

#[derive(Clone)]
pub struct GeminiTemplate {
    endpoint: Url,
    model: Arc<str>,
    api_key: Arc<str>,
    settings: GenerationSettings,
}

impl fmt::Debug for GeminiTemplate {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("GeminiTemplate")
            .field("endpoint", &self.endpoint)
            .field("model", &self.model)
            .field("api_key", &"[REDACTED]")
            .field("settings", &self.settings)
            .finish()
    }
}

impl GeminiTemplate {
    pub fn google(
        model: &str,
        api_key: &str,
        settings: GenerationSettings,
    ) -> Result<Self, PresetError> {
        Self::new(
            "https://generativelanguage.googleapis.com/v1beta/",
            model,
            api_key,
            settings,
        )
    }

    pub fn new(
        endpoint: &str,
        model: &str,
        api_key: &str,
        settings: GenerationSettings,
    ) -> Result<Self, PresetError> {
        if model.is_empty()
            || !model
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, b'-' | b'_' | b'.'))
        {
            return Err(PresetError::Model);
        }
        let endpoint = Url::parse(endpoint).map_err(|_| PresetError::Endpoint)?;
        let local = endpoint.host_str().is_some_and(|host| {
            host == "localhost"
                || host
                    .parse::<std::net::IpAddr>()
                    .is_ok_and(|ip| ip.is_loopback())
        });
        if (endpoint.scheme() != "https" && !(endpoint.scheme() == "http" && local))
            || !endpoint.username().is_empty()
            || endpoint.password().is_some()
            || endpoint.query().is_some()
            || endpoint.fragment().is_some()
            || !endpoint.path().ends_with('/')
        {
            return Err(PresetError::Endpoint);
        }
        if api_key.is_empty()
            || api_key
                .chars()
                .any(|character| character.is_whitespace() || character.is_control())
        {
            return Err(PresetError::ApiKey);
        }
        Ok(Self {
            endpoint,
            model: Arc::from(model),
            api_key: Arc::from(api_key),
            settings,
        })
    }

    pub fn model(&self) -> &str {
        &self.model
    }
    pub fn settings(&self) -> &GenerationSettings {
        &self.settings
    }
    pub(crate) fn request_url(&self) -> Url {
        let mut url = self
            .endpoint
            .join(&format!("models/{}:generateContent", self.model))
            .expect("validated Gemini model path");
        url.query_pairs_mut().append_pair("key", &self.api_key);
        url
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn invalid_configuration_is_not_replaced_and_key_is_redacted() {
        assert!(GenerationSettings::new(f32::NAN, 1, Duration::from_secs(1)).is_err());
        assert!(GenerationSettings::new(0.7, 0, Duration::from_secs(1)).is_err());
        let settings = GenerationSettings::new(0.7, 1, Duration::from_secs(1)).unwrap();
        assert!(GeminiTemplate::google("", "key", settings.clone()).is_err());
        assert!(GeminiTemplate::google("model/path", "key", settings.clone()).is_err());
        assert!(GeminiTemplate::google("model", "", settings.clone()).is_err());
        assert!(
            GeminiTemplate::new("http://example.com/", "model", "key", settings.clone()).is_err()
        );
        let template = GeminiTemplate::google("model", "private-test-key", settings).unwrap();
        assert!(!format!("{template:?}").contains("private-test-key"));
    }

    #[test]
    fn query_auth_encodes_the_key_once_and_keeps_debug_redacted() {
        let key = "test+key/&?=#";
        let settings = GenerationSettings::new(0.7, 1, Duration::from_secs(1)).unwrap();
        let template = GeminiTemplate::google("test-model", key, settings.clone()).unwrap();
        let url = template.request_url();
        assert_eq!(url.path(), "/v1beta/models/test-model:generateContent");
        let pairs: Vec<_> = url.query_pairs().collect();
        assert_eq!(pairs.len(), 1);
        assert_eq!(pairs[0].0, "key");
        assert_eq!(pairs[0].1, key);
        assert!(url.fragment().is_none());
        assert!(!format!("{template:?}").contains(key));
        assert!(GeminiTemplate::google("test-model", "key\n", settings).is_err());
    }
}
