use std::{fmt, sync::Arc};

use crate::timeline::{ContextAnchor, EventId, HistoryView};

#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize, serde::Deserialize,
)]
#[serde(rename_all = "kebab-case")]
pub enum CharacterId {
    Mita,
    KindMita,
}

impl CharacterId {
    pub const ALL: [Self; 2] = [Self::Mita, Self::KindMita];

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "mita" => Some(Self::Mita),
            "kind-mita" => Some(Self::KindMita),
            _ => None,
        }
    }
}

impl fmt::Display for CharacterId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Mita => "mita",
            Self::KindMita => "kind-mita",
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CharacterState {
    pub accepted_replies: u64,
    pub revision: u64,
}

pub(crate) struct Character {
    pub(super) id: CharacterId,
    pub(super) description: Arc<str>,
    pub(super) prompt: Arc<str>,
    pub(super) state: CharacterState,
}

impl Character {
    pub(super) fn create(id: CharacterId) -> Self {
        let (description, prompt) = match id {
            CharacterId::Mita => (
                "Мита — собеседница игрока.",
                "Отвечай от лица Миты. Учитывай только предоставленные тебе сведения и историю.",
            ),
            CharacterId::KindMita => (
                "Добрая Мита — внимательная и спокойная собеседница игрока.",
                "Отвечай от лица Доброй Миты. Учитывай только предоставленные тебе сведения и историю.",
            ),
        };
        Self {
            id,
            description: Arc::from(description),
            prompt: Arc::from(prompt),
            state: CharacterState {
                accepted_replies: 0,
                revision: 0,
            },
        }
    }
}

#[derive(Debug, Clone)]
pub struct CharacterContext {
    pub character_id: CharacterId,
    pub description: Arc<str>,
    pub prompt: Arc<str>,
    pub state: CharacterState,
    pub history: HistoryView,
    pub current_input: Arc<str>,
    pub trigger: EventId,
    pub anchor: ContextAnchor,
}

#[derive(Debug, Clone)]
pub struct CharacterView {
    pub character_id: CharacterId,
    pub description: Arc<str>,
    pub prompt: Arc<str>,
    pub state: CharacterState,
    pub history: HistoryView,
}

#[derive(Debug, Clone, Copy)]
pub enum ResponseEffect {
    RecordAcceptedReply,
}
