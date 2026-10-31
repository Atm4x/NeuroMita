mod terminal;

use std::{error::Error, num::NonZeroUsize, process::ExitCode, sync::Arc, time::Duration};

use neuromita::{
    app::{ApplicationConfig, ApplicationLifecycle, RuntimeLimits},
    generation::{
        GenerationPreset, GenerationProvider, ProviderTemplate, ResponseGenerator,
        gemini::{GeminiProvider, GeminiTemplate, GenerationSettings},
    },
};

#[tokio::main]
async fn main() -> ExitCode {
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Error: {error}");
            ExitCode::FAILURE
        }
    }
}

async fn run() -> Result<(), Box<dyn Error>> {
    let Some(options) = terminal::Options::parse()? else {
        return Ok(());
    };
    let key = std::env::var("GEMINI_API_KEY").map_err(|_| {
        std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "GEMINI_API_KEY must be set",
        )
    })?;
    let settings = GenerationSettings::new(0.7, 2048, Duration::from_secs(60))?;
    let template = GeminiTemplate::google(&options.model, &key, settings)?;
    let preset = GenerationPreset::new(ProviderTemplate::Gemini(template));
    let provider: Arc<dyn GenerationProvider> = Arc::new(GeminiProvider::new()?);
    let generator = ResponseGenerator::new([provider])?;
    let limits = RuntimeLimits {
        request_queue: NonZeroUsize::new(16).expect("positive limit"),
        discovery_buffer: NonZeroUsize::new(128).expect("positive limit"),
        character_commands: NonZeroUsize::new(32).expect("positive limit"),
        presenter_updates: NonZeroUsize::new(128).expect("positive limit"),
        retained_finished: NonZeroUsize::new(100).expect("positive limit"),
    };
    let config = ApplicationConfig::minimal(preset, generator, limits, options.listen);
    let app = ApplicationLifecycle::start(config).await?;
    println!("Server listening on {}", app.server().address());
    let result = terminal::run(&app.presenter().chat, options).await;
    let stopped = app.shutdown().await;
    result?;
    stopped?;
    Ok(())
}
