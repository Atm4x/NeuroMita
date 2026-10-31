mod characters;
mod chat;
mod settings;

pub use characters::CharactersPresenter;
pub(crate) use chat::PresenterRunner;
pub use chat::{ChatModel, ChatPresenter, PresenterError, RequestView};
pub use settings::{BoundProperty, PropertyObserver, SettingsPresenter, VoiceSettingsPresenter};

pub struct GuiPresenter {
    pub chat: ChatPresenter,
    pub settings: SettingsPresenter,
    pub characters: CharactersPresenter,
}
