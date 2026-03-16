from ui.gui_templates import create_settings_section, create_section_header
from utils.translation_manager import t

def setup_general_settings_controls(self, parent):
    create_section_header(parent, t("ui.settings.general.title"))

    privacy_config = [
        {'label': t('ui.settings.general.hide_private'),
         'key': 'HIDE_PRIVATE',
         'type': 'checkbutton',
         'default_checkbutton': True},
    ]
    create_settings_section(
        self,
        parent,
        t("ui.settings.general.privacy"),
        privacy_config,
        icon_name='fa5s.user-shield'
    )

    chat_settings_config = [
        {'label': t('ui.settings.general.chat_font_size'), 'key': 'CHAT_FONT_SIZE', 'type': 'entry',
         'default': 12, 'validation': self.validate_positive_integer,
         'tooltip': t('ui.settings.general.chat_font_size_help')},
        {'label': t('ui.settings.general.show_timestamps'), 'key': 'SHOW_CHAT_TIMESTAMPS',
         'type': 'checkbutton', 'default_checkbutton': False,
         'tooltip': t('ui.settings.general.show_timestamps_help')},
        {'label': t('ui.settings.general.hide_tags'), 'key': 'HIDE_CHAT_TAGS',
         'type': 'checkbutton', 'default_checkbutton': True,
         'tooltip': t('ui.settings.general.hide_tags_help')},
        {'label': t('ui.settings.general.show_reasoning'), 'key': 'SHOW_THINK_IN_GUI',
         'type': 'checkbutton', 'default_checkbutton': True}
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.general.chat_settings"),
        chat_settings_config,
        icon_name='fa5s.comments'
    )

    language_config = [
        {'label': 'Язык / Language', 'key': 'LANGUAGE', 'type': 'combobox',
         'options': ["RU", "EN"], 'default': "RU"},
        {'label': 'Перезапусти программу после смены!', 'type': 'text'},
        {'label': 'Restart program after change!', 'type': 'text'},
    ]

    create_settings_section(
        self, 
        parent,
        "Язык / Language",
        language_config,
        icon_name='fa5s.globe'
    )