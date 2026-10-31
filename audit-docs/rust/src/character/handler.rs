use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

use thiserror::Error;
use tokio::{
    sync::{mpsc, oneshot},
    task::JoinHandle,
};
use tokio_util::sync::CancellationToken;

use super::{
    CharacterContext, CharacterId, CharacterState, CharacterView, ResponseEffect, model::Character,
};
use crate::{
    request::{AcceptedResponse, RequestId, TurnIntent, UserInput},
    timeline::{ContextAnchor, ContextPosition, EventContent, EventId, SessionTimeline},
    voice::AudioArtifact,
};

#[derive(Debug, Clone, Error)]
pub enum CharacterError {
    #[error("character owner is unavailable")]
    Unavailable,
    #[error("character state changed since context preparation")]
    StaleState,
    #[error("character operation failed: {0}")]
    Internal(String),
}

#[derive(Debug, Clone, Copy)]
pub(crate) struct AcceptanceContext {
    pub anchor: ContextAnchor,
    pub trigger: EventId,
    pub state_revision: u64,
}

enum Command {
    Context {
        request: RequestId,
        input: UserInput,
        intent: TurnIntent,
        at: ContextPosition,
        reply: oneshot::Sender<Result<CharacterContext, CharacterError>>,
    },
    Accept {
        request: RequestId,
        context: AcceptanceContext,
        text: Arc<str>,
        audio: Option<AudioArtifact>,
        effects: Vec<ResponseEffect>,
        reply: oneshot::Sender<Result<AcceptedResponse, CharacterError>>,
    },
    State(oneshot::Sender<CharacterState>),
    View {
        at: ContextAnchor,
        reply: oneshot::Sender<Result<CharacterView, CharacterError>>,
    },
    Observe {
        input: UserInput,
        reply: oneshot::Sender<Result<EventId, CharacterError>>,
    },
}

#[derive(Clone)]
pub struct CharacterHandle {
    commands: mpsc::Sender<Command>,
}

impl CharacterHandle {
    pub async fn state(&self) -> Result<CharacterState, CharacterError> {
        let (reply, receive) = oneshot::channel();
        self.commands
            .send(Command::State(reply))
            .await
            .map_err(|_| CharacterError::Unavailable)?;
        receive.await.map_err(|_| CharacterError::Unavailable)
    }

    pub async fn get_context(&self, at: ContextAnchor) -> Result<CharacterView, CharacterError> {
        let (reply, receive) = oneshot::channel();
        self.commands
            .send(Command::View { at, reply })
            .await
            .map_err(|_| CharacterError::Unavailable)?;
        receive.await.map_err(|_| CharacterError::Unavailable)?
    }
    pub async fn observe(&self, input: UserInput) -> Result<EventId, CharacterError> {
        let (reply, receive) = oneshot::channel();
        self.commands
            .send(Command::Observe { input, reply })
            .await
            .map_err(|_| CharacterError::Unavailable)?;
        receive.await.map_err(|_| CharacterError::Unavailable)?
    }
    pub(crate) async fn prepare(
        &self,
        request: RequestId,
        input: UserInput,
        intent: TurnIntent,
        at: ContextPosition,
    ) -> Result<CharacterContext, CharacterError> {
        let (reply, receive) = oneshot::channel();
        self.commands
            .send(Command::Context {
                request,
                input,
                intent,
                at,
                reply,
            })
            .await
            .map_err(|_| CharacterError::Unavailable)?;
        receive.await.map_err(|_| CharacterError::Unavailable)?
    }

    pub(crate) async fn accept(
        &self,
        request: RequestId,
        context: AcceptanceContext,
        text: Arc<str>,
        audio: Option<AudioArtifact>,
        effects: Vec<ResponseEffect>,
    ) -> Result<AcceptedResponse, CharacterError> {
        let (reply, receive) = oneshot::channel();
        self.commands
            .send(Command::Accept {
                request,
                context,
                text,
                audio,
                effects,
                reply,
            })
            .await
            .map_err(|_| CharacterError::Unavailable)?;
        receive.await.map_err(|_| CharacterError::Unavailable)?
    }
}

#[derive(Clone)]
pub(crate) struct CharacterRegistry {
    handles: HashMap<CharacterId, CharacterHandle>,
}

impl CharacterRegistry {
    pub(crate) fn spawn(
        timeline: Arc<Mutex<SessionTimeline>>,
        stop: CancellationToken,
        capacity: usize,
    ) -> (Self, Vec<JoinHandle<()>>) {
        let mut handles = HashMap::new();
        let mut tasks = Vec::new();
        for id in CharacterId::ALL {
            let (send, receive) = mpsc::channel(capacity);
            let handler = CharacterHandler {
                character: Character::create(id),
                timeline: Arc::clone(&timeline),
            };
            handles.insert(id, CharacterHandle { commands: send });
            tasks.push(tokio::spawn(handler.run(receive, stop.clone())));
        }
        (Self { handles }, tasks)
    }

    pub(crate) fn get(&self, id: CharacterId) -> Option<CharacterHandle> {
        self.handles.get(&id).cloned()
    }
}

struct CharacterHandler {
    character: Character,
    timeline: Arc<Mutex<SessionTimeline>>,
}

impl CharacterHandler {
    async fn run(mut self, mut commands: mpsc::Receiver<Command>, stop: CancellationToken) {
        loop {
            let command = tokio::select! {
                biased;
                _ = stop.cancelled() => break,
                command = commands.recv() => match command { Some(command) => command, None => break },
            };
            match command {
                Command::Context {
                    request,
                    input,
                    intent,
                    at,
                    reply,
                } => {
                    let _ = reply.send(self.context(request, input, intent, at));
                }
                Command::Accept {
                    request,
                    context,
                    text,
                    audio,
                    effects,
                    reply,
                } => {
                    let _ = reply.send(self.accept(request, context, text, audio, effects));
                }
                Command::State(reply) => {
                    let _ = reply.send(self.character.state.clone());
                }
                Command::View { at, reply } => {
                    let _ = reply.send(self.view(at));
                }
                Command::Observe { input, reply } => {
                    let result = self
                        .timeline
                        .lock()
                        .map_err(|_| CharacterError::Internal("timeline lock poisoned".into()))
                        .and_then(|mut timeline| {
                            timeline
                                .observe(
                                    self.character.id,
                                    input.event_id(),
                                    Arc::clone(input.text()),
                                )
                                .map_err(CharacterError::Internal)
                        });
                    let _ = reply.send(result);
                }
            }
        }
    }

    fn context(
        &self,
        request: RequestId,
        input: UserInput,
        intent: TurnIntent,
        at: ContextPosition,
    ) -> Result<CharacterContext, CharacterError> {
        let mut timeline = self
            .timeline
            .lock()
            .map_err(|_| CharacterError::Internal("timeline lock poisoned".into()))?;
        let history = match at {
            ContextPosition::Latest => timeline.history(self.character.id),
            ContextPosition::At(at) => timeline
                .history_at(self.character.id, at)
                .map_err(CharacterError::Internal)?,
        };
        let anchor = history.at;
        let state = historical_state(&history);
        timeline
            .append_input(
                self.character.id,
                request,
                input.event_id(),
                Arc::clone(input.text()),
                intent,
            )
            .map_err(CharacterError::Internal)?;
        Ok(CharacterContext {
            character_id: self.character.id,
            description: Arc::clone(&self.character.description),
            prompt: Arc::clone(&self.character.prompt),
            state,
            history,
            current_input: Arc::clone(input.text()),
            trigger: input.event_id(),
            anchor,
        })
    }

    fn accept(
        &mut self,
        request: RequestId,
        context: AcceptanceContext,
        text: Arc<str>,
        audio: Option<AudioArtifact>,
        effects: Vec<ResponseEffect>,
    ) -> Result<AcceptedResponse, CharacterError> {
        if context.state_revision != self.character.state.revision {
            return Err(CharacterError::StaleState);
        }
        if !matches!(effects.as_slice(), [ResponseEffect::RecordAcceptedReply]) {
            return Err(CharacterError::Internal(
                "invalid reply effect batch".into(),
            ));
        }
        let accepted_replies = self
            .character
            .state
            .accepted_replies
            .checked_add(1)
            .ok_or_else(|| CharacterError::Internal("reply counter overflow".into()))?;
        let revision = self
            .character
            .state
            .revision
            .checked_add(1)
            .ok_or_else(|| CharacterError::Internal("state revision overflow".into()))?;
        let mut timeline = self
            .timeline
            .lock()
            .map_err(|_| CharacterError::Internal("timeline lock poisoned".into()))?;
        let event_id = timeline
            .append_reply(
                self.character.id,
                request,
                context.trigger,
                context.anchor,
                Arc::clone(&text),
            )
            .map_err(CharacterError::Internal)?;
        self.character.state = CharacterState {
            accepted_replies,
            revision,
        };
        Ok(AcceptedResponse {
            text,
            event_id,
            context: context.anchor,
            audio,
        })
    }
    fn view(&self, at: ContextAnchor) -> Result<CharacterView, CharacterError> {
        let timeline = self
            .timeline
            .lock()
            .map_err(|_| CharacterError::Internal("timeline lock poisoned".into()))?;
        let history = timeline
            .history_at(self.character.id, at)
            .map_err(CharacterError::Internal)?;
        Ok(CharacterView {
            character_id: self.character.id,
            description: Arc::clone(&self.character.description),
            prompt: Arc::clone(&self.character.prompt),
            state: historical_state(&history),
            history,
        })
    }
}

fn historical_state(history: &crate::timeline::HistoryView) -> CharacterState {
    let count = history
        .events
        .iter()
        .filter(|event| matches!(event.content, EventContent::CharacterReply { .. }))
        .count() as u64;
    CharacterState {
        accepted_replies: count,
        revision: count,
    }
}
