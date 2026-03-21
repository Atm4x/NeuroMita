from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QComboBox, QSizePolicy, QLabel,
)
from PyQt6.QtCore import QSize, Qt
import qtawesome as qta

from ui.gui_templates import create_settings_section, create_section_header
from utils import getTranslationVariant as _
from core.events import get_event_bus, Events
from managers.settings_manager import CollapsibleSection

def setup_model_interaction_controls(self, parent):
    create_section_header(parent, _("Настройки взаимодействия с моделью", "Model Interaction Settings"))
    
    general_config = [
        {'label': _('Настройки сообщений', 'Message settings'), 'type': 'subsection'},
        {'label': _('Промты раздельно', 'Separated prompts'), 'key': 'SEPARATE_PROMPTS',
         'type': 'checkbutton', 'default_checkbutton': True},

        {'label': _('Лимит сообщений', 'Message limit'), 'key': 'MODEL_MESSAGE_LIMIT',
         'type': 'entry', 'default': 40,
         'tooltip': _('Сколько сообщений будет помнить мита', 'How much messages Mita will remember')},
        {'label': _('Сохранять утерянную историю ', 'Save lost history'),
         'key': 'GPT4FREE_LAST_ATTEMPT', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': _('Сохранять утерянную память ', 'Save lost memory'),
         'key': 'SAVE_MISSED_MEMORY', 'type': 'checkbutton', 'default_checkbutton': False},

        {'label': _('Кол-во попыток', 'Attempt count'), 'key': 'MODEL_MESSAGE_ATTEMPTS_COUNT',
         'type': 'entry', 'default': 3},
        {'label': _('Время между попытками', 'time between attempts'),
         'key': 'MODEL_MESSAGE_ATTEMPTS_TIME', 'type': 'entry', 'default': 0.20},
        {'label': _('Включить стриминговую передачу', 'Enable Streaming'), 'key': 'ENABLE_STREAMING',
         'type': 'checkbutton',
         'default_checkbutton': False},
        {'label': _('Использовать gpt4free последней попыткой ', 'Use gpt4free as last attempt'),
         'key': 'GPT4FREE_LAST_ATTEMPT', 'type': 'checkbutton', 'default_checkbutton': False},

        {'type': 'end'},

        {'label': _('Настройки ожидания', 'Waiting settings'), 'type': 'subsection'},
        {'label': _('Время ожидания текста (сек)', 'Text waiting time (sec)'),
         'key': 'TEXT_WAIT_TIME', 'type': 'entry', 'default': 40,
         'tooltip': _('время ожидания ответа', 'response waiting time')},
        {'label': _('Время ожидания звука (сек)', 'Voice waiting time (sec)'),
         'key': 'VOICE_WAIT_TIME', 'type': 'entry', 'default': 40,
         'tooltip': _('время ожидания озвучки', 'voice generation waiting time')},

        {'type': 'end'},

        {'label': _('Настройки генерации текста', 'Text Generation Settings'), 'type': 'subsection'},

        {'label': _('Макс. токенов в ответе', 'Max response tokens'),
        'key': 'MODEL_MAX_RESPONSE_TOKENS',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_MAX_RESPONSE_TOKENS',
        'toggle_default': self.settings.get('USE_MODEL_MAX_RESPONSE_TOKENS', True),
        'default': 2500,
        'validation': self.validate_positive_integer,
        'tooltip': _('Максимальное количество токенов в ответе модели',
                    'Maximum number of tokens in the model response')},

        {'label': _('Температура', 'Temperature'), 'key': 'MODEL_TEMPERATURE',
         'type': 'entry', 'default': 1.0, 'validation': self.validate_float_0_to_2,
         'tooltip': _('Креативность ответа (0.0 = строго, 2.0 = очень творчески)',
                      'Creativity of response (0.0 = strict, 2.0 = very creative)')},

        {'label': _('Top-K', 'Top-K'),
        'key': 'MODEL_TOP_K',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_TOP_K',
        'toggle_default': self.settings.get('USE_MODEL_TOP_K', True),
        'default': 0,
        'validation': self.validate_positive_integer_or_zero,
        'tooltip': _('Ограничивает выбор токенов K наиболее вероятными (0 = отключено)',
                    'Limits token selection to K most likely (0 = disabled)')},

        {'label': _('Top-P', 'Top-P'),
        'key': 'MODEL_TOP_P',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_TOP_P',
        'toggle_default': self.settings.get('USE_MODEL_TOP_P', True),
        'default': 1.0,
        'validation': self.validate_float_0_to_1,
        'tooltip': _('Ограничивает выбор токенов по кумулятивной вероятности (0.0-1.0)',
                    'Limits token selection by cumulative probability (0.0-1.0)')},

        {'label': _('Бюджет размышлений', 'Thinking budget'),
        'key': 'MODEL_THINKING_BUDGET',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_THINKING_BUDGET',
        'toggle_default': self.settings.get('USE_MODEL_THINKING_BUDGET', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': _('Параметр, влияющий на глубину "размышлений" модели (зависит от модели)',
                    'Parameter influencing the depth of model "thoughts" (model-dependent)')},

        {'label': _('Штраф присутствия', 'Presence penalty'),
        'key': 'MODEL_PRESENCE_PENALTY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_PRESENCE_PENALTY',
        'toggle_default': self.settings.get('USE_MODEL_PRESENCE_PENALTY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': _('Штраф за использование новых токенов (-2.0 = поощрять новые, 2.0 = сильно штрафовать)',
                    'Penalty for using new tokens (-2.0 = encourage new, 2.0 = strongly penalize)')},

        {'label': _('Штраф частоты', 'Frequency penalty'),
        'key': 'MODEL_FREQUENCY_PENALTY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_FREQUENCY_PENALTY',
        'toggle_default': self.settings.get('USE_MODEL_FREQUENCY_PENALTY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': _('Штраф за частоту использования токенов (-2.0 = поощрять повторение, 2.0 = сильно штрафовать)',
                    'Penalty for the frequency of token usage (-2.0 = encourage repetition, 2.0 = strongly penalize)')},

        {'label': _('Лог вероятности', 'Log probability'),
        'key': 'MODEL_LOG_PROBABILITY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_LOG_PROBABILITY',
        'toggle_default': self.settings.get('USE_MODEL_LOG_PROBABILITY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': _('Параметр, влияющий на логарифмическую вероятность выбора токенов (-2.0 = поощрять, 2.0 = штрафовать)',
                    'Parameter influencing the logarithmic probability of token selection (-2.0 = encourage, 2.0 = penalize)')},

        {'label': _('Вызов инструментов', 'Tools use'),
         'key': 'TOOLS_ON',
         'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': _(
             'Позволяет использовать инструменты такие как поиск в сети',
             'Allow using tools like seacrh')},
        {'label': _("Режим инструментов","Tools mode"), 'key': 'TOOLS_MODE', 'type': 'combobox',
         'options': ["native", "legacy"], 'default': "native", "depends_on": "TOOLS_ON",
         'tooltip': _('Native - использует вшитые возможности модели, legacy - добавляет промпт и ловит вызов вручную',
                    'Native - using buit-in tools, legacy - using own prompts and handler')},

        {'label': _('GOOGLE API KEY'), 'key': 'GOOGLE_API_KEY', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},
        {'label': _('GOOGLE CSE ID'), 'key': 'GOOGLE_CSE_ID', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},

        {'type': 'end'},
    ]

    create_settings_section(
        self,
        parent,
        _("Параметры генерации", "Generation Parameters"),
        general_config,
        icon_name='fa5s.cogs'
    )

    event_bus = get_event_bus()
    presets_meta = event_bus.emit_and_wait(Events.ApiPresets.GET_PRESET_LIST, timeout=1.0)

    # Collect all presets for dropdowns and backup lists
    all_custom_presets = []
    all_builtin_presets = []
    if presets_meta and presets_meta[0]:
        all_custom_presets = presets_meta[0].get('custom', []) or []
        all_builtin_presets = presets_meta[0].get('builtin', []) or []

    hc_provider_names = [_('Текущий', 'Current')]
    for preset in all_custom_presets:
        hc_provider_names.append(preset.name)

    react_provider_names = [_('Текущий', 'Current')]
    for preset in all_custom_presets:
        react_provider_names.append(preset.name)

    # --- Backup Presets Section ---
    _build_backup_presets_section(self, parent, all_custom_presets, all_builtin_presets)

    history_compression_config = [
        {'label': _('Сжимать историю при достижении лимита', 'Compress history on limit'),
         'key': 'ENABLE_HISTORY_COMPRESSION_ON_LIMIT', 'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': _('Включить автоматическое сжатие истории чата, когда количество сообщений превышает лимит.',
                      'Enable automatic chat history compression when message count exceeds a limit.')},
        {'label': _('Периодическое сжатие истории', 'Periodic history compression'),
         'key': 'ENABLE_HISTORY_COMPRESSION_PERIODIC', 'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': _('Включить автоматическое сжатие истории чата через заданные интервалы.',
                      'Enable automatic chat history compression at specified intervals.')},
        {'label': _('Интервал периодического сжатия (сообщения)', 'Periodic compression interval (messages)'),
         'key': 'HISTORY_COMPRESSION_PERIODIC_INTERVAL', 'type': 'entry',
         'default': 20, 'validation': self.validate_positive_integer,
         'tooltip': _('Количество сообщений, после которых будет произведено периодическое сжатие истории.',
                      'Number of messages after which periodic history compression will occur.')},
        {'label': _('Шаблон промпта для сжатия', 'Compression prompt template'),
         'key': 'HISTORY_COMPRESSION_PROMPT_TEMPLATE', 'type': 'entry',
         'default': "Prompts/System/compression_prompt.txt",
         'tooltip': _('Путь к файлу шаблона промпта, используемого для сжатия истории.',
                      'Path to the prompt template file used for history compression.')},
        {'label': _('Процент для сжатия', 'Percent to compress'),
         'key': 'HISTORY_COMPRESSION_MIN_PERCENT_TO_COMPRESS', 'type': 'entry',
         'default': 0.85, 'validation': self.validate_float_0_1,
         'tooltip': _('Минимальное количество сообщений в истории, необходимое для запуска процесса сжатия.',
                      'Minimum number of messages in history required to trigger compression.')},
        {'label': _('Цель вывода сжатой истории', 'Compressed history output target'),
         'key': 'HISTORY_COMPRESSION_OUTPUT_TARGET', 'type': 'combobox',
         'options': ['history','memory'],
         'default': "history",
         'tooltip': _('Куда помещать результат сжатия истории (например, "memory", "summary_message").',
                      'Where to place the compressed history output (e.g., "memory", "summary_message").')},
        {'label': _('Провайдер для сжатия', 'Provider for compression'),
         'key': 'HC_PROVIDER',
         'type': 'combobox',
         'options': hc_provider_names,
         'default': _('Текущий', 'Current')},
    ]
    
    create_settings_section(self, parent,
                           _("Сжатие истории", "History Compression"),
                           history_compression_config)
    
    react_settings_config = [
        {
            'label': _('Использовать реакции (react)', 'Use react events'),
            'key': 'REACT_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'tooltip': _(
                'Включить генерацию реакций на действия игрока (react-задачи). '
                'Отключение полностью блокирует вызовы модели для react.',
                'Enable generation of reactions to player actions (react tasks). '
                'Disabling completely blocks model calls for react.'
            )
        },
        {
            'label': _('Использовать реакции L1 (тихие)', 'Enable react L1 (silent)'),
            'key': 'REACT_L1_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': True,
            'depends_on': 'REACT_ENABLED',
            'tooltip': _(
                'Тихие реакции: мимика/поза/действия без ответа текстом.',
                'Silent reactions: face/pose/actions without text answer.'
            )
        },
        {
            'label': _('Провайдер для реакций L1', 'Provider for react L1'),
            'key': 'REACT_PROVIDER_L1',
            'type': 'combobox',
            'options': react_provider_names,
            'default': _('Текущий', 'Current'),
            'depends_on': 'REACT_L1_ENABLED',
            'tooltip': _(
                'Какой API-пресет использовать для тихих react-сообщений (L1).',
                'Which API preset to use for silent react messages (L1).'
            )
        },
        {
            'label': _('Использовать реакции L2 (с ответом)', 'Enable react L2 (with answer)'),
            'key': 'REACT_L2_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'REACT_ENABLED',
            'tooltip': _(
                'Реакции с полноценным ответом: текст + озвучка, запись в историю.',
                'Answer reactions: text + voiceover, saved to history.'
            )
        },
        {
            'label': _('Провайдер для реакций L2', 'Provider for react L2'),
            'key': 'REACT_PROVIDER_L2',
            'type': 'combobox',
            'options': react_provider_names,
            'default': _('Текущий', 'Current'),
            'depends_on': 'REACT_L2_ENABLED',
            'tooltip': _(
                'Какой API-пресет использовать для react-ответов (L2).',
                'Which API preset to use for answer-react messages (L2).'
            )
        },
    ]

    create_settings_section(
        self,
        parent,
        _("Настройки реакций", "React settings"),
        react_settings_config
    )

    token_settings_config = [
        {'label': _('Показывать информацию о токенах', 'Show Token Info'), 'key': 'SHOW_TOKEN_INFO',
         'type': 'checkbutton', 'default_checkbutton': True,
         'tooltip': _('Отображать количество токенов и ориентировочную стоимость в интерфейсе чата.',
                      'Display token count and approximate cost in the chat interface.')},
        {'label': _('Стоимость токена (вход, ₽)', 'Token Cost (input, ₽)'), 'key': 'TOKEN_COST_INPUT', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 0.000001, 'validation': self.validate_float_positive_or_zero,
         'tooltip': _('Стоимость одного токена для входных данных (например, 0.000001 ₽ за токен).',
                      'Cost of one token for input data (e.g., 0.000001 ₽ per token).')},
        {'label': _('Стоимость токена (выход, ₽)', 'Token Cost (output, ₽)'), 'key': 'TOKEN_COST_OUTPUT', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 0.000002, 'validation': self.validate_float_positive_or_zero,
         'tooltip': _('Стоимость одного токена для выходных данных (например, 0.000002 ₽ за токен).',
                      'Cost of one token for output data (e.g., 0.000002 ₽ per token).')},
        {'label': _('Максимальное количество токенов модели', 'Max Model Tokens'), 'key': 'MAX_MODEL_TOKENS', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 32000, 'validation': self.validate_positive_integer,
         'tooltip': _('Максимальное количество токенов, которое может обработать модель.',
                      'Maximum number of tokens the model can process.')},
    ]

    create_settings_section(self, parent,
                           _("Настройки токенов", "Token Settings"),
                           token_settings_config)

    command_processing_config = [
        {'label': _('Использовать обработку команд', 'Use command processing'), 'key': 'USE_COMMAND_REPLACER',
         'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': _('Включает замену команд в ответе модели на основе схожести.',
                                                    'Enables replacing commands in the model response based on similarity.')},
        {'label': _('Мин. порог схожести', 'Min similarity threshold'), 'key': 'MIN_SIMILARITY_THRESHOLD',
         'type': 'entry', 
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default': 0.40, 
         'validation': self.validate_float_0_to_1, 
         'tooltip': _('Минимальный порог схожести для замены команды (0.0-1.0).',
                      'Minimum similarity threshold for command replacement (0.0-1.0).')},
        {'label': _('Порог смены категории', 'Category switch threshold'), 'key': 'CATEGORY_SWITCH_THRESHOLD',
         'type': 'entry',
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default': 0.18,
         'validation': self.validate_float_0_to_1, 
         'tooltip': _('Дополнительный порог для переключения на другую категорию команд (0.0-1.0).',
                      'Additional threshold for switching to a different command category (0.0-1.0).')},
        {'label': _('Пропускать параметры с запятой', 'Skip comma parameters'), 'key': 'SKIP_COMMA_PARAMETERS',
         'type': 'checkbutton', 
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default_checkbutton': True, 
         'tooltip': _('Пропускать параметры, содержащие запятую, при замене.',
                                                   'Skip parameters containing commas during replacement.')},
    ]

    create_settings_section(self, parent,
                           _("Обработка команд", "Command Processing"),
                           command_processing_config)


def _build_backup_presets_section(gui, parent_layout, custom_presets, builtin_presets):
    """
    Builds a collapsible section with an ordered list of backup presets.
    Users can add presets from a dropdown, remove them, and reorder with up/down buttons.
    """
    section = CollapsibleSection(
        _("Резервные провайдеры", "Backup Providers"), gui, icon_name="fa5s.shield-alt"
    )
    parent_layout.addWidget(section)

    # Description label
    desc = QLabel(_(
        "Если основной провайдер не отвечает, система автоматически "
        "переключится на следующий из списка. Порядок определяет приоритет.",
        "If the primary provider fails, the system will automatically "
        "fall back to the next one in the list. Order determines priority."
    ))
    desc.setWordWrap(True)
    desc.setStyleSheet("color: #bfbfbf; font-size: 11px; margin-bottom: 4px;")
    section.add_widget(desc)

    # All available presets (id -> name mapping)
    available_presets = {}
    for p in custom_presets:
        pid = getattr(p, "id", None)
        name = getattr(p, "name", "")
        if isinstance(pid, int) and pid > 0:
            available_presets[pid] = str(name)
    for p in builtin_presets:
        pid = getattr(p, "id", None)
        name = getattr(p, "name", "")
        if isinstance(pid, int) and pid > 0:
            available_presets[pid] = str(name)

    # --- List + buttons ---
    list_container = QWidget()
    list_layout = QHBoxLayout(list_container)
    list_layout.setContentsMargins(0, 0, 0, 0)
    list_layout.setSpacing(8)

    backup_list = QListWidget()
    backup_list.setObjectName("BackupPresetsList")
    backup_list.setFixedHeight(120)
    backup_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    list_layout.addWidget(backup_list, 1)

    btn_layout = QVBoxLayout()
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.setSpacing(4)

    move_up_btn = QPushButton()
    move_up_btn.setIcon(qta.icon('fa5s.arrow-up', color='#e6e6e6'))
    move_up_btn.setToolTip(_("Вверх", "Move up"))
    move_up_btn.setFixedSize(28, 28)
    move_up_btn.setIconSize(QSize(14, 14))

    move_down_btn = QPushButton()
    move_down_btn.setIcon(qta.icon('fa5s.arrow-down', color='#e6e6e6'))
    move_down_btn.setToolTip(_("Вниз", "Move down"))
    move_down_btn.setFixedSize(28, 28)
    move_down_btn.setIconSize(QSize(14, 14))

    remove_btn = QPushButton()
    remove_btn.setIcon(qta.icon('fa5s.minus', color='#e6e6e6'))
    remove_btn.setToolTip(_("Удалить", "Remove"))
    remove_btn.setFixedSize(28, 28)
    remove_btn.setIconSize(QSize(14, 14))

    btn_layout.addWidget(move_up_btn)
    btn_layout.addWidget(move_down_btn)
    btn_layout.addWidget(remove_btn)
    btn_layout.addStretch()
    list_layout.addLayout(btn_layout)

    section.add_widget(list_container)

    # --- Add preset row ---
    add_row = QWidget()
    add_layout = QHBoxLayout(add_row)
    add_layout.setContentsMargins(0, 4, 0, 0)
    add_layout.setSpacing(6)

    add_combo = QComboBox()
    add_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    add_combo.addItem(_("Выберите пресет...", "Select preset..."), None)
    for pid, name in sorted(available_presets.items(), key=lambda x: x[1]):
        add_combo.addItem(name, pid)

    add_btn = QPushButton()
    add_btn.setIcon(qta.icon('fa5s.plus', color='#e6e6e6'))
    add_btn.setToolTip(_("Добавить", "Add"))
    add_btn.setFixedSize(28, 28)
    add_btn.setIconSize(QSize(14, 14))

    add_layout.addWidget(add_combo, 1)
    add_layout.addWidget(add_btn)
    section.add_widget(add_row)

    # --- Setting key ---
    setting_key = "BACKUP_PRESET_IDS"

    def _get_current_ids():
        """Read the ordered list from the list widget."""
        ids = []
        for i in range(backup_list.count()):
            item = backup_list.item(i)
            pid = item.data(Qt.ItemDataRole.UserRole)
            if pid is not None:
                ids.append(int(pid))
        return ids

    def _save():
        """Persist the current list to settings."""
        ids = _get_current_ids()
        gui.settings[setting_key] = ids
        from managers.settings_manager import SettingsManager
        SettingsManager.set(setting_key, ids)

    def _load():
        """Load saved backup preset IDs into the list widget."""
        backup_list.clear()
        saved = gui.settings.get(setting_key, [])
        if not isinstance(saved, list):
            saved = []
        for pid in saved:
            try:
                pid = int(pid)
            except (ValueError, TypeError):
                continue
            name = available_presets.get(pid, f"Preset #{pid}")
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            backup_list.addItem(item)

    def _add_preset():
        pid = add_combo.currentData()
        if pid is None:
            return
        # Don't add duplicates
        current_ids = _get_current_ids()
        if int(pid) in current_ids:
            return
        name = available_presets.get(int(pid), f"Preset #{pid}")
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, int(pid))
        backup_list.addItem(item)
        add_combo.setCurrentIndex(0)
        _save()

    def _remove_preset():
        row = backup_list.currentRow()
        if row >= 0:
            backup_list.takeItem(row)
            _save()

    def _move_up():
        row = backup_list.currentRow()
        if row <= 0:
            return
        item = backup_list.takeItem(row)
        backup_list.insertItem(row - 1, item)
        backup_list.setCurrentRow(row - 1)
        _save()

    def _move_down():
        row = backup_list.currentRow()
        if row < 0 or row >= backup_list.count() - 1:
            return
        item = backup_list.takeItem(row)
        backup_list.insertItem(row + 1, item)
        backup_list.setCurrentRow(row + 1)
        _save()

    # Wire signals
    add_btn.clicked.connect(_add_preset)
    remove_btn.clicked.connect(_remove_preset)
    move_up_btn.clicked.connect(_move_up)
    move_down_btn.clicked.connect(_move_down)

    # Initial load
    _load()