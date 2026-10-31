use std::sync::Arc;

use tokio::sync::watch;

use crate::settings::{
    AppSettings, SettingsApi, SettingsError, SettingsSnapshot, VoiceSettings, Volume,
};

pub struct BoundProperty<T> {
    source: watch::Receiver<Arc<SettingsSnapshot>>,
    project: fn(&AppSettings) -> T,
    write: fn(T) -> Result<(), SettingsError>,
}

impl<T: Clone> Clone for BoundProperty<T> {
    fn clone(&self) -> Self {
        Self {
            source: self.source.clone(),
            project: self.project,
            write: self.write,
        }
    }
}

impl<T: Clone + PartialEq> BoundProperty<T> {
    fn new(
        project: fn(&AppSettings) -> T,
        write: fn(T) -> Result<(), SettingsError>,
    ) -> Result<Self, SettingsError> {
        Ok(Self {
            source: SettingsApi::observe()?,
            project,
            write,
        })
    }
    pub fn get(&self) -> T {
        (self.project)(&self.source.borrow().values)
    }
    pub fn set(&self, value: T) -> Result<(), SettingsError> {
        (self.write)(value)
    }
    pub fn observe(&self) -> PropertyObserver<T> {
        PropertyObserver {
            source: self.source.clone(),
            project: self.project,
            previous: None,
        }
    }
}

pub struct PropertyObserver<T> {
    source: watch::Receiver<Arc<SettingsSnapshot>>,
    project: fn(&AppSettings) -> T,
    previous: Option<T>,
}

impl<T: Clone + PartialEq> PropertyObserver<T> {
    pub async fn next(&mut self) -> Result<T, SettingsError> {
        loop {
            let value = {
                let snapshot = self.source.borrow_and_update();
                if snapshot.closed {
                    return Err(SettingsError::Stopped);
                }
                (self.project)(&snapshot.values)
            };
            if self.previous.as_ref() != Some(&value) {
                self.previous = Some(value.clone());
                return Ok(value);
            }
            self.source
                .changed()
                .await
                .map_err(|_| SettingsError::Stopped)?;
        }
    }
}

pub struct VoiceSettingsPresenter {
    pub volume: BoundProperty<Volume>,
    pub in_launcher: BoundProperty<bool>,
    pub in_game: BoundProperty<bool>,
    pub voice: BoundProperty<String>,
}

pub struct SettingsPresenter {
    pub voice: VoiceSettingsPresenter,
}
impl SettingsPresenter {
    pub(crate) fn new() -> Result<Self, SettingsError> {
        Ok(Self {
            voice: VoiceSettingsPresenter {
                volume: BoundProperty::new(
                    |settings| settings.voice.volume,
                    |value| {
                        SettingsApi::edit::<VoiceSettings>(|section| section.volume = value)
                            .map(|_| ())
                    },
                )?,
                in_launcher: BoundProperty::new(
                    |settings| settings.voice.in_launcher,
                    |value| {
                        SettingsApi::edit::<VoiceSettings>(|section| section.in_launcher = value)
                            .map(|_| ())
                    },
                )?,
                in_game: BoundProperty::new(
                    |settings| settings.voice.in_game,
                    |value| {
                        SettingsApi::edit::<VoiceSettings>(|section| section.in_game = value)
                            .map(|_| ())
                    },
                )?,
                voice: BoundProperty::new(
                    |settings| settings.voice.voice.clone(),
                    |value| {
                        SettingsApi::edit::<VoiceSettings>(|section| section.voice = value)
                            .map(|_| ())
                    },
                )?,
            },
        })
    }
    pub fn snapshot(&self) -> Result<Arc<SettingsSnapshot>, SettingsError> {
        SettingsApi::snapshot_all()
    }
    pub fn observe(&self) -> Result<watch::Receiver<Arc<SettingsSnapshot>>, SettingsError> {
        SettingsApi::observe()
    }
}
