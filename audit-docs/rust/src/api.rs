use std::{
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock},
};

use tokio::sync::mpsc;

use crate::{
    character::{CharacterError, CharacterHandle, CharacterId, CharacterRegistry},
    request::{
        InitiateRequest, Message, ReactRequest, ReplyRequest, RequestDiscovery, RequestHandle,
        RequestId, RequestRegistry, SubmitError,
    },
};

static CHAT: OnceLock<Arc<ChatApiState>> = OnceLock::new();
static CHARACTERS: OnceLock<CharacterRegistry> = OnceLock::new();

pub struct CharacterApi;
impl CharacterApi {
    pub fn get(id: CharacterId) -> Result<CharacterHandle, CharacterError> {
        CHARACTERS
            .get()
            .and_then(|registry| registry.get(id))
            .ok_or(CharacterError::Unavailable)
    }
    pub(crate) fn install(registry: CharacterRegistry) -> Result<(), CharacterRegistry> {
        CHARACTERS.set(registry)
    }
}

pub struct ChatApi;

pub(crate) struct ChatApiState {
    accepting: Mutex<bool>,
    pub(crate) registry: Arc<RequestRegistry>,
    handlers: HashMap<CharacterId, mpsc::Sender<RequestId>>,
}

impl ChatApiState {
    pub(crate) fn new(
        registry: Arc<RequestRegistry>,
        handlers: HashMap<CharacterId, mpsc::Sender<RequestId>>,
    ) -> Self {
        Self {
            accepting: Mutex::new(true),
            registry,
            handlers,
        }
    }

    pub(crate) fn close(&self) {
        *self.accepting.lock().expect("admission mutex poisoned") = false;
        self.registry.cancel_all();
    }
}

impl ChatApi {
    pub(crate) fn is_initialized() -> bool {
        CHAT.get().is_some()
    }
    pub fn reply(request: ReplyRequest) -> Result<RequestHandle, SubmitError> {
        Self::send(request)
    }
    pub fn react(request: ReactRequest) -> Result<RequestHandle, SubmitError> {
        Self::send(request)
    }
    pub fn initiate(request: InitiateRequest) -> Result<RequestHandle, SubmitError> {
        Self::send(request)
    }
    pub fn send(request: impl Message + 'static) -> Result<RequestHandle, SubmitError> {
        let state = CHAT.get().ok_or(SubmitError::Uninitialized)?;
        let accepting = state.accepting.lock().expect("admission mutex poisoned");
        if !*accepting {
            return Err(SubmitError::Stopped);
        }
        let handler = state
            .handlers
            .get(&request.character_id())
            .ok_or(SubmitError::CharacterUnavailable)?;
        let permit = handler.try_reserve().map_err(|error| match error {
            mpsc::error::TrySendError::Full(_) => SubmitError::QueueFull,
            mpsc::error::TrySendError::Closed(_) => SubmitError::QueueClosed,
        })?;
        let handle = state.registry.register(Box::new(request));
        permit.send(handle.id());
        Ok(handle)
    }

    pub fn observe_requests() -> Result<RequestDiscovery, SubmitError> {
        let state = CHAT.get().ok_or(SubmitError::Uninitialized)?;
        if !*state.accepting.lock().expect("admission mutex poisoned") {
            return Err(SubmitError::Stopped);
        }
        Ok(state.registry.observe())
    }

    pub fn active_request(id: RequestId) -> Result<Option<RequestHandle>, SubmitError> {
        let state = CHAT.get().ok_or(SubmitError::Uninitialized)?;
        Ok(state.registry.get(id).map(|record| record.handle()))
    }

    pub fn trace(id: RequestId) -> Result<Option<Arc<crate::request::RequestTrace>>, SubmitError> {
        Ok(CHAT
            .get()
            .ok_or(SubmitError::Uninitialized)?
            .registry
            .trace(id))
    }
    pub(crate) fn install(state: Arc<ChatApiState>) -> Result<(), Arc<ChatApiState>> {
        CHAT.set(state)
    }
}
