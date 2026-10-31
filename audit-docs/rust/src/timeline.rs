use std::sync::Arc;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::{
    character::CharacterId,
    request::{RequestId, TurnIntent},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct EventId(pub Uuid);

impl EventId {
    pub fn new() -> Self {
        Self(Uuid::new_v4())
    }
}
impl Default for EventId {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContextAnchor {
    pub branch_id: Uuid,
    pub through: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContextPosition {
    Latest,
    At(ContextAnchor),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EventContent {
    PlayerMessage {
        text: Arc<str>,
    },
    Observation {
        text: Arc<str>,
    },
    Reaction {
        text: Arc<str>,
        target: EventId,
    },
    Initiation {
        text: Arc<str>,
    },
    CharacterReply {
        text: Arc<str>,
        reply_to: EventId,
        context: ContextAnchor,
    },
}

#[derive(Debug, Clone)]
pub struct TimelineEvent {
    pub id: EventId,
    pub sequence: u64,
    pub observer: CharacterId,
    pub request_id: Option<RequestId>,
    pub content: EventContent,
}

#[derive(Debug, Clone)]
pub struct HistoryView {
    pub at: ContextAnchor,
    pub events: Vec<TimelineEvent>,
}

pub(crate) struct SessionTimeline {
    branch_id: Uuid,
    events: Vec<TimelineEvent>,
}

impl SessionTimeline {
    pub(crate) fn new() -> Self {
        Self {
            branch_id: Uuid::new_v4(),
            events: Vec::new(),
        }
    }
    pub(crate) fn anchor(&self) -> ContextAnchor {
        ContextAnchor {
            branch_id: self.branch_id,
            through: self.events.len() as u64,
        }
    }
    pub(crate) fn history(&self, character: CharacterId) -> HistoryView {
        HistoryView {
            at: self.anchor(),
            events: self
                .events
                .iter()
                .filter(|event| event.observer == character)
                .cloned()
                .collect(),
        }
    }
    pub(crate) fn history_at(
        &self,
        character: CharacterId,
        at: ContextAnchor,
    ) -> Result<HistoryView, String> {
        if at.branch_id != self.branch_id || at.through > self.events.len() as u64 {
            return Err("invalid timeline position".into());
        }
        Ok(HistoryView {
            at,
            events: self
                .events
                .iter()
                .filter(|event| event.observer == character && event.sequence <= at.through)
                .cloned()
                .collect(),
        })
    }
    pub(crate) fn observe(
        &mut self,
        character: CharacterId,
        id: EventId,
        text: Arc<str>,
    ) -> Result<EventId, String> {
        if self.events.iter().any(|event| event.id == id) {
            return Err("event already exists".into());
        }
        self.events.push(TimelineEvent {
            id,
            sequence: self.events.len() as u64 + 1,
            observer: character,
            request_id: None,
            content: EventContent::Observation { text },
        });
        Ok(id)
    }
    pub(crate) fn at_event(&self, id: EventId) -> Option<ContextAnchor> {
        self.events
            .iter()
            .find(|event| event.id == id)
            .map(|event| ContextAnchor {
                branch_id: self.branch_id,
                through: event.sequence,
            })
    }
    pub(crate) fn append_input(
        &mut self,
        character: CharacterId,
        request: RequestId,
        id: EventId,
        text: Arc<str>,
        intent: TurnIntent,
    ) -> Result<(), String> {
        if self.events.iter().any(|event| event.id == id) {
            return Err("input event already exists".into());
        }
        let content = match intent {
            TurnIntent::Reply => EventContent::PlayerMessage { text },
            TurnIntent::Initiate => EventContent::Initiation { text },
            TurnIntent::React(target) => {
                if !self
                    .events
                    .iter()
                    .any(|event| event.id == target && event.observer == character)
                {
                    return Err("reaction target is unknown to the character".into());
                }
                EventContent::Reaction { text, target }
            }
        };
        self.events.push(TimelineEvent {
            id,
            sequence: self.events.len() as u64 + 1,
            observer: character,
            request_id: Some(request),
            content,
        });
        Ok(())
    }
    pub(crate) fn append_reply(
        &mut self,
        character: CharacterId,
        request: RequestId,
        trigger: EventId,
        context: ContextAnchor,
        text: Arc<str>,
    ) -> Result<EventId, String> {
        if context.branch_id != self.branch_id || context.through > self.events.len() as u64 {
            return Err("context does not belong to the active timeline".into());
        }
        if !self.events.iter().any(|event| {
            event.id == trigger
                && event.observer == character
                && !matches!(event.content, EventContent::CharacterReply { .. })
        }) {
            return Err("reply target is not known to this character".into());
        }
        if self.events.iter().any(|event| {
            event.request_id == Some(request)
                && matches!(event.content, EventContent::CharacterReply { .. })
        }) {
            return Err("request result already accepted".into());
        }
        let id = EventId::new();
        self.events.push(TimelineEvent {
            id,
            sequence: self.events.len() as u64 + 1,
            observer: character,
            request_id: Some(request),
            content: EventContent::CharacterReply {
                text,
                reply_to: trigger,
                context,
            },
        });
        Ok(id)
    }
    pub(crate) fn events(&self) -> Vec<TimelineEvent> {
        self.events.clone()
    }
}
