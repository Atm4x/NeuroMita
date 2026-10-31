use std::sync::Arc;

use serde::{Deserialize, Serialize};

use super::GeminiTemplate;
use crate::{character::CharacterContext, generation::GenerationError, timeline::EventContent};

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(super) struct GenerateContent {
    system_instruction: Content,
    contents: Vec<Content>,
    generation_config: Config,
}

#[derive(Serialize, Deserialize)]
struct Content {
    #[serde(skip_serializing_if = "Option::is_none")]
    role: Option<String>,
    parts: Vec<Part>,
}

#[derive(Serialize, Deserialize)]
struct Part {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    text: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    thought: Option<bool>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Config {
    temperature: f32,
    max_output_tokens: u32,
    candidate_count: u32,
}

fn content(role: Option<&str>, text: &str) -> Content {
    Content {
        role: role.map(str::to_owned),
        parts: vec![Part {
            text: Some(text.to_owned()),
            thought: None,
        }],
    }
}

pub(super) fn encode(context: CharacterContext, template: &GeminiTemplate) -> GenerateContent {
    let mut contents = Vec::new();
    for event in context.history.events {
        let (role, text) = match event.content {
            EventContent::PlayerMessage { text } => ("user", text),
            EventContent::CharacterReply { text, .. } => ("model", text),
            EventContent::Observation { text }
            | EventContent::Reaction { text, .. }
            | EventContent::Initiation { text } => ("user", text),
        };
        contents.push(content(Some(role), &text));
    }
    contents.push(content(Some("user"), &context.current_input));
    GenerateContent {
        system_instruction: content(
            None,
            &format!(
                "{}\n{}\nПринятых ответов: {}.",
                context.description, context.prompt, context.state.accepted_replies
            ),
        ),
        contents,
        generation_config: Config {
            temperature: template.settings().temperature(),
            max_output_tokens: template.settings().max_output_tokens(),
            candidate_count: 1,
        },
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct GenerateResponse {
    #[serde(default)]
    candidates: Vec<Candidate>,
    prompt_feedback: Option<PromptFeedback>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Candidate {
    content: Option<Content>,
    finish_reason: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct PromptFeedback {
    block_reason: Option<String>,
}

pub(super) fn decode(bytes: &[u8]) -> Result<Arc<str>, GenerationError> {
    let response: GenerateResponse = serde_json::from_slice(bytes)
        .map_err(|_| GenerationError::Response("invalid Gemini JSON".into()))?;
    if response
        .prompt_feedback
        .and_then(|feedback| feedback.block_reason)
        .is_some()
    {
        return Err(GenerationError::Response(
            "Gemini blocked the prompt".into(),
        ));
    }
    if response.candidates.len() != 1 {
        return Err(GenerationError::Response(
            "expected exactly one candidate".into(),
        ));
    }
    let candidate = response
        .candidates
        .into_iter()
        .next()
        .expect("one candidate checked");
    if candidate.finish_reason.as_deref() != Some("STOP") {
        return Err(GenerationError::Response(format!(
            "generation did not finish successfully: {:?}",
            candidate.finish_reason
        )));
    }
    let content = candidate
        .content
        .ok_or_else(|| GenerationError::Response("candidate has no content".into()))?;
    let text: String = content
        .parts
        .into_iter()
        .filter(|part| part.thought != Some(true))
        .filter_map(|part| part.text)
        .collect();
    if text.trim().is_empty() {
        return Err(GenerationError::Response(
            "candidate has no answer text".into(),
        ));
    }
    Ok(Arc::from(text))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn reasoning_is_not_returned_as_answer() {
        let body = json!({"candidates":[{"content":{"parts":[{"text":"secret thought","thought":true},{"text":"answer"}]},"finishReason":"STOP"}]});
        assert_eq!(
            &*decode(&serde_json::to_vec(&body).unwrap()).unwrap(),
            "answer"
        );
    }

    #[test]
    fn blocked_truncated_and_empty_answers_are_errors() {
        for body in [
            json!({"promptFeedback":{"blockReason":"SAFETY"}}),
            json!({"candidates":[{"content":{"parts":[{"text":"partial"}]},"finishReason":"MAX_TOKENS"}]}),
            json!({"candidates":[{"content":{"parts":[{"text":"only thought","thought":true}]},"finishReason":"STOP"}]}),
            json!({"candidates":[]}),
            json!({"candidates":[{"finishReason":"STOP"}]}),
        ] {
            assert!(decode(&serde_json::to_vec(&body).unwrap()).is_err());
        }
        assert!(decode(b"not json").is_err());
    }
}
