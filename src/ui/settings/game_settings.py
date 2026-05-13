from ui.gui_templates import create_settings_section, create_section_header
from utils import getTranslationVariant as _

def setup_game_controls(self, parent):
    create_section_header(parent, _("Настройки игры", "Game Settings"))

    api_config = [
        {'label': _('НЕ НАЖИМАТЬ!', 'Do not turn this on!'),
         'type': 'text'},
        {'label': _('Использовать новый API', 'Use new API'), 'key': 'USE_NEW_API', 'type': 'checkbutton',
        'default_checkbutton': True,
        'tooltip': _('Использовать новую систему передачи данных с задачами', 'Use new task-based data transfer system')},
    ]

    create_settings_section(
        self,
        parent,
        _("Настройки сервера", "Server settings"),
        api_config
    )
    
    dialogue_config = [
        {'label': _('Диалоги мит автоматически', 'Mitas\'s dialogues automatically'), 'key': 'MITA_DIALOGUE_AUTO', 'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': _("Миты автоматическики говорят по порядку, без вызова команд","Mitas response by order, without using commands")},
        {'label': _('Лимит речей нпс %', 'Limit NPC conversation'), 'key': 'CC_Limit_mod', 'type': 'entry',
         'default': 100, 'tooltip': _('Сколько от кол-ва персонажей может отклоняться повтор речей нпс',
                                      'How long NPC can talk ignoring player'),'depends_on':'MITA_DIALOGUE_OLD_ON'},
        {'label': _('ГеймМастер - экспериментальная функция', 'GameMaster is experimental feature'),
         'type': 'text'},
        {'label': _('ГеймМастер включен', 'GameMaster is on'), 'key': 'GM_ON', 'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': 'Помогает вести диалоги, в теории устраняя проблемы'},
        {'label': _('Задача ГМу', 'GM task'), 'key': 'GM_SMALL_PROMPT', 'type': 'textarea', 'default': ""},
        {'label': _('ГеймМастер встревает каждые', 'GameMaster intervene each'), 'key': 'GM_REPEAT',
         'type': 'entry',
         'default': 2,
         'tooltip': _('Пример: 3 Означает, что через каждые две фразы ГМ напишет свое сообщение',
                      'Example: 3 means that after 2 phrases GM will write his message')},
    ]

    create_settings_section(
        self,
        parent,
        _("Настройки диалогов и GameMaster", "Dialogue and GameMaster Settings"),
        dialogue_config
    )

    gm_orchestrator_config = [
        {'label': _('Оркестратор GameMaster включён', 'GameMaster orchestrator enabled'),
         'key': 'GM_ENABLED', 'type': 'checkbutton', 'default_checkbutton': True,
         'tooltip': _('Включить новый Python-оркестратор ролей GameMaster',
                      'Enable new Python orchestrator for GameMaster roles')},
        {'label': _('Роль: Модератор (повторы, циклы)', 'Role: Moderator (repetition, loops)'),
         'key': 'GM_ROLE_MODERATOR', 'type': 'checkbutton', 'default_checkbutton': True,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Роль: Нарратор (атмосфера)', 'Role: Narrator (atmosphere)'),
         'key': 'GM_ROLE_NARRATOR', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Роль: Режиссёр (выбор оратора)', 'Role: Director (speaker selection)'),
         'key': 'GM_ROLE_DIRECTOR', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Роль: Тренер (советы митам)', 'Role: Coach (hints to mitas)'),
         'key': 'GM_ROLE_COACH', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Мин. интервал между вмешательствами, сек', 'Min cooldown between interventions, sec'),
         'key': 'GM_MIN_COOLDOWN_SEC', 'type': 'entry', 'default': 5.0,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Макс. вмешательств за сессию', 'Max interventions per session'),
         'key': 'GM_MAX_INTERVENTIONS_PER_SESSION', 'type': 'entry', 'default': 20,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Порог повторов (n-gram Jaccard)', 'Repetition threshold (n-gram Jaccard)'),
         'key': 'GM_REPETITION_THRESHOLD', 'type': 'entry', 'default': 0.7,
         'depends_on': 'GM_ROLE_MODERATOR'},
        {'label': _('Окно проверки на циклы (ходов)', 'Loop detection window (turns)'),
         'key': 'GM_LOOP_WINDOW', 'type': 'entry', 'default': 6,
         'depends_on': 'GM_ROLE_MODERATOR'},
        {'label': _('Порог схожести для циклов', 'Loop similarity threshold'),
         'key': 'GM_LOOP_SIMILARITY', 'type': 'entry', 'default': 0.6,
         'depends_on': 'GM_ROLE_MODERATOR'},
        {'label': _('Таймаут паузы для нарратора, сек', 'Pause timeout for narrator, sec'),
         'key': 'GM_PAUSE_TIMEOUT_SEC', 'type': 'entry', 'default': 30.0,
         'depends_on': 'GM_ROLE_NARRATOR'},
        {'label': _('Нарратор каждые N ходов', 'Narrator every N turns'),
         'key': 'GM_NARRATOR_EVERY', 'type': 'entry', 'default': 5,
         'depends_on': 'GM_ROLE_NARRATOR'},
        {'label': _('Использовать отдельный пресет LLM для GM', 'Use separate LLM preset for GM'),
         'key': 'GM_USE_SEPARATE_MODEL', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ENABLED'},
        {'label': _('ID пресета LLM для GM', 'GM LLM preset ID'),
         'key': 'GM_MODEL_PRESET_ID', 'type': 'entry', 'default': '',
         'depends_on': 'GM_USE_SEPARATE_MODEL'},
        {'label': _('RAG для GameMaster', 'RAG for GameMaster'),
         'key': 'GM_RAG_ENABLED', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ENABLED'},
        {'label': _('RAG top-K для GM', 'GM RAG top-K'),
         'key': 'GM_RAG_TOP_K', 'type': 'entry', 'default': 3,
         'depends_on': 'GM_RAG_ENABLED'},
        {'label': _('Показывать нарратив GM в UI', 'Show GM narration in UI'),
         'key': 'GM_SHOW_NARRATION', 'type': 'checkbutton', 'default_checkbutton': True,
         'depends_on': 'GM_ENABLED'},
        {'label': _('Объявлять следующего оратора', 'Announce next speaker'),
         'key': 'GM_ANNOUNCE_SPEAKER', 'type': 'checkbutton', 'default_checkbutton': True,
         'depends_on': 'GM_ROLE_DIRECTOR'},
        {'label': _('Подсказки Coach видны игроку', 'Coach hints visible to player'),
         'key': 'GM_COACH_VISIBLE_TO_PLAYER', 'type': 'checkbutton', 'default_checkbutton': False,
         'depends_on': 'GM_ROLE_COACH'},
    ]

    create_settings_section(
        self,
        parent,
        _("GameMaster — расширенные роли", "GameMaster — advanced roles"),
        gm_orchestrator_config
    )

    mita_chain_config = [
        {'label': _('Режим цепочки реплик мит', 'Mita chain mode'),
         'key': 'MITADIALOGUE_CHAIN_MODE', 'type': 'combobox',
         'options': ['immediate', 'adaptive', 'wait_display'],
         'default': 'adaptive',
         'tooltip': _('immediate — без пауз; adaptive — ждём окно прерывания; wait_display — ждём сигнал из Unity',
                      'immediate — no pauses; adaptive — wait interrupt window; wait_display — wait Unity signal')},
        {'label': _('Окно прерывания цепочки, сек', 'Chain interrupt window, sec'),
         'key': 'MITADIALOGUE_INTERRUPT_WINDOW_SEC', 'type': 'entry', 'default': 3.0},
        {'label': _('Макс. ходов мит без игрока', 'Max NPC turns without player'),
         'key': 'MITADIALOGUE_MAX_AUTO_TURNS', 'type': 'entry', 'default': 3},
    ]

    create_settings_section(
        self,
        parent,
        _("Цепочки реплик мит", "Mita chain settings"),
        mita_chain_config
    )
    
    mod_config = [
        {'label': _('Меню действий', 'Action menu'), 'key': 'ACTION_MENU', 'type': 'checkbutton', 
        'default_checkbutton': True,
        'tooltip': _('Показывать меню действий в игре (Y)', 'Show action menu in game (Y)')},
        {'label': _('Меню выбора Мит', 'Mitas selection menu'), 'key': 'MITAS_MENU', 'type': 'checkbutton', 
        'default_checkbutton': False,
        'tooltip': _('Показывать меню выбора персонажей Мит в игре', 'Show Mitas character selection menu in game')},
        {'label': _('Дерево иерархии мира (устарело)', 'World hierarchy tree (outdated)'), 'key': 'WORLD_HIERARCHY_TREE', 'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': _('Нейронка будет знать какие объекты есть в радиусе и расстояние до них. Функция устарела.',
                      'The neural network will know which objects are in range and the distance to them. This feature is outdated.')},
        {'label': _('Игнорировать запросы', 'Ignore requests'), 'key': 'IGNORE_GAME_REQUESTS', 'type': 'checkbutton',
        'default_checkbutton': False,
        'tooltip': _('Блокировать запросы из игры', 'Block requests from the game'),
        'widget_name': 'IGNORE_GAME_REQUESTS'},
        {'label': _('Уровень блокировки', 'Blocking level'), 'key': 'GAME_BLOCK_LEVEL', 'type': 'combobox',
        'options': ['Idle events', 'All events'],
        'default': 'Idle events',
        'depends_on': 'IGNORE_GAME_REQUESTS',
        'tooltip': _('Idle events - блокирует запросы от таймера молчания, All events - блокирует все запросы с внутриигровых событий',
                    'Idle events - blocks idle timer requests, All events - blocks all in-game event requests')},
    ]
    
    create_settings_section(
        self,
        parent,
        _("Настройки мода", "Mod Settings"),
        mod_config
    )

    games_config = [
        {
            'label': _('Включить игры', 'Enable games'),
            'key': 'ENABLE_GAMES',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'tooltip': _('Глобально разрешает запуск встроенных игр (шахматы, морской бой).',
                         'Globally allows launching built-in games (Chess, Sea Battle).')
        },
        {
            'label': _('Разрешить запуск игр при подключенном Unity', 'Allow games when Unity is connected'),
            'key': 'ALLOW_GAMES_WHEN_CONNECTED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': _('Если ВЫКЛ и Unity подключен к серверу, игры не будут запускаться.',
                         'If OFF and Unity client is connected, games will not be launched.')
        },
        {
            'label': _('Шахматы', 'Chess'),
            'key': 'ENABLE_GAME_CHESS',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': _('Разрешить игру "Шахматы".', 'Allow "Chess" game.')
        },
        {
            'label': _('Морской бой', 'Sea Battle'),
            'key': 'ENABLE_GAME_SEABATTLE',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'ENABLE_GAMES',
            'tooltip': _('Разрешить игру "Морской бой".', 'Allow "Sea Battle" game.')
        },
    ]

    create_settings_section(
        self,
        parent,
        _("Игры", "Games"),
        games_config
    )
