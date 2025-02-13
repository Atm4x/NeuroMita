from chat_model import ChatModel
from server import ChatServer

from Silero import TelegramBotHandler

import os
import glob

import asyncio
import threading
import tkinter as tk


class ChatGUI:
    def __init__(self):

        self.silero_connected = False
        self.game_connected = False

        self.chat_window = None
        self.token_count_label = None

        self.bot_handler = None
        self.bot_handler_ready = False
        self.model = ChatModel(self)
        self.server = ChatServer(self, self.model)
        self.server_thread = None
        self.running = False
        self.start_server()
        self.textToTalk = ""
        self.patch_to_sound_file = ""
        self.ConnectedToGame = False
        self.root = tk.Tk()
        self.root.title("Чат с MitaAI")
        self.api_hash = None
        self.api_id = None
        self.phone = None

        try:
            self.api_key = os.getenv("NM_API_KEY")
            self.api_url = os.getenv("NM_API_URL")
            self.api_model = os.getenv("NM_API_MODEL")
            self.makeRequest = bool(os.getenv("NM_API_REQ", False))
        except:
            print("Не удалось удачно получить из сис переменных все про апи")

        self.last_price = ""

        self.delete_all_wav_files()
        self.setup_ui()

        # Событие для синхронизации потоков
        self.loop_ready_event = threading.Event()

        self.loop = None  # Переменная для хранения ссылки на цикл событий
        self.asyncio_thread = threading.Thread(target=self.start_asyncio_loop, daemon=True)
        self.asyncio_thread.start()

        self.start_silero_async()

        # Запуск проверки переменной textToTalk через after
        self.root.after(100, self.check_text_to_talk)

    def delete_all_wav_files(self):
        # Получаем список всех .wav файлов в корневой директории
        wav_files = glob.glob("*.wav")

        # Проходим по каждому файлу и удаляем его
        for wav_file in wav_files:
            try:
                os.remove(wav_file)
                print(f"Удален файл: {wav_file}")
            except Exception as e:
                print(f"Ошибка при удалении файла {wav_file}: {e}")

    def start_asyncio_loop(self):
        """Запускает цикл событий asyncio в отдельном потоке."""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            print("Цикл событий asyncio успешно запущен.")
            self.loop_ready_event.set()  # Сигнализируем, что цикл событий готов
            self.loop.run_forever()
        except Exception as e:
            print(f"Ошибка при запуске цикла событий asyncio: {e}")

    def start_silero_async(self):
        """Отправляет задачу для запуска Silero в цикл событий."""
        print("Ожидание готовности цикла событий...")
        self.loop_ready_event.wait()  # Ждем, пока цикл событий будет готов
        if self.loop and self.loop.is_running():
            print("Запускаем Silero через цикл событий.")
            asyncio.run_coroutine_threadsafe(self.startSilero(), self.loop)
        else:
            print("Ошибка: Цикл событий asyncio не запущен.")

    async def startSilero(self):
        """Асинхронный запуск обработчика Telegram Bot."""
        print("Telegram Bot запускается!")
        try:
            self.bot_handler = TelegramBotHandler(self)
            await self.bot_handler.start()
            self.bot_handler_ready = True
            print("Telegram Bot запущен!")
        except Exception as e:
            print(f"Ошибка при запуске Telegram Bot: {e}")
            self.gui.silero_connected.set(False)

    def run_in_thread(self, response):
        """Запуск асинхронной задачи в отдельном потоке."""
        # Убедимся, что цикл событий готов и запускаем задачу в том же цикле
        self.loop_ready_event.wait()  # Ждем, пока цикл событий будет готов
        if self.loop and self.loop.is_running():
            print("Запускаем асинхронную задачу в цикле событий...")
            # Здесь мы вызываем асинхронную задачу через главный цикл
            self.loop.create_task(self.run_send_and_receive(self.textToTalk))
        else:
            print("Ошибка: Цикл событий asyncio не готов.")

    async def run_send_and_receive(self, response):
        """Асинхронный метод для вызова send_and_receive."""
        print("Попытка получить фразу")
        await self.bot_handler.send_and_receive(response)
        print("Завершение получения фразы")

    def check_text_to_talk(self):
        """Периодическая проверка переменной self.textToTalk."""

        if self.textToTalk != "":  #and not self.ConnectedToGame:
            print(f"Есть текст для отправки: {self.textToTalk}")
            # Вызываем метод для отправки текста, если переменная не пуста
            if self.loop and self.loop.is_running():
                print("Цикл событий готов. Отправка текста.")
                asyncio.run_coroutine_threadsafe(self.run_send_and_receive(self.textToTalk), self.loop)
                self.textToTalk = ""  # Очищаем текст после отправки
                print("Выполнено")
            else:
                print("Ошибка: Цикл событий не готов.")
        #if self.patch_to_sound_file !="":

        # Перезапуск проверки через 100 миллисекунд
        self.root.after(100, self.check_text_to_talk)  # Это обеспечит постоянную проверку

    def start_server(self):
        """Запускает сервер в отдельном потоке."""
        if not self.running:
            self.running = True
            self.server.start()  # Инициализация сокета
            self.server_thread = threading.Thread(target=self.run_server_loop, daemon=True)
            self.server_thread.start()
            print("Сервер запущен.")

    def stop_server(self):
        """Останавливает сервер."""
        if self.running:
            self.running = False
            self.server.stop()
            print("Сервер остановлен.")

    def run_server_loop(self):
        """Цикл обработки подключений сервера."""
        while self.running:
            needUpdate = self.server.handle_connection()
            if needUpdate:
                self.load_chat_history()

    def setup_ui(self):
        self.root.config(bg="#2c2c2c")  # Установите темный цвет фона для всего окна

        main_frame = tk.Frame(self.root, bg="#2c2c2c")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Первый столбец
        left_frame = tk.Frame(main_frame, bg="#2c2c2c")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.chat_window = tk.Text(
            left_frame, height=30, width=80, state=tk.NORMAL,
            bg="#1e1e1e", fg="#ffffff", insertbackground="white", wrap=tk.WORD,
            font=("Arial", 12)
        )

        self.chat_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        input_frame = tk.Frame(left_frame, bg="#2c2c2c")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.user_entry = tk.Text(input_frame, height=3, width=50, bg="#1e1e1e", fg="#ffffff", insertbackground="white",
                                  font=("Arial", 12))
        self.user_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.user_entry.bind("<KeyRelease>", self.update_token_count)

        self.send_button = tk.Button(
            input_frame, text="Отправить", command=self.send_message,
            bg="#9370db", fg="#ffffff", font=("Arial", 12)
        )
        self.send_button.pack(side=tk.RIGHT, padx=5)

        self.token_count_label = tk.Label(
            left_frame, text=f"Последнее сообщение: {self.last_price}",
            bg="#2c2c2c", fg="#ffffff", font=("Arial", 12)
        )
        self.token_count_label.pack(fill=tk.X, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Второй столбец
        right_frame = tk.Frame(main_frame, bg="#2c2c2c")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Передаем right_frame как родителя
        self.setup_status_indicators(right_frame)

        self.setup_attitude_controls(right_frame)
        self.setup_boredom_controls(right_frame)
        self.setup_stress_controls(right_frame)
        self.setup_secret_controls(right_frame)

        self.setup_history_controls(right_frame)
        self.setup_debug_controls(right_frame)
        self.setup_api_controls(right_frame)

        self.load_chat_history()

    def insert_message(self, role, content):
        if role == "user":
            # Вставляем имя пользователя с зеленым цветом, а текст — обычным
            self.chat_window.insert(tk.END, "Вы: ", "user_name")
            self.chat_window.insert(tk.END, f"{content}\n")
        elif role == "assistant":
            # Вставляем имя Миты с синим цветом, а текст — обычным
            self.chat_window.insert(tk.END, "Мита: ", "gpt_name")
            self.chat_window.insert(tk.END, f"{content}\n\n")

    def setup_status_indicators(self, parent):
        # Создаем фрейм для индикаторов
        status_frame = tk.Frame(parent, bg="#2c2c2c")
        status_frame.pack(fill=tk.X, pady=5)

        # Переменные статуса
        self.game_connected = tk.BooleanVar(value=False)  # Статус подключения к игре
        self.silero_connected = tk.BooleanVar(value=False)  # Статус подключения к Silero

        # Галки для подключения
        self.game_status_checkbox = tk.Checkbutton(
            status_frame,
            text="Подключение к игре",
            variable=self.game_connected,
            state="disabled",
            bg="#2c2c2c",
            fg="#ffffff",
            selectcolor="#2c2c2c"
        )
        self.game_status_checkbox.pack(side=tk.LEFT, padx=5, pady=5)

        self.silero_status_checkbox = tk.Checkbutton(
            status_frame,
            text="Подключение к Silero",
            variable=self.silero_connected,
            state="disabled",
            bg="#2c2c2c",
            fg="#ffffff",
            selectcolor="#2c2c2c"
        )
        self.silero_status_checkbox.pack(side=tk.LEFT, padx=5, pady=5)

    def updateAll(self):
        self.update_status_colors()
        self.update_debug_info()

    def update_status_colors(self):
        self.game_connected.set(self.ConnectedToGame)  # Статус подключения к игре
        # Обновление цвета для подключения к игре
        game_color = "#00ff00" if self.game_connected.get() else "#ffffff"
        self.game_status_checkbox.config(fg=game_color)

        # Обновление цвета для подключения к Silero
        silero_color = "#00ff00" if self.silero_connected.get() else "#ffffff"
        self.silero_status_checkbox.config(fg=silero_color)

    def setup_attitude_controls(self, parent):
        attitude_frame = tk.Frame(parent, bg="#2c2c2c")
        attitude_frame.pack(fill=tk.X, pady=5)

        self.mood_label = tk.Label(
            attitude_frame, text=f"Настроение: {self.model.attitude}", bg="#2c2c2c", fg="#ffffff"
        )
        self.mood_label.pack(side=tk.LEFT, padx=5)

        mood_up_button = tk.Button(
            attitude_frame, text="+", command=lambda: self.adjust_attitude(15),
            bg="#8a2be2", fg="#ffffff"
        )
        mood_up_button.pack(side=tk.RIGHT, padx=5)

        mood_down_button = tk.Button(
            attitude_frame, text="-", command=lambda: self.adjust_attitude(-15),
            bg="#8a2be2", fg="#ffffff"
        )
        mood_down_button.pack(side=tk.RIGHT, padx=5)

    def setup_boredom_controls(self, parent):
        boredom_frame = tk.Frame(parent, bg="#2c2c2c")
        boredom_frame.pack(fill=tk.X, pady=5)

        self.boredom_label = tk.Label(
            boredom_frame, text=f"Скука: {self.model.boredom}", bg="#2c2c2c", fg="#ffffff"
        )
        self.boredom_label.pack(side=tk.LEFT, padx=5)

        stress_up_button = tk.Button(
            boredom_frame, text="+", command=lambda: self.adjust_boredom(15),
            bg="#8a2be2", fg="#ffffff"
        )
        stress_up_button.pack(side=tk.RIGHT, padx=5)

        stress_down_button = tk.Button(
            boredom_frame, text="-", command=lambda: self.adjust_boredom(-15),
            bg="#8a2be2", fg="#ffffff"
        )
        stress_down_button.pack(side=tk.RIGHT, padx=5)

    def setup_stress_controls(self, parent):
        stress_frame = tk.Frame(parent, bg="#2c2c2c")
        stress_frame.pack(fill=tk.X, pady=5)

        self.stress_label = tk.Label(
            stress_frame, text=f"Стресс: {self.model.stress}", bg="#2c2c2c", fg="#ffffff"
        )
        self.stress_label.pack(side=tk.LEFT, padx=5)

        stress_up_button = tk.Button(
            stress_frame, text="+", command=lambda: self.adjust_stress(15),
            bg="#8a2be2", fg="#ffffff"
        )
        stress_up_button.pack(side=tk.RIGHT, padx=5)

        stress_down_button = tk.Button(
            stress_frame, text="-", command=lambda: self.adjust_stress(-15),
            bg="#8a2be2", fg="#ffffff"
        )
        stress_down_button.pack(side=tk.RIGHT, padx=5)

    def setup_secret_controls(self, parent):
        secret_frame = tk.Frame(parent, bg="#2c2c2c")
        secret_frame.pack(fill=tk.X, pady=5)

        self.secret_var = tk.BooleanVar(value=self.model.secretExposed)

        secret_checkbox = tk.Checkbutton(
            secret_frame, text="Секрет раскрыт", variable=self.secret_var,
            bg="#2c2c2c", fg="#ffffff", command=self.adjust_secret
        )
        secret_checkbox.pack(side=tk.LEFT, padx=5)

    def setup_history_controls(self, parent):
        history_frame = tk.Frame(parent, bg="#2c2c2c")
        history_frame.pack(fill=tk.X, pady=5)

        clear_button = tk.Button(
            history_frame, text="Очистить историю", command=self.clear_history,
            bg="#8a2be2", fg="#ffffff"
        )
        clear_button.pack(side=tk.LEFT, padx=5)

        save_history_button = tk.Button(
            history_frame, text="Сохранить историю", command=self.model.save_chat_history,
            bg="#8a2be2", fg="#ffffff"
        )
        save_history_button.pack(side=tk.LEFT, padx=10)

        reload_prompts_button = tk.Button(
            history_frame, text="Перезагрузить промпты", command=self.model.reload_promts,
            bg="#8a2be2", fg="#ffffff"
        )
        reload_prompts_button.pack(side=tk.LEFT, padx=15)

    def load_chat_history(self):
        self.model.load_history()
        """Загрузить историю из модели и отобразить в интерфейсе."""
        for entry in self.model.chat_history:
            role = entry["role"]
            content = entry["content"]
            self.insert_message(role, content)
        self.update_debug_info()
        self.token_count_label.text = self.last_price

    def setup_debug_controls(self, parent):
        debug_frame = tk.Frame(parent, bg="#2c2c2c")
        debug_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.debug_window = tk.Text(
            debug_frame, height=5, width=50, bg="#1e1e1e", fg="#ffffff",
            state=tk.NORMAL, wrap=tk.WORD, insertbackground="white"
        )
        self.debug_window.pack(fill=tk.BOTH, expand=True)

        self.update_debug_info()  # Отобразить изначальное состояние переменных

    def setup_api_controls(self, parent):
        api_frame = tk.Frame(parent, bg="#2c2c2c")
        api_frame.pack(fill=tk.X, pady=10)

        self.show_api_var = tk.BooleanVar(value=False)

        api_toggle = tk.Checkbutton(
            api_frame, text="Показать настройки API", variable=self.show_api_var,
            command=self.toggle_api_settings, bg="#2c2c2c", fg="#ffffff"
        )
        api_toggle.pack(side=tk.LEFT, padx=5)

        self.api_settings_frame = tk.Frame(parent, bg="#2c2c2c")

        # Элементы в одном столбце
        tk.Label(
            self.api_settings_frame, text="API-ключ:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.api_key_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                      insertbackground="white")
        self.api_key_entry.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Ссылка:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)

        self.api_url_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                      insertbackground="white")
        self.api_url_entry.grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Модель:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)

        self.api_model_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                        insertbackground="white")
        self.api_model_entry.grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Telegram API ID:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)

        self.api_id_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                     insertbackground="white")
        self.api_id_entry.grid(row=7, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Telegram API Hash:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=8, column=0, padx=5, pady=5, sticky=tk.W)

        self.api_hash_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                       insertbackground="white")
        self.api_hash_entry.grid(row=9, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Telegram Phone:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=10, column=0, padx=5, pady=5, sticky=tk.W)

        self.phone_entry = tk.Entry(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",
                                    insertbackground="white")
        self.phone_entry.grid(row=11, column=0, padx=5, pady=5, sticky=tk.W)

        tk.Label(
            self.api_settings_frame, text="Make request:", bg="#2c2c2c", fg="#ffffff"
        ).grid(row=12, column=0, padx=5, pady=5, sticky=tk.W)

        # Переменная для тумблера

        #self.makeRequest_entry = tk.Checkbutton(self.api_settings_frame, width=50, bg="#1e1e1e", fg="#ffffff",text="Делать через request",variable=self.toggle_state)
        self.makeRequest_entry = tk.Checkbutton(
            self.api_settings_frame, text="Делать через request", variable=self.show_api_var,
            command=self.toggle_makeRequest, bg="#2c2c2c", fg="#ffffff"
        )
        self.makeRequest_entry.grid(row=13, column=0, padx=5, pady=5, sticky=tk.W)

        save_button = tk.Button(
            self.api_settings_frame, text="Сохранить", command=self.save_api_settings,
            bg="#8a2be2", fg="#ffffff"
        )
        save_button.grid(row=14, column=0, pady=10, sticky=tk.W)

    def toggle_makeRequest(self):
        print("FFF")
        self.makeRequest = not self.makeRequest
        if self.makeRequest:
            self.makeRequest_entry.config(text="Сейчас делается через реквест + структура гемини")
        else:
            self.makeRequest_entry.config(text="Сейчас делается через open api + структура гпт")

    def save_api_settings(self):

        api_key = self.api_key_entry.get()
        if api_key:
            self.api_key = api_key
            set_system_variable("NM_API_KEY", self.api_key)
            print(f"API-ключ сохранён: {self.api_key}")

        api_url = self.api_url_entry.get()
        if api_url:
            self.api_url = api_url
            set_system_variable("NM_API_URL", self.api_url)
            print(f"Ссылка API сохранена: {self.api_url}")

        api_model = self.api_model_entry.get()
        if api_model:
            self.api_model = api_model
            set_system_variable("NM_API_MODEL", self.api_model)
            print(f"Модель сохранена: {self.api_model}")


        api_id = self.api_id_entry.get()
        if api_id:
            self.api_id = api_id
            set_system_variable("NM_TELEGRAM_API_ID", self.api_id)
            print(f"Telegram API ID сохранён: {self.api_id}")

        api_hash = self.api_hash_entry.get()
        if api_hash:
            self.api_hash = api_hash
            set_system_variable("NM_TELEGRAM_API_HASH", self.api_hash)
            print(f"Telegram API Hash сохранён: {self.api_hash}")

        phone = self.phone_entry.get()
        if phone:
            self.phone = phone
            set_system_variable("NM_TELEGRAM_PHONE", self.phone)
            print(f"Telegram Phone сохранён: {self.phone}")

        # В чат модел пишем
        if self.api_key:
            self.model.set_api_key(self.api_key)
        if self.api_url:
            self.model.set_api_url(self.api_url)
        if self.api_model:
            self.model.api_model = self.api_model
        print(f"Сохранение данных авторизации")

        set_system_variable("NM_API_REQ", str(self.makeRequest))
        self.model.makeRequest = self.makeRequest


        self.model.update_openai_client()
        # В силеро пишем
        if not self.silero_connected:
            self.bot_handler.api_id = int(self.api_id)
            self.bot_handler.api_hash = self.api_hash
            self.bot_handler.phone = self.phone
            self.bot_handler.start()








        os.environ.update(os.environ)



    def paste_from_clipboard(self, event=None):
        try:
            clipboard_content = self.root.clipboard_get()
            self.user_entry.insert(tk.INSERT, clipboard_content)
        except tk.TclError:
            pass  # Если буфер обмена пуст, ничего не делаем

    def copy_to_clipboard(self, event=None):
        try:
            # Получение выделенного текста из поля ввода
            selected_text = self.user_entry.selection_get()
            # Копирование текста в буфер обмена
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
            self.root.update()  # Обновление буфера обмена
        except tk.TclError:
            # Если текст не выделен, ничего не делать
            pass

    def toggle_api_settings(self):
        if self.show_api_var.get():
            self.api_settings_frame.pack(fill=tk.X, padx=10, pady=10)
        else:
            self.api_settings_frame.pack_forget()

    def update_debug_info(self):
        """Обновить окно отладки с отображением актуальных данных."""
        self.debug_window.delete(1.0, tk.END)  # Очистить старые данные
        debug_info = (
            f"Отношение к игроку: {self.model.attitude}\n"
            f"Скука: {self.model.boredom}\n"
            f"Стресс: {self.model.stress}\n"
            f"Секрет: {self.model.secretExposed}\n"
        )
        self.debug_window.insert(tk.END, debug_info)

    def adjust_attitude(self, amount):
        self.model.adjust_attitude(amount)
        self.mood_label.config(text=f"Отношение: {self.model.attitude}")
        self.update_debug_info()

    def adjust_boredom(self, amount):
        self.model.adjust_boredom(amount)
        self.boredom_label.config(text=f"Скука: {self.model.boredom}")
        self.update_debug_info()

    def adjust_stress(self, amount):
        self.model.adjust_stress(amount)
        self.stress_label.config(text=f"Стресс: {self.model.stress}")
        self.update_debug_info()

    def adjust_secret(self):
        self.model.secretExposed = not self.model.secretExposed
        self.update_debug_info()

    def update_token_count(self, event=None):
        if False and self.model.hasTokenizer:
            user_input = self.user_entry.get("1.0", "end-1c")
            token_count, cost = self.model.calculate_cost(user_input)
            self.token_count_label.config(
                text=f"ВЫКЛЮЧЕНО!! Токенов: {token_count}/{self.model.max_input_tokens} | Ориент. стоимость: {cost:.4f} ₽"
            )
            self.update_debug_info()

    def insertDialog(self, input_text="", response=""):
        if input_text != "":
            self.chat_window.insert(tk.END, "Вы: ", "user_name")
            self.chat_window.insert(tk.END, f"{input_text}\n")
        if response != "":
            self.chat_window.insert(tk.END, "Мита: ", "gpt_name")
            self.chat_window.insert(tk.END, f"{response}\n\n")

    def send_message(self, system_input=""):
        user_input = self.user_entry.get("1.0", "end-1c")
        if not user_input.strip() and system_input == "":
            return

        if user_input != "":
            self.insert_message("user", user_input)
            self.user_entry.delete("1.0", "end")

        response = self.model.generate_response(user_input, system_input)
        counter = 0
        #while self.model.repeatResponse and counter<3:
        #   response += self.model.generate_response("", "")
        #  counter+=1
        self.insert_message("assistant", response)
        self.user_entry.delete("1.0", "end")
        self.updateAll()
        # Отправка сообщения на сервер
        if self.server:
            try:
                # Отправляем сообщение клиенту через сервер
                if self.server.client_socket:
                    self.server.send_message_to_server(response)
                    print("Сообщение отправлено на сервер.")
                else:
                    print("Нет активного подключения к клиенту.")
            except Exception as e:
                print(f"Ошибка при отправке сообщения на сервер: {e}")

    def clear_history(self):
        self.model.clear_history()
        self.chat_window.delete(1.0, tk.END)
        self.update_debug_info()

    def run(self):
        self.root.mainloop()

    def on_closing(self):
        self.stop_server()
        #self.send_message("Игрок покинул игру")
        print("Закрываемся")
        self.root.destroy()
        #1

    def close_app(self):
        """Закрытие приложения корректным образом."""
        print("Завершение программы...")
        self.root.destroy()  # Закрывает GUI


import winreg


def set_system_variable(name, value):
    try:
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(reg_key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(reg_key)
        print(f"Переменная {name} успешно установлена в системных настройках.")
    except Exception as e:
        print(f"Ошибка при установке переменной {name}: {e}")
