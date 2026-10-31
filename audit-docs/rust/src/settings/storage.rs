use std::{path::PathBuf, sync::Mutex};

use serde::{Deserialize, Serialize};

use super::{AppSettings, SettingsError};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StoredSettings {
    pub schema_version: u32,
    pub revision: u64,
    pub settings: AppSettings,
}

pub trait SettingsRepository: Send + Sync + 'static {
    fn load(&self) -> Result<StoredSettings, SettingsError>;
    fn save(&self, settings: &StoredSettings) -> Result<(), SettingsError>;
}

pub struct MemorySettingsRepository {
    value: Mutex<Option<StoredSettings>>,
}
impl MemorySettingsRepository {
    pub fn new() -> Self {
        Self {
            value: Mutex::new(None),
        }
    }
}
impl Default for MemorySettingsRepository {
    fn default() -> Self {
        Self::new()
    }
}
impl SettingsRepository for MemorySettingsRepository {
    fn load(&self) -> Result<StoredSettings, SettingsError> {
        self.value
            .lock()
            .expect("settings storage poisoned")
            .clone()
            .ok_or_else(|| SettingsError::Storage("no stored settings".into()))
    }
    fn save(&self, settings: &StoredSettings) -> Result<(), SettingsError> {
        *self.value.lock().expect("settings storage poisoned") = Some(settings.clone());
        Ok(())
    }
}

pub struct JsonSettingsRepository {
    path: PathBuf,
}
impl JsonSettingsRepository {
    pub fn new(path: PathBuf) -> Self {
        Self { path }
    }
}
impl SettingsRepository for JsonSettingsRepository {
    fn load(&self) -> Result<StoredSettings, SettingsError> {
        let bytes =
            std::fs::read(&self.path).map_err(|error| SettingsError::Storage(error.to_string()))?;
        let stored: StoredSettings = serde_json::from_slice(&bytes)
            .map_err(|error| SettingsError::Storage(error.to_string()))?;
        if stored.schema_version != 1 {
            return Err(SettingsError::Storage("unsupported settings schema".into()));
        }
        stored.settings.validate()?;
        Ok(stored)
    }
    fn save(&self, settings: &StoredSettings) -> Result<(), SettingsError> {
        use std::io::Write;
        let bytes = serde_json::to_vec_pretty(settings)
            .map_err(|error| SettingsError::Storage(error.to_string()))?;
        let temporary = self
            .path
            .with_extension(format!("{}.tmp", uuid::Uuid::new_v4()));
        let result = (|| {
            let mut file = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            file.write_all(&bytes)?;
            file.sync_all()?;
            std::fs::rename(&temporary, &self.path)
        })();
        if result.is_err() {
            let _ = std::fs::remove_file(&temporary);
        }
        result.map_err(|error| SettingsError::Storage(error.to_string()))
    }
}
