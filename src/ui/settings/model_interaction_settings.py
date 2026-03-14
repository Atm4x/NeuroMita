from ui.gui_templates import create_settings_section, create_section_header
from utils.translation_manager import t
from core.events import get_event_bus, Events

def setup_model_interaction_controls(self, parent):
    create_section_header(parent, t("ui.settings.model_interaction.title"))
    
    general_config = [
        {'label': t('ui.settings.model_interaction.message_settings'), 'type': 'subsection'},
        {'label': t('ui.settings.model_interaction.separated_prompts'), 'key': 'SEPARATE_PROMPTS',
         'type': 'checkbutton', 'default_checkbutton': True},

        {'label': t('ui.settings.model_interaction.message_limit'), 'key': 'MODEL_MESSAGE_LIMIT',
         'type': 'entry', 'default': 40,
         'tooltip': t('ui.settings.model_interaction.message_limit_help')},
        {'label': t('ui.settings.model_interaction.save_lost_history'),
         'key': 'GPT4FREE_LAST_ATTEMPT', 'type': 'checkbutton', 'default_checkbutton': False},
        {'label': t('ui.settings.model_interaction.save_lost_memory'),
         'key': 'SAVE_MISSED_MEMORY', 'type': 'checkbutton', 'default_checkbutton': False},

        {'label': t('ui.settings.model_interaction.attempt_count'), 'key': 'MODEL_MESSAGE_ATTEMPTS_COUNT',
         'type': 'entry', 'default': 3},
        {'label': t('ui.settings.model_interaction.attempt_time'),
         'key': 'MODEL_MESSAGE_ATTEMPTS_TIME', 'type': 'entry', 'default': 0.20},
        {'label': t('ui.settings.model_interaction.enable_streaming'), 'key': 'ENABLE_STREAMING',
         'type': 'checkbutton',
         'default_checkbutton': False},
        {'label': t('ui.settings.model_interaction.gpt4free_last'),
         'key': 'GPT4FREE_LAST_ATTEMPT', 'type': 'checkbutton', 'default_checkbutton': False},

        {'type': 'end'},

        {'label': t('ui.settings.model_interaction.waiting_settings'), 'type': 'subsection'},
        {'label': t('ui.settings.model_interaction.text_wait_time'),
         'key': 'TEXT_WAIT_TIME', 'type': 'entry', 'default': 40,
         'tooltip': t('ui.settings.model_interaction.text_wait_time_help')},
        {'label': t('ui.settings.model_interaction.voice_wait_time'),
         'key': 'VOICE_WAIT_TIME', 'type': 'entry', 'default': 40,
         'tooltip': t('ui.settings.model_interaction.voice_wait_time_help')},

        {'type': 'end'},

        {'label': t('ui.settings.model_interaction.text_generation'), 'type': 'subsection'},

        {'label': t('ui.settings.model_interaction.max_response_tokens'),
        'key': 'MODEL_MAX_RESPONSE_TOKENS',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_MAX_RESPONSE_TOKENS',
        'toggle_default': self.settings.get('USE_MODEL_MAX_RESPONSE_TOKENS', True),
        'default': 2500,
        'validation': self.validate_positive_integer,
        'tooltip': t('ui.settings.model_interaction.max_response_tokens_help')},

        {'label': t('ui.settings.model_interaction.temperature'), 'key': 'MODEL_TEMPERATURE',
         'type': 'entry', 'default': 1.0, 'validation': self.validate_float_0_to_2,
         'tooltip': t('ui.settings.model_interaction.temperature_help')},

        {'label': t('ui.settings.model_interaction.top_k'),
        'key': 'MODEL_TOP_K',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_TOP_K',
        'toggle_default': self.settings.get('USE_MODEL_TOP_K', True),
        'default': 0,
        'validation': self.validate_positive_integer_or_zero,
        'tooltip': t('ui.settings.model_interaction.top_k_help')},

        {'label': t('ui.settings.model_interaction.top_p'),
        'key': 'MODEL_TOP_P',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_TOP_P',
        'toggle_default': self.settings.get('USE_MODEL_TOP_P', True),
        'default': 1.0,
        'validation': self.validate_float_0_to_1,
        'tooltip': t('ui.settings.model_interaction.top_p_help')},

        {'label': t('ui.settings.model_interaction.thinking_budget'),
        'key': 'MODEL_THINKING_BUDGET',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_THINKING_BUDGET',
        'toggle_default': self.settings.get('USE_MODEL_THINKING_BUDGET', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': t('ui.settings.model_interaction.thinking_budget_help')},

        {'label': t('ui.settings.model_interaction.presence_penalty'),
        'key': 'MODEL_PRESENCE_PENALTY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_PRESENCE_PENALTY',
        'toggle_default': self.settings.get('USE_MODEL_PRESENCE_PENALTY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': t('ui.settings.model_interaction.presence_penalty_help')},

        {'label': t('ui.settings.model_interaction.frequency_penalty'),
        'key': 'MODEL_FREQUENCY_PENALTY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_FREQUENCY_PENALTY',
        'toggle_default': self.settings.get('USE_MODEL_FREQUENCY_PENALTY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': t('ui.settings.model_interaction.frequency_penalty_help')},

        {'label': t('ui.settings.model_interaction.log_probability'),
        'key': 'MODEL_LOG_PROBABILITY',
        'type': 'entry',
        'toggle_key': 'USE_MODEL_LOG_PROBABILITY',
        'toggle_default': self.settings.get('USE_MODEL_LOG_PROBABILITY', False),
        'default': 0.0,
        'validation': self.validate_float_minus2_to_2,
        'tooltip': t('ui.settings.model_interaction.log_probability_help')},

        {'label': t('ui.settings.model_interaction.tools_use'),
         'key': 'TOOLS_ON',
         'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': t('ui.settings.model_interaction.tools_use_help')},
        {'label': t("ui.settings.model_interaction.tools_mode"), 'key': 'TOOLS_MODE', 'type': 'combobox',
         'options': ["native", "legacy"], 'default': "native", "depends_on": "TOOLS_ON",
         'tooltip': t('ui.settings.model_interaction.tools_mode_help')},

        {'label': t('ui.settings.model_interaction.tools_use'), 'key': 'GOOGLE_API_KEY', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},
        {'label': t('ui.settings.model_interaction.tools_use'), 'key': 'GOOGLE_CSE_ID', 'type': 'entry',
         'default': "", 'hide': bool(self.settings.get("HIDE_PRIVATE"))},

        {'type': 'end'},
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.model_interaction.text_generation"),
        general_config,
        icon_name='fa5s.cogs'
    )

    event_bus = get_event_bus()
    presets_meta = event_bus.emit_and_wait(Events.ApiPresets.GET_PRESET_LIST, timeout=1.0)
    hc_provider_names = [t('ui.settings.model_interaction.current')]
    if presets_meta and presets_meta[0]:
        all_presets = presets_meta[0].get('custom', [])
        for preset in all_presets:
            hc_provider_names.append(preset.name)
    react_provider_names = [t('ui.settings.model_interaction.current')]
    if presets_meta and presets_meta[0]:
        all_presets = presets_meta[0].get('custom', [])
        for preset in all_presets:
            react_provider_names.append(preset.name)

    history_compression_config = [
        {'label': t('ui.settings.model_interaction.compress_on_limit'),
         'key': 'ENABLE_HISTORY_COMPRESSION_ON_LIMIT', 'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': t('ui.settings.model_interaction.compress_on_limit_help')},
        {'label': t('ui.settings.model_interaction.periodic_compression'),
         'key': 'ENABLE_HISTORY_COMPRESSION_PERIODIC', 'type': 'checkbutton',
         'default_checkbutton': False,
         'tooltip': t('ui.settings.model_interaction.periodic_compression_help')},
        {'label': t('ui.settings.model_interaction.compression_interval'),
         'key': 'HISTORY_COMPRESSION_PERIODIC_INTERVAL', 'type': 'entry',
         'default': 20, 'validation': self.validate_positive_integer,
         'tooltip': t('ui.settings.model_interaction.compression_interval_help')},
        {'label': t('ui.settings.model_interaction.compression_prompt_template'),
         'key': 'HISTORY_COMPRESSION_PROMPT_TEMPLATE', 'type': 'entry',
         'default': "Prompts/System/compression_prompt.txt",
         'tooltip': t('ui.settings.model_interaction.compression_prompt_template_help')},
        {'label': t('ui.settings.model_interaction.compression_percent'),
         'key': 'HISTORY_COMPRESSION_MIN_PERCENT_TO_COMPRESS', 'type': 'entry',
         'default': 0.85, 'validation': self.validate_float_0_1,
         'tooltip': t('ui.settings.model_interaction.compression_percent_help')},
        {'label': t('ui.settings.model_interaction.compression_output_target'),
         'key': 'HISTORY_COMPRESSION_OUTPUT_TARGET', 'type': 'combobox',
         'options': ['history','memory'],
         'default': "history",
         'tooltip': t('ui.settings.model_interaction.compression_output_target_help')},
        {'label': t('ui.settings.model_interaction.compression_provider'),
         'key': 'HC_PROVIDER',
         'type': 'combobox',
         'options': hc_provider_names,
         'default': t('ui.settings.model_interaction.current')},
    ]

    create_settings_section(self, parent,
                           t("ui.settings.model_interaction.history_compression"),
                           history_compression_config)

    react_settings_config = [
        {
            'label': t('ui.settings.model_interaction.use_react'),
            'key': 'REACT_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'tooltip': t('ui.settings.model_interaction.use_react_help')
        },
        {
            'label': t('ui.settings.model_interaction.react_l1_enabled'),
            'key': 'REACT_L1_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': True,
            'depends_on': 'REACT_ENABLED',
            'tooltip': t('ui.settings.model_interaction.react_l1_enabled_help')
        },
        {
            'label': t('ui.settings.model_interaction.react_l1_provider'),
            'key': 'REACT_PROVIDER_L1',
            'type': 'combobox',
            'options': react_provider_names,
            'default': t('ui.settings.model_interaction.current_provider'),
            'depends_on': 'REACT_L1_ENABLED',
            'tooltip': t('ui.settings.model_interaction.react_l1_provider_help')
        },
        {
            'label': t('ui.settings.model_interaction.react_l2_enabled'),
            'key': 'REACT_L2_ENABLED',
            'type': 'checkbutton',
            'default_checkbutton': False,
            'depends_on': 'REACT_ENABLED',
            'tooltip': t('ui.settings.model_interaction.react_l2_enabled_help')
        },
        {
            'label': t('ui.settings.model_interaction.react_l2_provider'),
            'key': 'REACT_PROVIDER_L2',
            'type': 'combobox',
            'options': react_provider_names,
            'default': t('ui.settings.model_interaction.current_provider'),
            'depends_on': 'REACT_L2_ENABLED',
            'tooltip': t('ui.settings.model_interaction.react_l2_provider_help')
        },
    ]

    create_settings_section(
        self,
        parent,
        t("ui.settings.model_interaction.react_settings"),
        react_settings_config
    )

    token_settings_config = [
        {'label': t('ui.settings.model_interaction.show_token_info'), 'key': 'SHOW_TOKEN_INFO',
         'type': 'checkbutton', 'default_checkbutton': True,
         'tooltip': t('ui.settings.model_interaction.show_token_info_help')},
        {'label': t('ui.settings.model_interaction.token_cost_input'), 'key': 'TOKEN_COST_INPUT', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 0.000001, 'validation': self.validate_float_positive_or_zero,
         'tooltip': t('ui.settings.model_interaction.token_cost_input_help')},
        {'label': t('ui.settings.model_interaction.token_cost_output'), 'key': 'TOKEN_COST_OUTPUT', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 0.000002, 'validation': self.validate_float_positive_or_zero,
         'tooltip': t('ui.settings.model_interaction.token_cost_output_help')},
        {'label': t('ui.settings.model_interaction.max_model_tokens'), 'key': 'MAX_MODEL_TOKENS', 'depends_on': 'SHOW_TOKEN_INFO',
         'type': 'entry', 'default': 32000, 'validation': self.validate_positive_integer,
         'tooltip': t('ui.settings.model_interaction.max_model_tokens_help')},
    ]

    create_settings_section(self, parent,
                           t("ui.settings.model_interaction.token_settings"),
                           token_settings_config)

    command_processing_config = [
        {'label': t('ui.settings.model_interaction.use_command_processing'), 'key': 'USE_COMMAND_REPLACER',
         'type': 'checkbutton',
         'default_checkbutton': False, 'tooltip': t('ui.settings.model_interaction.use_command_processing_help')},
        {'label': t('ui.settings.model_interaction.min_similarity_threshold'), 'key': 'MIN_SIMILARITY_THRESHOLD',
         'type': 'entry',
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default': 0.40,
         'validation': self.validate_float_0_to_1,
         'tooltip': t('ui.settings.model_interaction.min_similarity_threshold_help')},
        {'label': t('ui.settings.model_interaction.category_switch_threshold'), 'key': 'CATEGORY_SWITCH_THRESHOLD',
         'type': 'entry',
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default': 0.18,
         'validation': self.validate_float_0_to_1,
         'tooltip': t('ui.settings.model_interaction.category_switch_threshold_help')},
        {'label': t('ui.settings.model_interaction.skip_comma_parameters'), 'key': 'SKIP_COMMA_PARAMETERS',
         'type': 'checkbutton',
         'depends_on': 'USE_COMMAND_REPLACER', 'hide_when_disabled': True,
         'default_checkbutton': True,
         'tooltip': t('ui.settings.model_interaction.skip_comma_parameters_help')},
    ]

    create_settings_section(self, parent,
                           t("ui.settings.model_interaction.command_processing"),
                           command_processing_config)