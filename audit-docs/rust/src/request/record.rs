use std::sync::{Arc, Mutex, Weak};

use tokio::sync::watch;
use tokio_util::sync::CancellationToken;

use super::{registry::RegistryInner, *};

pub(crate) struct RequestRecord {
    inner: Mutex<Execution>,
    updates: watch::Sender<Arc<RequestSnapshot>>,
    pub(crate) cancellation: CancellationToken,
    registry: Weak<RegistryInner>,
}

struct Execution {
    snapshot: Arc<RequestSnapshot>,
    phase: EffectPhase,
    message: Option<Box<dyn Message>>,
    trace: Option<RequestTrace>,
    draft_text: Option<Arc<str>>,
}

#[derive(Clone)]
pub struct RequestHandle {
    pub(crate) record: Arc<RequestRecord>,
}

impl std::fmt::Debug for RequestHandle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("RequestHandle")
            .field("id", &self.id())
            .finish()
    }
}

impl RequestHandle {
    pub fn id(&self) -> RequestId {
        self.record.snapshot().metadata.id
    }
    pub fn snapshot(&self) -> Arc<RequestSnapshot> {
        self.record.snapshot()
    }
    pub fn cancel(&self) -> CancelResult {
        self.record.cancel()
    }
    pub fn observe(&self) -> RequestObserver {
        RequestObserver {
            updates: self.record.updates.subscribe(),
            initial: true,
            finished: false,
        }
    }
    pub async fn wait(&self) -> Result<Arc<RequestSnapshot>, ObserveError> {
        let mut observer = self.observe();
        while let Some(snapshot) = observer.next().await? {
            if snapshot.state.is_terminal() {
                return Ok(snapshot);
            }
        }
        Err(ObserveError::ClosedBeforeCompletion)
    }
}

pub struct RequestObserver {
    updates: watch::Receiver<Arc<RequestSnapshot>>,
    initial: bool,
    finished: bool,
}

impl RequestObserver {
    pub async fn next(&mut self) -> Result<Option<Arc<RequestSnapshot>>, ObserveError> {
        if self.finished {
            return Ok(None);
        }
        if !self.initial {
            self.updates
                .changed()
                .await
                .map_err(|_| ObserveError::ClosedBeforeCompletion)?;
        }
        self.initial = false;
        let snapshot = Arc::clone(&self.updates.borrow_and_update());
        self.finished = snapshot.state.is_terminal();
        Ok(Some(snapshot))
    }
}

impl RequestRecord {
    pub(crate) fn new(message: Box<dyn Message>, registry: Weak<RegistryInner>) -> Arc<Self> {
        let snapshot = Arc::new(RequestSnapshot {
            metadata: RequestMetadata {
                id: RequestId::new(),
                character_id: message.character_id(),
                source: message.source(),
                intent: message.intent(),
            },
            revision: 0,
            state: RequestState::Pending,
        });
        let (updates, _) = watch::channel(Arc::clone(&snapshot));
        let trace = RequestTrace {
            metadata: snapshot.metadata.clone(),
            input: message.input().clone(),
            preset_description: format!("{:?}", message.preset()),
            voice: message.voice().clone(),
            context: None,
            generated_text: None,
            transitions: vec![RequestTransition {
                revision: 0,
                phase: EffectPhase::Working,
                state: RequestState::Pending,
            }],
        };
        Arc::new(Self {
            inner: Mutex::new(Execution {
                snapshot,
                phase: EffectPhase::Working,
                message: Some(message),
                trace: Some(trace),
                draft_text: None,
            }),
            updates,
            cancellation: CancellationToken::new(),
            registry,
        })
    }

    pub(crate) fn handle(self: &Arc<Self>) -> RequestHandle {
        RequestHandle {
            record: Arc::clone(self),
        }
    }
    pub(crate) fn snapshot(&self) -> Arc<RequestSnapshot> {
        Arc::clone(&self.inner.lock().expect("request mutex poisoned").snapshot)
    }

    fn publish(&self, inner: &mut Execution, state: RequestState) {
        let snapshot = Arc::new(RequestSnapshot {
            metadata: inner.snapshot.metadata.clone(),
            revision: inner.snapshot.revision + 1,
            state,
        });
        inner.snapshot = Arc::clone(&snapshot);
        let phase = inner.phase;
        if let Some(trace) = &mut inner.trace {
            trace.transitions.push(RequestTransition {
                revision: snapshot.revision,
                phase,
                state: snapshot.state.clone(),
            });
        }
        self.updates.send_replace(snapshot);
    }

    fn retire(&self) {
        if let Some(registry) = self.registry.upgrade() {
            registry.complete(self);
        }
    }

    pub(crate) fn try_start(&self) -> Option<Box<dyn Message>> {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if !matches!(inner.snapshot.state, RequestState::Pending) {
            return None;
        }
        let message = inner.message.take()?;
        self.publish(
            &mut inner,
            RequestState::Processing(ProcessingStage::GeneratingText),
        );
        Some(message)
    }

    pub(crate) fn cancel(&self) -> CancelResult {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if inner.snapshot.state.is_terminal() {
            return CancelResult::AlreadyFinished;
        }
        if inner.phase == EffectPhase::Accepting {
            return CancelResult::TooLate;
        }
        self.cancellation.cancel();
        if matches!(inner.snapshot.state, RequestState::Pending) {
            inner.phase = EffectPhase::Discarded;
            inner.message.take();
            self.publish(&mut inner, RequestState::Cancelled);
            drop(inner);
            self.retire();
            CancelResult::Cancelled
        } else {
            CancelResult::Requested
        }
    }

    pub(crate) fn begin_accepting(&self) -> bool {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if inner.phase != EffectPhase::Working
            || inner.snapshot.state.is_terminal()
            || self.cancellation.is_cancelled()
        {
            return false;
        }
        inner.phase = EffectPhase::Accepting;
        let snapshot = Arc::clone(&inner.snapshot);
        if let Some(trace) = &mut inner.trace {
            trace.transitions.push(RequestTransition {
                revision: snapshot.revision,
                phase: EffectPhase::Accepting,
                state: snapshot.state.clone(),
            });
        }
        true
    }

    pub(crate) fn finish(&self, outcome: RequestOutcome) {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if inner.snapshot.state.is_terminal() {
            return;
        }
        let cancelled = inner.phase == EffectPhase::Working && self.cancellation.is_cancelled();
        inner.phase = if matches!(
            outcome,
            RequestOutcome::Success(_) | RequestOutcome::VoiceGenerationFailed { .. }
        ) {
            EffectPhase::Applied
        } else {
            EffectPhase::Discarded
        };
        let state = if cancelled {
            RequestState::Cancelled
        } else {
            RequestState::Finished(outcome)
        };
        self.publish(&mut inner, state);
        drop(inner);
        self.retire();
    }

    pub(crate) fn finish_cancelled(&self) {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if inner.snapshot.state.is_terminal() || inner.phase == EffectPhase::Accepting {
            return;
        }
        inner.phase = EffectPhase::Discarded;
        inner.message.take();
        self.publish(&mut inner, RequestState::Cancelled);
        drop(inner);
        self.retire();
    }

    pub(crate) fn prepared(&self, context: crate::character::CharacterContext) {
        if let Some(trace) = &mut self.inner.lock().expect("request mutex poisoned").trace {
            trace.context = Some(context);
        }
    }
    pub(crate) fn text_ready(&self, text: Arc<str>) {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        inner.draft_text = Some(Arc::clone(&text));
        if let Some(trace) = &mut inner.trace {
            trace.generated_text = Some(text);
        }
    }
    pub(crate) fn failure(&self, message: String) -> InternalFailure {
        InternalFailure {
            message: Arc::from(message),
            partial_text: self
                .inner
                .lock()
                .expect("request mutex poisoned")
                .draft_text
                .clone(),
        }
    }
    pub(crate) fn take_trace(&self) -> Option<Arc<RequestTrace>> {
        self.inner
            .lock()
            .expect("request mutex poisoned")
            .trace
            .take()
            .map(Arc::new)
    }
    pub(crate) fn trace(&self) -> Option<Arc<RequestTrace>> {
        self.inner
            .lock()
            .expect("request mutex poisoned")
            .trace
            .clone()
            .map(Arc::new)
    }
    pub(crate) fn generating_voice(&self, text: Arc<str>) -> bool {
        let mut inner = self.inner.lock().expect("request mutex poisoned");
        if inner.snapshot.state.is_terminal() || self.cancellation.is_cancelled() {
            return false;
        }
        self.publish(
            &mut inner,
            RequestState::Processing(ProcessingStage::GeneratingVoice { text }),
        );
        true
    }
}

#[cfg(test)]
mod tests {
    use std::{sync::Barrier, time::Duration};

    use super::*;
    use crate::{
        character::CharacterId,
        generation::{
            GenerationPreset, ProviderTemplate,
            gemini::{GeminiTemplate, GenerationSettings},
        },
    };

    fn request() -> ReplyRequest {
        let settings = GenerationSettings::new(0.7, 32, Duration::from_secs(1)).unwrap();
        let preset = GenerationPreset::new(ProviderTemplate::Gemini(
            GeminiTemplate::google("test-model", "test-key", settings).unwrap(),
        ));
        ReplyRequest::new(
            CharacterId::Mita,
            preset,
            UserInput::new("test".into()).unwrap(),
            RequestSource::Presenter,
        )
    }

    #[test]
    fn cancellation_and_acceptance_have_one_winner() {
        for _ in 0..64 {
            let registry = RequestRegistry::new(4);
            let handle = registry.register(Box::new(request()));
            let record = Arc::clone(&handle.record);
            assert!(record.try_start().is_some());
            let barrier = Barrier::new(2);
            let (accepted, cancelled) = std::thread::scope(|scope| {
                let accepting = scope.spawn(|| {
                    barrier.wait();
                    record.begin_accepting()
                });
                let cancelling = scope.spawn(|| {
                    barrier.wait();
                    handle.cancel()
                });
                (accepting.join().unwrap(), cancelling.join().unwrap())
            });
            if accepted {
                assert_eq!(cancelled, CancelResult::TooLate);
                assert!(!record.cancellation.is_cancelled());
                record.finish(RequestOutcome::InternalError(
                    Arc::<str>::from("simulated acceptance rejection").into(),
                ));
                assert!(matches!(handle.snapshot().state, RequestState::Finished(_)));
            } else {
                assert_eq!(cancelled, CancelResult::Requested);
                record.finish_cancelled();
                assert!(matches!(handle.snapshot().state, RequestState::Cancelled));
            }
            assert_eq!(registry.active_count(), 0);
        }
    }

    #[test]
    fn queued_cancel_prevents_start_and_keeps_terminal_handle() {
        let registry = RequestRegistry::new(4);
        let handle = registry.register(Box::new(request()));
        assert_eq!(handle.cancel(), CancelResult::Cancelled);
        assert!(handle.record.try_start().is_none());
        assert_eq!(registry.active_count(), 0);
        assert!(registry.get(handle.id()).is_none());
        assert!(matches!(handle.snapshot().state, RequestState::Cancelled));
    }
}
