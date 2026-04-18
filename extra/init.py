import os
import sys
os.environ["HYDRA_FULL_ERROR"] = "1"

import torch
print(torch.__version__)

def ensure_project_root():
    project_root_file = os.path.join(os.path.dirname(sys.executable), '.project-root')
    
    if not os.path.exists(project_root_file):
        open(project_root_file, 'w').close() 
        print(f"Файл '{project_root_file}' создан.")

ensure_project_root()


from fish_speech_lib.inference import FishSpeech
import soundfile as sf

# Инициализация модели
tts = FishSpeech(
    device="cuda", 
    half=False,   
    compile_model=True, 
)

try:
    sample_rate, audio_data = tts(
        "Игровая инициализация!",
        reference_audio=r"Models/Mila.wav",
        reference_audio_text="О боже! Ты меня напугал! Блин, Моё сохранение! Не поняла... А где игра? Ты мне весь рут испоганил! Ну, чего тебе? А? Так! Я очень занята, Чтобы тебя развлекать, дурачка! Посмотрите на него, наглец! Не быть дружбе между нами! Из-за тебя ушиблась... Блин. А? Миту? Да пожалуйста! Дела мне до неё нет! Ни до первой, ни до сотой! Я Мила. Они там Мита на Мите, С миру по Мите, и это всё Митой погоняет! Да, да! Ну что за дурак, в самом деле? А куда это ты? Думаешь, вот так просто уйти отсюда? Ты думал, там что-то будет? А что ты там хотел увидеть? Страну чудес? Отсюда нет выхода! Не подходи! Я не знаю, что это! Какой-то глюк! Что ещё за кольцо? Обручальное?! И ты собираешься трогать это? Знай, если мой дом взорвётся — ты труп! Эй! А ну ВЫШЕЛ! Разве ты не видишь, что ванная занята?! И чего ты тут до сих пор стоишь?! ВЫЙДИ уже! Не зли меня! Уходи отсюда! Ты не иначе как ОГЛОХ! Девушке нужно помыться! Ну и что это было? Ни стыда, ни совести! Откуда мне знать, Сколько ещё ты будешь ковыряться в этих глюках? Ага... Ну, раз мой дом ещё цел, Значит, ты справился с глюком на кухне? Хорошо, а теперь я разрешаю тебе, Пойти в ванную комнату. А-а-ай! Ты снова напугал меня! Чего тебе?",
        max_new_tokens=1000,
        chunk_length=1000,

        use_memory_cache=False,
    )

    sf.write("temp/inited.wav", audio_data, sample_rate, format='WAV')

except ValueError as e:
    print(f"Error: {e}")
