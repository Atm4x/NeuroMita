use std::{
    collections::HashMap,
    num::NonZeroUsize,
    sync::{Arc, Mutex},
};

use std::sync::atomic::{AtomicBool, Ordering};
use thiserror::Error;
use tokio::{sync::mpsc, task::JoinHandle};
use tokio_util::sync::CancellationToken;

static STARTING: AtomicBool = AtomicBool::new(false);
struct StartupGuard {
    committed: bool,
}
impl Drop for StartupGuard {
    fn drop(&mut self) {
        if !self.committed {
            STARTING.store(false, Ordering::Release);
        }
    }
}

use crate::{
    api::{CharacterApi, ChatApi, ChatApiState},
    character::{CharacterHandle, CharacterId, CharacterRegistry},
    generation::{GenerationPreset, ResponseGenerator},
    lifecycle::Lifecycle,
    presentation::{CharactersPresenter, GuiPresenter, PresenterRunner, SettingsPresenter},
    request::{MessageHandler, RequestRegistry},
    server::{ServerConfig, ServerHandle, ServerLifecycle},
    settings::{
        AppSettings, MemorySettingsRepository, SettingsConfig, SettingsError, SettingsLifecycle,
        SettingsOwner, SettingsSource,
    },
    timeline::{SessionTimeline, TimelineEvent},
    voice::{UnavailableVoiceProvider, VoiceProvider},
};

pub struct RuntimeLimits {
    pub request_queue: NonZeroUsize,
    pub discovery_buffer: NonZeroUsize,
    pub character_commands: NonZeroUsize,
    pub presenter_updates: NonZeroUsize,
    pub retained_finished: NonZeroUsize,
}

pub struct ApplicationConfig {
    pub preset: GenerationPreset,
    pub generator: ResponseGenerator,
    pub limits: RuntimeLimits,
    pub voice: Arc<dyn VoiceProvider>,
    pub settings: SettingsConfig,
    pub server: ServerConfig,
}

impl ApplicationConfig {
    pub fn minimal(
        preset: GenerationPreset,
        generator: ResponseGenerator,
        limits: RuntimeLimits,
        bind: std::net::SocketAddr,
    ) -> Self {
        Self {
            server: ServerConfig::test_protocol(bind, CharacterId::Mita, preset.clone()),
            preset,
            generator,
            limits,
            voice: Arc::new(UnavailableVoiceProvider),
            settings: SettingsConfig {
                source: SettingsSource::Initial(AppSettings::initial_profile()),
                repository: Arc::new(MemorySettingsRepository::new()),
            },
        }
    }
}

#[derive(Debug, Error)]
pub enum ApplicationError {
    #[error("ChatApi has already been initialized in this process")]
    AlreadyInitialized,
    #[error("application task failed: {0}")]
    Task(String),
    #[error(transparent)]
    Settings(#[from] SettingsError),
    #[error("server: {0}")]
    Server(#[from] std::io::Error),
}

pub struct ApplicationLifecycle {
    api: Arc<ChatApiState>,
    characters: CharacterRegistry,
    timeline: Arc<Mutex<SessionTimeline>>,
    presenter: GuiPresenter,
    workers_stop: CancellationToken,
    owners_stop: CancellationToken,
    presenter_stop: CancellationToken,
    workers: Vec<JoinHandle<()>>,
    owners: Vec<JoinHandle<()>>,
    presenter_task: Option<JoinHandle<()>>,
    settings_owner: Arc<SettingsOwner>,
    settings_stop: CancellationToken,
    settings_task: Option<JoinHandle<Result<(), SettingsError>>>,
    server: ServerHandle,
    server_stop: CancellationToken,
    server_task: Option<JoinHandle<std::io::Result<()>>>,
}

impl ApplicationLifecycle {
    pub async fn start(config: ApplicationConfig) -> Result<Self, ApplicationError> {
        if ChatApi::is_initialized()
            || STARTING
                .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
                .is_err()
        {
            return Err(ApplicationError::AlreadyInitialized);
        }
        let mut startup = StartupGuard { committed: false };
        let ApplicationConfig {
            preset,
            generator,
            limits,
            voice,
            settings,
            server,
        } = config;
        let settings = SettingsLifecycle::prepare(settings).await?;
        let (server_lifecycle, server) = ServerLifecycle::bind(server).await?;
        let registry = Arc::new(RequestRegistry::new(limits.discovery_buffer.get()));
        let timeline = Arc::new(Mutex::new(SessionTimeline::new()));
        let workers_stop = CancellationToken::new();
        let owners_stop = CancellationToken::new();
        let presenter_stop = CancellationToken::new();
        let (characters, owners) = CharacterRegistry::spawn(
            Arc::clone(&timeline),
            owners_stop.clone(),
            limits.character_commands.get(),
        );
        let generator = Arc::new(generator);
        let mut handlers = HashMap::new();
        let mut workers = Vec::new();
        for id in CharacterId::ALL {
            let (send, receive) = mpsc::channel(limits.request_queue.get());
            handlers.insert(id, send);
            let worker = MessageHandler {
                character: characters.get(id).expect("hardcoded character exists"),
                registry: Arc::clone(&registry),
                generator: Arc::clone(&generator),
                voice: Arc::clone(&voice),
            };
            workers.push(tokio::spawn(
                worker.run_queue(receive, workers_stop.clone()),
            ));
        }
        let api = Arc::new(ChatApiState::new(registry, handlers));
        let discovery = api.registry.observe();
        settings.install()?;
        CharacterApi::install(characters.clone())
            .map_err(|_| ApplicationError::AlreadyInitialized)?;
        if ChatApi::install(Arc::clone(&api)).is_err() {
            api.close();
            workers_stop.cancel();
            for worker in workers {
                let _ = worker.await;
            }
            owners_stop.cancel();
            for owner in owners {
                let _ = owner.await;
            }
            return Err(ApplicationError::AlreadyInitialized);
        }
        let (chat, runner) = PresenterRunner::new(
            preset,
            discovery,
            limits.presenter_updates.get(),
            limits.retained_finished.get(),
        );
        let presenter_task = Some(tokio::spawn(runner.run(presenter_stop.clone())));
        let settings_presenter = SettingsPresenter::new()?;
        let settings_owner = settings.owner();
        let settings_stop = CancellationToken::new();
        let settings_task = Some(tokio::spawn(settings.run(settings_stop.clone())));
        let server_stop = CancellationToken::new();
        let server_task = Some(tokio::spawn(server_lifecycle.run(server_stop.clone())));
        startup.committed = true;
        Ok(Self {
            api,
            characters,
            timeline,
            presenter: GuiPresenter {
                chat,
                settings: settings_presenter,
                characters: CharactersPresenter,
            },
            workers_stop,
            owners_stop,
            presenter_stop,
            workers,
            owners,
            presenter_task,
            settings_owner,
            settings_stop,
            settings_task,
            server,
            server_stop,
            server_task,
        })
    }

    pub fn presenter(&self) -> &GuiPresenter {
        &self.presenter
    }
    pub fn server(&self) -> &ServerHandle {
        &self.server
    }
    pub fn at(&self) -> crate::timeline::ContextAnchor {
        self.timeline
            .lock()
            .expect("timeline lock poisoned")
            .anchor()
    }
    pub fn at_event(
        &self,
        event: crate::timeline::EventId,
    ) -> Option<crate::timeline::ContextAnchor> {
        self.timeline
            .lock()
            .expect("timeline lock poisoned")
            .at_event(event)
    }
    pub fn character(&self, id: CharacterId) -> Option<CharacterHandle> {
        self.characters.get(id)
    }
    pub fn timeline(&self) -> Vec<TimelineEvent> {
        self.timeline
            .lock()
            .expect("timeline lock poisoned")
            .events()
    }
    pub fn active_requests(&self) -> usize {
        self.api.registry.active_count()
    }

    pub async fn shutdown(mut self) -> Result<(), ApplicationError> {
        let mut failure = None;
        self.server_stop.cancel();
        if let Some(task) = self.server_task.take() {
            match task.await {
                Ok(Ok(())) => {}
                Ok(Err(error)) => failure = Some(ApplicationError::Server(error)),
                Err(error) => failure = Some(ApplicationError::Task(error.to_string())),
            }
        }
        self.api.close();
        self.workers_stop.cancel();
        for worker in self.workers.drain(..) {
            if let Err(error) = worker.await {
                failure = Some(ApplicationError::Task(error.to_string()));
            }
        }
        self.owners_stop.cancel();
        for owner in self.owners.drain(..) {
            if let Err(error) = owner.await {
                failure = Some(ApplicationError::Task(error.to_string()));
            }
        }
        self.presenter_stop.cancel();
        if let Some(task) = self.presenter_task.take()
            && let Err(error) = task.await
        {
            failure = Some(ApplicationError::Task(error.to_string()));
        }
        self.settings_owner.close();
        self.settings_stop.cancel();
        if let Some(task) = self.settings_task.take() {
            match task.await {
                Ok(Ok(())) => {}
                Ok(Err(error)) => failure = Some(ApplicationError::Settings(error)),
                Err(error) => failure = Some(ApplicationError::Task(error.to_string())),
            }
        }
        match failure {
            Some(error) => Err(error),
            None => Ok(()),
        }
    }
}

impl Drop for ApplicationLifecycle {
    fn drop(&mut self) {
        self.api.close();
        self.workers_stop.cancel();
        self.presenter_stop.cancel();
        self.server_stop.cancel();
        self.settings_owner.close();
        self.settings_stop.cancel();
        self.owners_stop.cancel();
    }
}

impl Lifecycle for ApplicationLifecycle {
    type Error = ApplicationError;
    async fn run(self, stop: CancellationToken) -> Result<(), Self::Error> {
        stop.cancelled().await;
        self.shutdown().await
    }
}
