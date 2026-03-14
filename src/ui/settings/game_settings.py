from ui.gui_templates import create_settings_section, create_section_header
from utils.translation_manager import t

def setup_game_controls(self, parent):
    create_section_header(parent, t("ui.settings.game_settings.title"))

    api_config = [
        {'label': t('ui.settings.game_settings.do_not_turn_on'),
         'type': 'text'},
        {'label': t('ui.settings.game_settings.use_new_api'), 'key': 'USE_NEW_API', 'type': 'checkbutton',
        'default_checkbutton': False,
        'tooltip': t('ui.settings.game_settings.use_new_api_help')},
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.game_settings.section_server"),
        api_config
    )

    dialogue_config = [
        {'label': t('ui.settings.game_settings.mita_dialogue_auto'), 'key': 'MITA_DIALOGUE_AUTO', 'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': t("ui.settings.game_settings.mita_dialogue_auto_help")},
        {'label': t('ui.settings.game_settings.limit_npc_conversation'), 'key': 'CC_Limit_mod', 'type': 'entry',
         'default': 100, 'tooltip': t('ui.settings.game_settings.limit_npc_conversation_help'),
         'depends_on':'MITA_DIALOGUE_OLD_ON'},
        {'label': t('ui.settings.game_settings.gamemaster_experimental'),
         'type': 'text'},
        {'label': t('ui.settings.game_settings.gamemaster_enabled'), 'key': 'GM_ON', 'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': 'Помогает вести диалоги, в теории устраняя проблемы'},
        {'label': t('ui.settings.game_settings.gamemaster_task'), 'key': 'GM_SMALL_PROMPT', 'type': 'textarea', 'default': ""},
        {'label': t('ui.settings.game_settings.gamemaster_intervene'), 'key': 'GM_REPEAT',
         'type': 'entry',
         'default': 2,
         'tooltip': t('ui.settings.game_settings.gamemaster_intervene_help')},
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.game_settings.section_dialogue"),
        dialogue_config
    )

    mod_config = [
        {'label': t('ui.settings.game_settings.action_menu'), 'key': 'ACTION_MENU', 'type': 'checkbutton',
        'default_checkbutton': True,
        'tooltip': t('ui.settings.game_settings.action_menu_help')},
        {'label': t('ui.settings.game_settings.mitas_selection_menu'), 'key': 'MITAS_MENU', 'type': 'checkbutton',
        'default_checkbutton': False,
        'tooltip': t('ui.settings.game_settings.mitas_selection_menu_help')},
        {'label': t('ui.settings.game_settings.ignore_requests'), 'key': 'IGNORE_GAME_REQUESTS', 'type': 'checkbutton',
        'default_checkbutton': False,
        'tooltip': t('ui.settings.game_settings.ignore_requests_help'),
        'widget_name': 'IGNORE_GAME_REQUESTS'},
        {'label': t('ui.settings.game_settings.blocking_level'), 'key': 'GAME_BLOCK_LEVEL', 'type': 'combobox',
        'options': ['Idle events', 'All events'],
        'default': 'Idle events',
        'depends_on': 'IGNORE_GAME_REQUESTS',
        'tooltip': t('ui.settings.game_settings.blocking_level_help')},
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.game_settings.section_mod"),
        mod_config
    )

    games_config = [
        {
            'label': t('ui.settings.game_settings.enable_games'),
            'key': 'ENABLE_GAMES',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'tooltip': t('ui.settings.game_settings.enable_games_help')
        },
        {
            'label': t('ui.settings.game_settings.allow_games_with_unity'),
            'key': 'ALLOW_GAMES_WHEN_CONNECTED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': t('ui.settings.game_settings.allow_games_with_unity_help')
        },
        {
            'label': t('ui.settings.game_settings.chess'),
            'key': 'ENABLE_GAME_CHESS',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': t('ui.settings.game_settings.chess_help')
        },
        {
            'label': t('ui.settings.game_settings.sea_battle'),
            'key': 'ENABLE_GAME_SEABATTLE',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': t('ui.settings.game_settings.sea_battle_help')
        },
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.game_settings.section_games"),
        games_config
    )