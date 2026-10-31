use crate::{
    api::CharacterApi,
    character::{CharacterError, CharacterId, CharacterState, CharacterView},
    request::{InputError, UserInput},
    timeline::{ContextAnchor, EventId},
};

pub struct CharactersPresenter;
impl CharactersPresenter {
    pub fn available(&self) -> &'static [CharacterId] {
        &CharacterId::ALL
    }
    pub async fn state(&self, id: CharacterId) -> Result<CharacterState, CharacterError> {
        CharacterApi::get(id)?.state().await
    }
    pub async fn context(
        &self,
        id: CharacterId,
        at: ContextAnchor,
    ) -> Result<CharacterView, CharacterError> {
        CharacterApi::get(id)?.get_context(at).await
    }
    pub async fn observe(
        &self,
        id: CharacterId,
        input: UserInput,
    ) -> Result<EventId, CharacterError> {
        CharacterApi::get(id)?.observe(input).await
    }
    pub fn input(&self, text: String) -> Result<UserInput, InputError> {
        UserInput::new(text)
    }
}
