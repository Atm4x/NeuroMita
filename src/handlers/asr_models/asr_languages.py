"""ASR language capabilities shipped in the app; no runtime/ML dependencies."""

# GigaAM v2/v3 scope: https://github.com/salute-developers/GigaAM#gigaam-overview
# Primary Whisper source (verified 2026-10-09):
# https://raw.githubusercontent.com/openai/whisper/main/whisper/tokenizer.py
# All 100 codes also match lang_to_id in generation_config.json for
# https://huggingface.co/openai/whisper-large-v3
# https://huggingface.co/openai/whisper-large-v3-turbo
# https://huggingface.co/onnx-community/whisper-large-v3-turbo-onnx
_WHISPER_LANGUAGES = (
    ('en', 'English', 'Английский'),
    ('zh', 'Chinese', 'Китайский'),
    ('de', 'German', 'Немецкий'),
    ('es', 'Spanish', 'Испанский'),
    ('ru', 'Russian', 'Русский'),
    ('ko', 'Korean', 'Корейский'),
    ('fr', 'French', 'Французский'),
    ('ja', 'Japanese', 'Японский'),
    ('pt', 'Portuguese', 'Португальский'),
    ('tr', 'Turkish', 'Турецкий'),
    ('pl', 'Polish', 'Польский'),
    ('ca', 'Catalan', 'Каталанский'),
    ('nl', 'Dutch', 'Нидерландский'),
    ('ar', 'Arabic', 'Арабский'),
    ('sv', 'Swedish', 'Шведский'),
    ('it', 'Italian', 'Итальянский'),
    ('id', 'Indonesian', 'Индонезийский'),
    ('hi', 'Hindi', 'Хинди'),
    ('fi', 'Finnish', 'Финский'),
    ('vi', 'Vietnamese', 'Вьетнамский'),
    ('he', 'Hebrew', 'Иврит'),
    ('uk', 'Ukrainian', 'Украинский'),
    ('el', 'Greek', 'Греческий'),
    ('ms', 'Malay', 'Малайский'),
    ('cs', 'Czech', 'Чешский'),
    ('ro', 'Romanian', 'Румынский'),
    ('da', 'Danish', 'Датский'),
    ('hu', 'Hungarian', 'Венгерский'),
    ('ta', 'Tamil', 'Тамильский'),
    ('no', 'Norwegian', 'Норвежский'),
    ('th', 'Thai', 'Тайский'),
    ('ur', 'Urdu', 'Урду'),
    ('hr', 'Croatian', 'Хорватский'),
    ('bg', 'Bulgarian', 'Болгарский'),
    ('lt', 'Lithuanian', 'Литовский'),
    ('la', 'Latin', 'Латынь'),
    ('mi', 'Maori', 'Маори'),
    ('ml', 'Malayalam', 'Малаялам'),
    ('cy', 'Welsh', 'Валлийский'),
    ('sk', 'Slovak', 'Словацкий'),
    ('te', 'Telugu', 'Телугу'),
    ('fa', 'Persian', 'Персидский'),
    ('lv', 'Latvian', 'Латышский'),
    ('bn', 'Bengali', 'Бенгальский'),
    ('sr', 'Serbian', 'Сербский'),
    ('az', 'Azerbaijani', 'Азербайджанский'),
    ('sl', 'Slovenian', 'Словенский'),
    ('kn', 'Kannada', 'Каннада'),
    ('et', 'Estonian', 'Эстонский'),
    ('mk', 'Macedonian', 'Македонский'),
    ('br', 'Breton', 'Бретонский'),
    ('eu', 'Basque', 'Баскский'),
    ('is', 'Icelandic', 'Исландский'),
    ('hy', 'Armenian', 'Армянский'),
    ('ne', 'Nepali', 'Непальский'),
    ('mn', 'Mongolian', 'Монгольский'),
    ('bs', 'Bosnian', 'Боснийский'),
    ('kk', 'Kazakh', 'Казахский'),
    ('sq', 'Albanian', 'Албанский'),
    ('sw', 'Swahili', 'Суахили'),
    ('gl', 'Galician', 'Галисийский'),
    ('mr', 'Marathi', 'Маратхи'),
    ('pa', 'Punjabi', 'Панджаби'),
    ('si', 'Sinhala', 'Сингальский'),
    ('km', 'Khmer', 'Кхмерский'),
    ('sn', 'Shona', 'Шона'),
    ('yo', 'Yoruba', 'Йоруба'),
    ('so', 'Somali', 'Сомали'),
    ('af', 'Afrikaans', 'Африкаанс'),
    ('oc', 'Occitan', 'Окситанский'),
    ('ka', 'Georgian', 'Грузинский'),
    ('be', 'Belarusian', 'Белорусский'),
    ('tg', 'Tajik', 'Таджикский'),
    ('sd', 'Sindhi', 'Синдхи'),
    ('gu', 'Gujarati', 'Гуджарати'),
    ('am', 'Amharic', 'Амхарский'),
    ('yi', 'Yiddish', 'Идиш'),
    ('lo', 'Lao', 'Лаосский'),
    ('uz', 'Uzbek', 'Узбекский'),
    ('fo', 'Faroese', 'Фарерский'),
    ('ht', 'Haitian Creole', 'Гаитянский креольский'),
    ('ps', 'Pashto', 'Пушту'),
    ('tk', 'Turkmen', 'Туркменский'),
    ('nn', 'Nynorsk', 'Нюнорск'),
    ('mt', 'Maltese', 'Мальтийский'),
    ('sa', 'Sanskrit', 'Санскрит'),
    ('lb', 'Luxembourgish', 'Люксембургский'),
    ('my', 'Myanmar', 'Бирманский'),
    ('bo', 'Tibetan', 'Тибетский'),
    ('tl', 'Tagalog', 'Тагальский'),
    ('mg', 'Malagasy', 'Малагасийский'),
    ('as', 'Assamese', 'Ассамский'),
    ('tt', 'Tatar', 'Татарский'),
    ('haw', 'Hawaiian', 'Гавайский'),
    ('ln', 'Lingala', 'Лингала'),
    ('ha', 'Hausa', 'Хауса'),
    ('ba', 'Bashkir', 'Башкирский'),
    ('jw', 'Javanese', 'Яванский'),
    ('su', 'Sundanese', 'Сунданский'),
    ('yue', 'Cantonese', 'Кантонский'),
)

# Google Web Speech demo catalogue (verified 2026-10-10), plus legacy zh-CN:
# https://www.google.com/intl/en/chrome/demos/speech.html
_GOOGLE_LANGUAGES = (
    ("ru-RU", "Russian", "Русский"),
    ("uk-UA", "Ukrainian", "Украинский"),
    ("en-US", "English (US)", "Английский (США)"),
    ("en-GB", "English (UK)", "Английский (Великобритания)"),
    ("de-DE", "German", "Немецкий"),
    ("fr-FR", "French", "Французский"),
    ("es-ES", "Spanish", "Испанский"),
    ("ja-JP", "Japanese", "Японский"),
    ("zh-CN", "Chinese", "Китайский"),
    ("af-ZA", "Afrikaans", "Африкаанс"),
    ("am-ET", "Amharic", "Амхарский"),
    ("az-AZ", "Azerbaijani", "Азербайджанский"),
    ("bn-BD", "Bengali (Bangladesh)", "Бенгальский (Бангладеш)"),
    ("bn-IN", "Bengali (India)", "Бенгальский (Индия)"),
    ("id-ID", "Indonesian", "Индонезийский"),
    ("ms-MY", "Malay", "Малайский"),
    ("ca-ES", "Catalan", "Каталанский"),
    ("cs-CZ", "Czech", "Чешский"),
    ("da-DK", "Danish", "Датский"),
    ("en-AU", "English (Australia)", "Английский (Австралия)"),
    ("en-CA", "English (Canada)", "Английский (Канада)"),
    ("en-IN", "English (India)", "Английский (Индия)"),
    ("en-KE", "English (Kenya)", "Английский (Кения)"),
    ("en-TZ", "English (Tanzania)", "Английский (Танзания)"),
    ("en-GH", "English (Ghana)", "Английский (Гана)"),
    ("en-NZ", "English (New Zealand)", "Английский (Новая Зеландия)"),
    ("en-NG", "English (Nigeria)", "Английский (Нигерия)"),
    ("en-ZA", "English (South Africa)", "Английский (ЮАР)"),
    ("en-PH", "English (Philippines)", "Английский (Филиппины)"),
    ("es-AR", "Spanish (Argentina)", "Испанский (Аргентина)"),
    ("es-BO", "Spanish (Bolivia)", "Испанский (Боливия)"),
    ("es-CL", "Spanish (Chile)", "Испанский (Чили)"),
    ("es-CO", "Spanish (Colombia)", "Испанский (Колумбия)"),
    ("es-CR", "Spanish (Costa Rica)", "Испанский (Коста-Рика)"),
    ("es-EC", "Spanish (Ecuador)", "Испанский (Эквадор)"),
    ("es-SV", "Spanish (El Salvador)", "Испанский (Сальвадор)"),
    ("es-US", "Spanish (US)", "Испанский (США)"),
    ("es-GT", "Spanish (Guatemala)", "Испанский (Гватемала)"),
    ("es-HN", "Spanish (Honduras)", "Испанский (Гондурас)"),
    ("es-MX", "Spanish (Mexico)", "Испанский (Мексика)"),
    ("es-NI", "Spanish (Nicaragua)", "Испанский (Никарагуа)"),
    ("es-PA", "Spanish (Panama)", "Испанский (Панама)"),
    ("es-PY", "Spanish (Paraguay)", "Испанский (Парагвай)"),
    ("es-PE", "Spanish (Peru)", "Испанский (Перу)"),
    ("es-PR", "Spanish (Puerto Rico)", "Испанский (Пуэрто-Рико)"),
    ("es-DO", "Spanish (Dominican Republic)", "Испанский (Доминиканская Республика)"),
    ("es-UY", "Spanish (Uruguay)", "Испанский (Уругвай)"),
    ("es-VE", "Spanish (Venezuela)", "Испанский (Венесуэла)"),
    ("eu-ES", "Basque", "Баскский"),
    ("fil-PH", "Filipino", "Филиппинский"),
    ("jv-ID", "Javanese", "Яванский"),
    ("gl-ES", "Galician", "Галисийский"),
    ("gu-IN", "Gujarati", "Гуджарати"),
    ("hr-HR", "Croatian", "Хорватский"),
    ("zu-ZA", "Zulu", "Зулу"),
    ("is-IS", "Icelandic", "Исландский"),
    ("it-IT", "Italian (Italy)", "Итальянский (Италия)"),
    ("it-CH", "Italian (Switzerland)", "Итальянский (Швейцария)"),
    ("kn-IN", "Kannada", "Каннада"),
    ("km-KH", "Khmer", "Кхмерский"),
    ("lv-LV", "Latvian", "Латышский"),
    ("lt-LT", "Lithuanian", "Литовский"),
    ("ml-IN", "Malayalam", "Малаялам"),
    ("mr-IN", "Marathi", "Маратхи"),
    ("hu-HU", "Hungarian", "Венгерский"),
    ("lo-LA", "Lao", "Лаосский"),
    ("nl-NL", "Dutch", "Нидерландский"),
    ("ne-NP", "Nepali", "Непальский"),
    ("nb-NO", "Norwegian Bokmal", "Норвежский букмол"),
    ("pl-PL", "Polish", "Польский"),
    ("pt-BR", "Portuguese (Brazil)", "Португальский (Бразилия)"),
    ("pt-PT", "Portuguese (Portugal)", "Португальский (Португалия)"),
    ("ro-RO", "Romanian", "Румынский"),
    ("si-LK", "Sinhala", "Сингальский"),
    ("sl-SI", "Slovenian", "Словенский"),
    ("su-ID", "Sundanese", "Сунданский"),
    ("sk-SK", "Slovak", "Словацкий"),
    ("fi-FI", "Finnish", "Финский"),
    ("sv-SE", "Swedish", "Шведский"),
    ("sw-TZ", "Swahili (Tanzania)", "Суахили (Танзания)"),
    ("sw-KE", "Swahili (Kenya)", "Суахили (Кения)"),
    ("ka-GE", "Georgian", "Грузинский"),
    ("hy-AM", "Armenian", "Армянский"),
    ("ta-IN", "Tamil (India)", "Тамильский (Индия)"),
    ("ta-SG", "Tamil (Singapore)", "Тамильский (Сингапур)"),
    ("ta-LK", "Tamil (Sri Lanka)", "Тамильский (Шри-Ланка)"),
    ("ta-MY", "Tamil (Malaysia)", "Тамильский (Малайзия)"),
    ("te-IN", "Telugu", "Телугу"),
    ("vi-VN", "Vietnamese", "Вьетнамский"),
    ("tr-TR", "Turkish", "Турецкий"),
    ("ur-PK", "Urdu (Pakistan)", "Урду (Пакистан)"),
    ("ur-IN", "Urdu (India)", "Урду (Индия)"),
    ("el-GR", "Greek", "Греческий"),
    ("bg-BG", "Bulgarian", "Болгарский"),
    ("sr-RS", "Serbian", "Сербский"),
    ("ko-KR", "Korean", "Корейский"),
    ("cmn-Hans-CN", "Mandarin (Mainland China)", "Севернокитайский (материковый Китай)"),
    ("cmn-Hans-HK", "Mandarin (Hong Kong)", "Севернокитайский (Гонконг)"),
    ("cmn-Hant-TW", "Mandarin (Taiwan)", "Севернокитайский (Тайвань)"),
    ("yue-Hant-HK", "Cantonese (Hong Kong)", "Кантонский (Гонконг)"),
    ("hi-IN", "Hindi", "Хинди"),
    ("th-TH", "Thai", "Тайский"),
)

_GOOGLE_PRIMARY_CODES = (
    "ru-RU", "uk-UA", "en-US", "de-DE", "fr-FR", "es-ES",
    "it-IT", "pt-BR", "ja-JP", "zh-CN", "ko-KR",
)
_WHISPER_PRIMARY_CODES = tuple(code.split("-")[0] for code in _GOOGLE_PRIMARY_CODES)


def _primary_first(languages: tuple, primary_codes: tuple) -> tuple:
    by_code = {row[0]: row for row in languages}
    return tuple(by_code[code] for code in primary_codes) + tuple(
        row for row in languages if row[0] not in primary_codes
    )


def _languages(engine_id: str) -> tuple:
    if engine_id == "google":
        return _primary_first(_GOOGLE_LANGUAGES, _GOOGLE_PRIMARY_CODES)
    if engine_id in ("whisper", "whisper_onnx"):
        return _primary_first(_WHISPER_LANGUAGES, _WHISPER_PRIMARY_CODES)
    if engine_id in ("gigaam", "gigaam_onnx"):
        return (("ru", "Russian", "Русский"),)
    raise ValueError(f"Unknown ASR engine: {engine_id!r}")


def asr_language_names(engine_id: str) -> list[str]:
    return [english for _, english, _ in _languages(engine_id)]


def asr_language_field(engine_id: str) -> dict:
    languages = _languages(engine_id)
    options = [code for code, _, _ in languages]
    labels = {code: f"{russian} / {english} ({code})" for code, english, russian in languages}
    fixed = engine_id in ("gigaam", "gigaam_onnx")
    if engine_id == "google":
        for code in _GOOGLE_PRIMARY_CODES:
            labels[code] = "★ " + labels[code]
        help_ru = f"★ — 11 основных языков в начале списка. В приложении доступны {len(languages)} вариантов языка и региона по каталогу демонстрации Google Web Speech, включая прежний zh-CN. Нужен интернет; автоопределение здесь недоступно. Доступность и качество зависят от сервиса Google и записи."
        help_en = f"★ marks the 11 primary languages at the top of the list. The app offers {len(languages)} language and regional choices from the Google Web Speech demo catalogue, including legacy zh-CN. Internet is required; automatic detection is unavailable here. Availability and quality depend on Google's service and the recording."
    elif fixed:
        help_ru = "Доступные модели GigaAM v2/v3 распознают только русский язык. Смена языка и автоопределение не поддерживаются."
        help_en = "The available GigaAM v2/v3 models recognize Russian only. Language selection and automatic detection are unsupported."
    else:
        for code in _WHISPER_PRIMARY_CODES:
            labels[code] = "★ " + labels[code]
        options.append("auto")
        labels["auto"] = "Автоопределение / Automatic detection (auto)"
        help_ru = "★ — 11 основных языков в начале списка. Whisper large-v3 и large-v3-turbo поддерживают 100 языков и автоопределение. Качество зависит от языка и записи; автоопределение может ошибаться на коротких фрагментах."
        help_en = "★ marks the 11 primary languages at the top of the list. Whisper large-v3 and large-v3-turbo support 100 languages and automatic detection. Quality varies by language and recording; detection may be unreliable on short clips."
    return {
        "key": "language", "label_ru": "Язык", "label_en": "Language",
        "type": "combobox", "options": options, "option_labels": labels,
        "default": "ru-RU" if engine_id == "google" else "ru",
        "enabled": not fixed, "help_ru": help_ru, "help_en": help_en,
    }
