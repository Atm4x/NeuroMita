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
)


def _languages(engine_id: str) -> tuple:
    if engine_id == "google":
        return _GOOGLE_LANGUAGES
    if engine_id in ("whisper", "whisper_onnx"):
        return _WHISPER_LANGUAGES
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
        help_ru = "В приложении доступны 9 вариантов Google Web Speech. Это не полный список языков всех сервисов Google. Нужен интернет; автоопределение здесь недоступно."
        help_en = "The app offers 9 Google Web Speech choices, not all languages of every Google service. Internet is required; automatic detection is unavailable here."
    elif fixed:
        help_ru = "Доступные модели GigaAM v2/v3 распознают только русский язык. Смена языка и автоопределение не поддерживаются."
        help_en = "The available GigaAM v2/v3 models recognize Russian only. Language selection and automatic detection are unsupported."
    else:
        options.append("auto")
        labels["auto"] = "Автоопределение / Automatic detection (auto)"
        help_ru = "Whisper large-v3 и large-v3-turbo поддерживают 100 языков и автоопределение. Качество зависит от языка и записи; автоопределение может ошибаться на коротких фрагментах."
        help_en = "Whisper large-v3 and large-v3-turbo support 100 languages and automatic detection. Quality varies by language and recording; detection may be unreliable on short clips."
    return {
        "key": "language", "label_ru": "Язык", "label_en": "Language",
        "type": "combobox", "options": options, "option_labels": labels,
        "default": "ru-RU" if engine_id == "google" else "ru",
        "enabled": not fixed, "help_ru": help_ru, "help_en": help_en,
    }
