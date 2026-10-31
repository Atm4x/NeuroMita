use std::{num::NonZeroUsize, sync::Arc, time::Duration};

use neuromita::{
    app::{ApplicationConfig, ApplicationLifecycle, RuntimeLimits},
    character::CharacterId,
    generation::{
        GenerationPreset, GenerationProvider, ProviderTemplate, ResponseGenerator,
        gemini::{GeminiProvider, GeminiTemplate, GenerationSettings},
    },
    request::{RequestOutcome, RequestState},
};

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires explicit local Gemini fixture path and preset ID; makes one paid/provider request"]
async fn live_presenter_to_gemini() {
    let path =
        std::env::var("NEUROMITA_LIVE_GEMINI_PRESET_FILE").expect("explicit fixture path required");
    let id = std::env::var("NEUROMITA_LIVE_GEMINI_PRESET_ID")
        .expect("explicit fixture preset ID required");
    let bytes = std::fs::read(path).expect("fixture cannot be read");
    let fixture: serde_json::Value =
        serde_json::from_slice(&bytes).expect("fixture is not valid JSON");
    let preset = &fixture["presets"][&id];
    let model = preset["default_model"].as_str().expect("model is required");
    let key = preset["key"].as_str().expect("key is required");
    let template = GeminiTemplate::google(
        model,
        key,
        GenerationSettings::new(0.0, 8192, Duration::from_secs(90)).unwrap(),
    )
    .expect("invalid explicit Gemini configuration");
    let preset = GenerationPreset::new(ProviderTemplate::Gemini(template));
    let provider: Arc<dyn GenerationProvider> = Arc::new(GeminiProvider::new().unwrap());
    let limits = RuntimeLimits {
        request_queue: NonZeroUsize::new(2).unwrap(),
        discovery_buffer: NonZeroUsize::new(8).unwrap(),
        character_commands: NonZeroUsize::new(8).unwrap(),
        presenter_updates: NonZeroUsize::new(8).unwrap(),
        retained_finished: NonZeroUsize::new(4).unwrap(),
    };
    let app = ApplicationLifecycle::start(ApplicationConfig::minimal(
        preset,
        ResponseGenerator::new([provider]).unwrap(),
        limits,
        "127.0.0.1:0".parse().unwrap(),
    ))
    .await
    .unwrap();
    let request = app
        .presenter()
        .chat
        .reply(
            CharacterId::Mita,
            "Проверка соединения. Ответь одним словом: готово".into(),
        )
        .unwrap();
    let result = tokio::time::timeout(Duration::from_secs(100), request.wait()).await;
    app.shutdown().await.unwrap();
    let snapshot = result.expect("Gemini request timed out").unwrap();
    match &snapshot.state {
        RequestState::Finished(RequestOutcome::Success(response)) => {
            assert!(!response.text.trim().is_empty());
            println!(
                "Gemini live check succeeded: model={model}, request={}, answer={}",
                request.id(),
                response.text
            );
        }
        state => panic!("Gemini live request did not succeed: {state:?}"),
    }
}
