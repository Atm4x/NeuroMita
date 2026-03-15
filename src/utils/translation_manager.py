import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class TranslationManager:
    """Singleton for managing application translations and language switching."""

    _instance: Optional["TranslationManager"] = None
    _translations: Dict[str, Dict[str, Any]] = {}
    _current_language: str = "RU"

    def __init__(self):
        pass

    @classmethod
    def initialize(cls, language: Optional[str] = None) -> None:
        """Initialize TranslationManager with specified language or default."""
        if cls._instance is None:
            cls._instance = cls()

        # If language not specified, try to load from SettingsManager
        if language is None:
            try:
                from managers.settings_manager import SettingsManager
                language = SettingsManager.get("LANGUAGE", "RU")
            except Exception:
                language = "RU"

        cls.set_language(language)

    @classmethod
    def set_language(cls, language: str) -> None:
        """Change the current language and reload translations."""
        if cls._instance is None:
            cls._instance = cls()

        old_language = cls._current_language
        cls._current_language = language.upper()

        # Force reload when language is explicitly changed
        cls._translations.pop(cls._current_language, None)
        cls._load_translations(cls._current_language)

        # Try to fall back to English if not available
        if not cls._translations.get(cls._current_language):
            cls._load_translations("EN")
            if not cls._translations.get("EN"):
                raise RuntimeError("Could not load any translations!")

    @classmethod
    def _load_translations(cls, language: str) -> None:
        """Load translation file for specified language."""
        if language in cls._translations:
            return  # Already loaded

        locales_dir = cls._get_locales_dir()
        translation_file = os.path.join(locales_dir, f"{language.lower()}.json")

        if not os.path.exists(translation_file):
            return

        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                cls._translations[language] = json.load(f)
        except Exception as e:
            print(f"Error loading translations for {language}: {e}")

    @staticmethod
    def _get_locales_dir() -> str:
        """Get the locales directory path, supporting both development and PyInstaller."""
        # Get the directory where utils is located
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to src directory
        src_dir = os.path.dirname(utils_dir)
        # locales directory
        locales_dir = os.path.join(src_dir, "locales")

        return locales_dir

    @classmethod
    def t(cls, key: str, **kwargs) -> str:
        """
        Get translated string by key.

        Args:
            key: Translation key path (e.g., "dialogs.ffmpeg.title")
            **kwargs: Variables for string interpolation (e.g., name="John")

        Returns:
            Translated string, or key itself if not found
        """
        if cls._instance is None:
            cls.initialize()

        # Get the translation
        translation = cls._get_translation(key)

        # If not found in current language, try English
        if translation is None and cls._current_language != "EN":
            cls._ensure_english_loaded()
            translation = cls._get_translation_from_language(key, "EN")

        # If still not found, return the key itself
        if translation is None:
            return key

        # Perform string interpolation if kwargs provided
        if kwargs:
            try:
                return translation.format(**kwargs)
            except KeyError as e:
                print(f"Missing interpolation variable in key '{key}': {e}")
                return translation

        return translation

    @classmethod
    def _get_translation(cls, key: str) -> Optional[str]:
        """Get translation from current language."""
        return cls._get_translation_from_language(key, cls._current_language)

    @classmethod
    def _get_translation_from_language(cls, key: str, language: str) -> Optional[str]:
        """Get translation from specified language."""
        if language not in cls._translations:
            cls._load_translations(language)

        translations = cls._translations.get(language, {})

        # Support nested keys like "dialogs.ffmpeg.title"
        keys = key.split(".")
        value = translations

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        # Return only if it's a string
        if isinstance(value, str):
            return value

        return None

    @classmethod
    def _ensure_english_loaded(cls) -> None:
        """Ensure English translations are loaded as fallback."""
        if "EN" not in cls._translations:
            cls._load_translations("EN")

    @classmethod
    def get_current_language(cls) -> str:
        """Get current language setting."""
        if cls._instance is None:
            cls.initialize()
        return cls._current_language

    @classmethod
    def get_available_languages(cls) -> list:
        """Get list of available languages."""
        locales_dir = cls._get_locales_dir()
        languages = []

        if os.path.exists(locales_dir):
            for filename in os.listdir(locales_dir):
                if filename.endswith(".json"):
                    lang = filename[:-5].upper()  # Remove .json and uppercase
                    languages.append(lang)

        return sorted(languages)


# Global translation function for convenience
def t(key: str, **kwargs) -> str:
    """Translate string by key path."""
    return TranslationManager.t(key, **kwargs)
