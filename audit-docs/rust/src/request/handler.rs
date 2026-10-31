use std::sync::Arc;

use tokio::sync::mpsc;
use tokio_util::sync::CancellationToken;

use super::*;
use crate::{
    character::{AcceptanceContext, CharacterHandle},
    generation::{GenerationRequest, ResponseGenerator},
    voice::{VoicePlan, VoiceProvider},
};

#[derive(Clone)]
pub(crate) struct MessageHandler {
    pub(crate) character: CharacterHandle,
    pub(crate) registry: Arc<RequestRegistry>,
    pub(crate) generator: Arc<ResponseGenerator>,
    pub(crate) voice: Arc<dyn VoiceProvider>,
}

impl MessageHandler {
    pub(crate) async fn run_queue(
        self,
        mut queue: mpsc::Receiver<RequestId>,
        stop: CancellationToken,
    ) {
        loop {
            let id = tokio::select! {
                biased;
                _ = stop.cancelled() => break,
                item = queue.recv() => match item { Some(id) => id, None => break },
            };
            let Some(record) = self.registry.get(id) else {
                continue;
            };
            let Some(message) = record.try_start() else {
                continue;
            };
            let handler = self.clone();
            let task = tokio::spawn(async move {
                let _guard = WorkGuard(Arc::clone(&record));
                handler.process(record, message).await;
            });
            let _ = task.await;
        }
        queue.close();
        while let Some(id) = queue.recv().await {
            if let Some(record) = self.registry.get(id) {
                record.cancel();
                record.finish_cancelled();
            }
        }
    }

    async fn process(&self, record: Arc<RequestRecord>, message: Box<dyn Message>) {
        let id = record.snapshot().metadata.id;
        let prepared = tokio::select! {
            biased;
            _ = record.cancellation.cancelled() => { record.finish_cancelled(); return; }
            context = self.character.prepare(id, message.input().clone(), message.intent(), message.at()) => context,
        };
        let context = match prepared {
            Ok(context) => context,
            Err(error) => {
                record.finish(RequestOutcome::InternalError(
                    record.failure(error.to_string()),
                ));
                return;
            }
        };
        let acceptance = AcceptanceContext {
            anchor: context.anchor,
            trigger: context.trigger,
            state_revision: context.state.revision,
        };
        record.prepared(context.clone());
        let request = GenerationRequest {
            context,
            preset: message.preset().clone(),
        };
        let generated = tokio::select! {
            biased;
            _ = record.cancellation.cancelled() => { record.finish_cancelled(); return; }
            response = self.generator.generate(request) => response,
        };
        let proposed = match generated {
            Ok(proposed) => proposed,
            Err(error) => {
                record.finish(RequestOutcome::TextGenerationFailed(error));
                return;
            }
        };
        let text = proposed.text;
        record.text_ready(Arc::clone(&text));
        let voice = match message.voice() {
            VoicePlan::Disabled => Ok(None),
            VoicePlan::Synthesize(options) => {
                if !record.generating_voice(Arc::clone(&text)) {
                    record.finish_cancelled();
                    return;
                }
                tokio::select! {
                    biased;
                    _ = record.cancellation.cancelled() => { record.finish_cancelled(); return; }
                    audio = self.voice.synthesize(Arc::clone(&text), options.clone()) => audio.map(Some),
                }
            }
        };
        let (audio, voice_error) = match voice {
            Ok(audio) => (audio, None),
            Err(error) => (None, Some(error)),
        };
        if !record.begin_accepting() {
            record.finish_cancelled();
            return;
        }
        let outcome = match self
            .character
            .accept(id, acceptance, text, audio, proposed.effects)
            .await
        {
            Ok(response) => match voice_error {
                Some(error) => RequestOutcome::VoiceGenerationFailed { response, error },
                None => RequestOutcome::Success(response),
            },
            Err(error) => RequestOutcome::InternalError(record.failure(error.to_string())),
        };
        record.finish(outcome);
    }
}

struct WorkGuard(Arc<RequestRecord>);

impl Drop for WorkGuard {
    fn drop(&mut self) {
        if !self.0.snapshot().state.is_terminal() {
            self.0.finish(RequestOutcome::InternalError(
                self.0.failure("request worker stopped unexpectedly".into()),
            ));
        }
    }
}
