use std::{
    collections::{HashMap, VecDeque},
    sync::{Arc, Mutex},
};

use thiserror::Error;
use tokio::sync::broadcast;

use super::*;

pub(crate) struct RequestRegistry {
    inner: Arc<RegistryInner>,
}

pub(crate) struct RegistryInner {
    records: Mutex<HashMap<RequestId, Arc<RequestRecord>>>,
    accepted: broadcast::Sender<RequestHandle>,
    traces: Mutex<VecDeque<Arc<RequestTrace>>>,
    trace_capacity: usize,
}

impl RegistryInner {
    pub(crate) fn complete(&self, record: &RequestRecord) {
        let mut records = self.records.lock().expect("registry mutex poisoned");
        if let Some(trace) = record.take_trace() {
            let mut traces = self.traces.lock().expect("trace mutex poisoned");
            if traces.len() == self.trace_capacity {
                traces.pop_front();
            }
            traces.push_back(trace);
        }
        records.remove(&record.snapshot().metadata.id);
    }
}

pub struct RequestDiscovery {
    pub active: Vec<RequestHandle>,
    accepted: broadcast::Receiver<RequestHandle>,
}

#[derive(Debug, Error)]
pub enum DiscoveryError {
    #[error(
        "request discovery lagged by {0} notifications; resubscribe to recover active requests"
    )]
    Lagged(u64),
    #[error("request discovery closed")]
    Closed,
}

impl RequestDiscovery {
    pub async fn next(&mut self) -> Result<RequestHandle, DiscoveryError> {
        self.accepted.recv().await.map_err(|error| match error {
            broadcast::error::RecvError::Lagged(count) => DiscoveryError::Lagged(count),
            broadcast::error::RecvError::Closed => DiscoveryError::Closed,
        })
    }
}

impl RequestRegistry {
    pub(crate) fn new(discovery_capacity: usize) -> Self {
        let (accepted, _) = broadcast::channel(discovery_capacity);
        Self {
            inner: Arc::new(RegistryInner {
                records: Mutex::new(HashMap::new()),
                accepted,
                traces: Mutex::new(VecDeque::new()),
                trace_capacity: discovery_capacity,
            }),
        }
    }

    pub(crate) fn register(&self, message: Box<dyn Message>) -> RequestHandle {
        let record = RequestRecord::new(message, Arc::downgrade(&self.inner));
        let handle = record.handle();
        let mut records = self.inner.records.lock().expect("registry mutex poisoned");
        records.insert(handle.id(), record);
        let _ = self.inner.accepted.send(handle.clone());
        handle
    }

    pub(crate) fn get(&self, id: RequestId) -> Option<Arc<RequestRecord>> {
        self.inner
            .records
            .lock()
            .expect("registry mutex poisoned")
            .get(&id)
            .cloned()
    }

    pub(crate) fn trace(&self, id: RequestId) -> Option<Arc<RequestTrace>> {
        let records = self.inner.records.lock().expect("registry mutex poisoned");
        if let Some(record) = records.get(&id) {
            return record.trace();
        }
        self.inner
            .traces
            .lock()
            .expect("trace mutex poisoned")
            .iter()
            .find(|trace| trace.metadata.id == id)
            .cloned()
    }
    pub(crate) fn observe(&self) -> RequestDiscovery {
        let records = self.inner.records.lock().expect("registry mutex poisoned");
        let accepted = self.inner.accepted.subscribe();
        let active = records
            .values()
            .filter(|record| !record.snapshot().state.is_terminal())
            .map(|record| record.handle())
            .collect();
        RequestDiscovery { active, accepted }
    }

    pub(crate) fn cancel_all(&self) {
        let handles: Vec<_> = self
            .inner
            .records
            .lock()
            .expect("registry mutex poisoned")
            .values()
            .map(|record| record.handle())
            .collect();
        for handle in handles {
            handle.cancel();
        }
    }

    pub(crate) fn active_count(&self) -> usize {
        self.inner
            .records
            .lock()
            .expect("registry mutex poisoned")
            .values()
            .filter(|record| !record.snapshot().state.is_terminal())
            .count()
    }
}
