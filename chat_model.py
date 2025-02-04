import json

import requests
import tiktoken
from openai import OpenAI
import os
import sys
import datetime
import time
from g4f.client import Client
import re
import shutil


from utils import clamp, print_ip_and_country, get_resource_path, load_text_from_file, save_combined_messages, \
    calculate_cost_for_combined_messages, count_tokens





class ChatModel:
    def __init__(self, gui):

        self.gui = gui

        self.api_key = os.getenv("NM_API_KEY")  #"sk-PkNRM8HNkAeVadcJEwKVW6c8OTtafs6f"
        self.api_url = os.getenv("NM_API_URL")

        # Stable
        if False:
            self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)
            self.modelName = "gpt-4o-mini"
        # test deepseek
        if False:
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.proxyapi.ru/deepseek")
            self.modelName = "deepseek-chat"
        # test gemini
        if True:
            self.url = "https://api.proxyapi.ru/google/v1/models/gemini-1.5-flash:generateContent"
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.proxyapi.ru/google")
            self.modelName = "gemini-1.5-flash"

        #self.client = OpenAI(api_key="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", base_url="https://openrouter.ai/api/v1")
        #self.client = OpenAI(api_key="sk-61554d38a5b9423e97b0b766e35bb598", base_url="https://api.deepseek.com")
        #self.client = Client()

        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
            self.hasTokenizer = True
        except:
            print("Тиктокен не сработал(")
            self.hasTokenizer = False

        self.max_input_tokens = 2048
        self.max_response_tokens = 4000
        self.cost_input_per_1000 = 0.0432
        self.cost_response_per_1000 = 0.1728
        self.history_file = "SavedHistories/chat_history.json"
        self.chat_history = self.load_history().get('messages', [])
        self.memory_limit = 40  # Ограничение сообщения
        self.attitude = 60
        self.boredom = 10
        self.stress = 5

        self.distance = 0.0
        self.roomPlayer = -1
        self.roomMita = -1
        self.nearObjects = ""
        self.actualInfo = ""
        self.LongMemoryRememberCount = 0

        self.infos = []

        self.SecretExposedText = ""
        self.secretExposed = False
        self.secretExposedFirst = False
        # Загрузка данных из файлов
        self.PlayingFirst = False

        self.load_prompts()

        self.MitaLongMemory = {"role": "system", "content": f" ДолгаяПамять<  >КонецДолгойПамяти "}
        self.MitaMainBehaviour = []
        self.MitaExamples = []
        self.systemMessages = []
        self.HideAiData = True
        #print_ip_and_country()

        self.repeatResponse = False

    def appendInfos(self, info):
        message = {
            "role": "system",
            "content": info
        }
        self.infos.append(message)

    def load_prompts(self):
        self.common = self.load_text_from_file("Promts/Main/common.txt")
        self.main = self.load_text_from_file("Promts/Main/main.txt")
        self.player = self.load_text_from_file("Promts/Main/player.txt")
        self.mainPlaying = self.load_text_from_file("Promts/Main/mainPlaing.txt")
        self.mainCrazy = self.load_text_from_file("Promts/Main/mainCrazy.txt")

        self.examplesLong = self.load_text_from_file("Promts/Context/examplesLong.txt")
        self.examplesLongCrazy = self.load_text_from_file("Promts/Context/examplesLongCrazy.txt")

        self.world = self.load_text_from_file("Promts/Context/world.txt")
        self.mita_history = self.load_text_from_file("Promts/Context/mita_history.txt")

        self.variableEffects = self.load_text_from_file("Promts/Structural/VariablesEffects.txt")
        self.response_structure = self.load_text_from_file("Promts/Structural/response_structure.txt")

        self.SecretExposedText = self.load_text_from_file("Promts/Events/SecretExposed.txt")

    @staticmethod
    def load_text_from_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    @staticmethod
    def load_json_file(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Файл {filepath} не найден.")
            return {}

    def calculate_cost(self, user_input):
        # Загружаем историю
        history_data = self.load_history()

        # Получаем только сообщения
        messages = history_data.get('messages', [])

        # Добавляем новое сообщение от пользователя
        messages.append({"role": "user", "content": user_input})

        # Считаем токены
        token_count = self.count_tokens(messages)

        # Рассчитываем стоимость
        cost = (token_count / 1000) * self.cost_input_per_1000

        return token_count, cost

    def count_tokens(self, messages):
        return sum(len(self.tokenizer.encode(msg["content"])) for msg in messages if
                   isinstance(msg, dict) and "content" in msg)

    def adjust_attitude(self, amount):
        amount = clamp(amount, -20, 20)
        """Корректируем отношение."""
        self.attitude = clamp(self.attitude + amount, 0, 100)
        print(f"Отношение изменилось на {amount}, новое значение: {self.attitude}")

    def adjust_boredom(self, amount):
        amount = clamp(amount, -20, 20)
        """Корректируем уровень скуки."""
        self.boredom = clamp(self.boredom + amount, 0, 100)
        print(f"Скука изменилась на {amount}, новое значение: {self.boredom}")

    def adjust_stress(self, amount):
        amount = clamp(amount, -20, 20)
        """Корректируем уровень стресса."""
        self.stress = clamp(self.stress + amount, 0, 100)
        print(f"Стресс изменился на {amount}, новое значение: {self.stress}")

    def set_api_key(self, api_key):
        self.api_key = api_key
        self.set_api_key_url()

    def set_api_url(self, api_url):
        self.api_url = api_url
        self.set_api_key_url()

    def set_api_key_url(self):
        if self.api_url != "":
            self.client = OpenAI(api_key=self.api_key,
                                 base_url=self.api_url)
        else:
            self.client = OpenAI(api_key=self.api_key)

    def generate_response(self, user_input, system_input=""):
        self.repeatResponse = False
        # Загрузка истории из файла
        history_data = self.load_history()

        messages = history_data.get('messages', [])
        if len(self.infos) > 0:
            print("Попытался расширить messages")
            messages.extend(self.infos)
            self.infos.clear()

        current_info = history_data.get('currentInfo', {})

        print(
            f"mood: {self.attitude}, secretExposed: {self.secretExposed}, secretExposedFirst: {self.secretExposedFirst}")

        # Логика для первой фазы (вводная информация)
        if len(messages) == 0:
            self._initialize_conversation()

        # Логика для поведения при игре с игроком
        elif self.attitude < 50 and not (self.secretExposed or self.PlayingFirst):
            self._start_playing_with_player()

        # Логика для раскрытия секрета
        elif (self.attitude <= 10 or self.secretExposed) and not self.secretExposedFirst:
            self._reveal_secret(messages)

        # Обновление текущего настроения
        timed_system_message = self._generate_timed_system_message()

        # Добавление информации о времени и пользовательского ввода
        messages = self._process_user_input(user_input, system_input, messages)

        # Ограничение на количество сообщений
        messages = messages[-self.memory_limit:]

        # Обновление текущей информации
        current_info.update({
            'MitaMainBehaviour': self.MitaMainBehaviour,
            'MitaExamples': self.MitaExamples,
            'timed_system_message': timed_system_message,
            'MitaLongMemory': self.MitaLongMemory
        })
        current_info['MitaSystemMessages'] = self.systemMessages

        combined_messages = self._combine_messages(messages, timed_system_message)

        # Генерация ответа с использованием клиента
        try:
            response = self._generate_chat_response(combined_messages)

            response_message = {
                "role": "assistant",
                "content": response
            }
            messages.append(response_message)

            # Процессинг ответа: изменяем показатели и сохраняем историю
            response = self.process_response(user_input, response, messages)

            current_info.update({
                'MitaLongMemory': self.MitaLongMemory
            })

            print("До фразы")
            self.gui.textToTalk = self.process_text_to_voice(response)
            print("self.gui.textToTalk: "+self.gui.textToTalk)
            #self.update_memory_in_history()
            self.save_history({
                'messages': messages,
                'currentInfo': current_info,
                # Сохраняем переменные в историю
                'attitude': self.attitude,
                'boredom': self.boredom,
                'stress': self.stress,
                'secretExposed': self.secretExposed,
                'secretExposedFirst': self.secretExposedFirst
            })

            return response
        except Exception as e:
            print(f"Ошибка на фазе генерации: {e}")
            return f"Ошибка на фазе генерации: {e}"

    def _initialize_conversation(self):
        """Инициализация начальной беседы"""
        self.systemMessages.insert(0, {"role": "system", "content": f"{self.player}\n"})
        self.MitaExamples = {"role": "system", "content": f"{self.examplesLong}\n"}
        self.MitaMainBehaviour = {"role": "system", "content": f"{self.main}\n"}
        self.systemMessages.insert(0, {"role": "system", "content": f"{self.response_structure}"})

    def _start_playing_with_player(self):
        """Игровая логика, когда персонаж начинает играть с игроком"""
        print("Играет с игроком в якобы невиновную")
        self.PlayingFirst = True
        self.MitaMainBehaviour = {"role": "system", "content": f"{self.mainPlaying}\n"}

    def _reveal_secret(self, messages):
        """Логика раскрытия секрета"""
        print("Перестала играть вообще")
        self.secretExposedFirst = True
        self.secretExposed = True
        self.MitaMainBehaviour = {
            "role": "system",
            "content": f"{self.mainCrazy}\n{self.response_structure}"
        }
        self.MitaExamples = {"role": "system", "content": f"{self.examplesLongCrazy}\n"}
        add_temporary_system_message(messages, f"{self.SecretExposedText}")
        system_message = {"role": "system", "content": f"{self.mita_history}\n"}
        self.systemMessages.append(system_message)

    def _generate_timed_system_message(self):
        """Генерация сообщения с текущим состоянием персонажа"""
        return {
            "role": "system",
            "content": (f"Твои характеристики. {self.variableEffects}"
                        f"Конкретно сейчас они следующие: "
                        f"Отношение: {self.attitude}/100."
                        f"Стресс: {self.stress}/100."
                        f"Скука: {self.boredom}/100."
                        f"Состояние секрета: {self.secretExposed}"
                        f"{self.common}")
        }

    def _process_user_input(self, user_input, system_input, messages):
        self.LongMemoryRememberCount += 1

        """Обработка пользовательского ввода и добавление сообщений"""
        date_now = datetime.datetime.now().replace(microsecond=0)

        repeated_system_message = f"Time: {date_now}. до игрока {self.distance}м. "

        if self.distance == 0:
            repeated_system_message = f"Time: {date_now}. до игрока ? м. "
        #elif float(self.distance) > 10:
        #
        # Проверяем правильность вызова get_room_name
        repeated_system_message += f"You are in {self.get_room_name(int(self.roomMita))}, player is in {self.get_room_name(int(self.roomPlayer))}. "

        if self.LongMemoryRememberCount % 3 == 0:
            repeated_system_message += " Запомни факты за 3 сообщения пользователя используя <+h>Факт который нужно запомнить</h>"

        if self.LongMemoryRememberCount % 6 == 0:
            repeated_system_message += " Реструктуризируй память при необходимости используя <#h>Итоговые факты об игроке</h>"

        messages.append({"role": "system", "content": repeated_system_message})

        if system_input != "":
            messages.append({"role": "system", "content": system_input})
        if user_input != "":
            messages.append({"role": "user", "content": user_input})

        return messages

    def get_room_name(self, room_id):
        # Сопоставление ID комнаты с её названием
        room_names = {
            0: "Кухня",  # Кухня
            1: "Зал",  # Главная комната
            2: "Комната",  # Спальня
            3: "Туалет",  # Туалет
            4: "Подвал"  # Туалет
        }

        # Возвращаем название комнаты, если оно есть, иначе возвращаем сообщение о неизвестной комнате
        return room_names.get(room_id, "?")

    def _combine_messages(self, messages, timed_system_message):
        """Комбинирование всех сообщений перед отправкой"""
        combined_messages = []
        # Чем выше здесь, тем дальше от начала будет

        # Добавляем systemMessages, если они не пустые Здесь Как она отвечает и коммон скрипТ!
        if self.systemMessages:
            combined_messages.extend(self.systemMessages)
            print("systemMessages успешно добавлены. Количество:", len(self.systemMessages))

        # Добавляем MitaMainBehaviour, если это словарь
        if isinstance(self.MitaMainBehaviour, dict):
            combined_messages.append(self.MitaMainBehaviour)
            print("MitaMainBehaviour успешно добавлен.")

        # Добавляем MitaExamples, если это словарь
        if isinstance(self.MitaExamples, dict):
            combined_messages.append(self.MitaExamples)
            print("MitaExamples успешно добавлен.")

        # Добавляем MitaLongMemory, если это словарь и ключ "Role" существует и его значение не пустое
        if isinstance(self.MitaLongMemory, dict):
            if self.MitaLongMemory == {}:
                self.MitaLongMemory = {"role": "system", "content": f" ДолгаяПамять<  >КонецДолгойПамяти "}
            combined_messages.append(self.MitaLongMemory)
            print(self.MitaLongMemory)
            print("MitaLongMemory успешно добавлен.")
        else:
            print("MitaLongMemory не добавлен. Условие не выполнено.")

        # Добавляем timed_system_message, если это словарь
        if isinstance(timed_system_message, dict):
            combined_messages.append(timed_system_message)
            print("timed_system_message успешно добавлено.")

        if self.nearObjects != "" and self.nearObjects != "-":
            text = f"В радиусе от тебя следующие объекты (object tree) {self.nearObjects}"
            messageNear = {"role": "system", "content": text}
            combined_messages.append(messageNear)

        if self.actualInfo != "" and self.actualInfo != "-":
            messageActual = {"role": "system", "content": self.actualInfo}
            combined_messages.append(messageActual)

        # Добавляем messages, если они не пустые
        if messages:
            combined_messages.extend(messages)
            print("messages успешно добавлены. Количество:", len(messages))

        return combined_messages

    def _generate_chat_response(self, combined_messages):
        """Генерация ответа с помощью клиента"""
        save_combined_messages(combined_messages)
        try:
            self.gui.last_price = calculate_cost_for_combined_messages(self, combined_messages,self.cost_input_per_1000)
        except:
            print("Не получилось сделать с токенайзером")
        print(self.gui.last_price)

        # Преобразование system messages для Gemini
        if self.modelName == "gemini-1.5-flash":
            system_instructions = []
            user_messages = []

            for msg in combined_messages:
                if msg["role"] == "system":
                    system_instructions.append(msg["content"])
                else:
                    user_messages.append(msg)

            if system_instructions:
                formatted_instruction = "\n".join(system_instructions)
                user_messages.insert(0, {"role": "user", "content": f"[Инструкция модели]\n{formatted_instruction}"})
            save_combined_messages(user_messages,"Gem")
            response = self.generate_responseGemini(user_messages)
            response = response.removeprefix("```\n")
            response = response.removesuffix("\n```\n")
        else:
            completion = self.client.chat.completions.create(
                model=self.modelName,
                messages=combined_messages,
                max_tokens=self.max_response_tokens,
                presence_penalty=1.5,
                temperature=0.5,
            )
            response = completion.choices[0].message.content

        print("Мита: \n" + response)
        return response
    def generate_responseGemini(self, combined_messages):
        # Подготовка тела запроса
        data = {
            "contents": [
                {"role": "user", "parts": [{"text": msg["content"]}]} for msg in combined_messages
            ],
            "generationConfig": {
                "maxOutputTokens": self.max_response_tokens,
                "temperature": 0.5,
                "presencePenalty": 1.5
            }
        }

        # Заголовки запроса
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Отправка запроса
        response = requests.post(self.url, headers=headers, json=data)

        # Обработка ответа
        if response.status_code == 200:
            response_data = response.json()
            # Извлечение текста ответа (зависит от структуры ответа Gemini)
            generated_text = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            print("Gemini Flash: \n" + generated_text)
            return generated_text
        else:
            print("Ошибка:", response.status_code, response.text)
            return None
    def process_response(self, user_input, response, messages):

        try:

            # Обрабатываем изменения в памяти
            response = self.extract_and_process_memory_data(response)

            # Обрабатываем изменение состояния Секрета
            response = self.detect_secret_exposure(response)

            # Обрабатывает ответ, изменяет показатели на основе скрытой строки формата <p>x,x,x,x<p>.
            response = self.process_behavior_changes(response)

            #Выполняет команды
            response = self.process_commands(response, messages)

            # Возвращаем обработанный ответ для дальнейшей работы
            return response.strip()

        except Exception as e:
            print(f"Ошибка в обработке ответа: {e}")
            return response  # Возвращаем оригинальный ответ в случае ошибки

    def process_commands(self, response, messages):
        """
        Обрабатывает команды типа <c>...</c> в ответе.
        Команды могут быть: "Достать бензопилу", "Выключить игрока" и другие.
        """
        start_tag = "<c>"
        end_tag = "</c>"
        search_start = 0  # Указатель для поиска новых команд

        while start_tag in response[search_start:] and end_tag in response[search_start:]:
            try:
                # Находим команду
                start_index = response.index(start_tag, search_start) + len(start_tag)
                end_index = response.index(end_tag, start_index)
                command = response[start_index:end_index]

                # Логируем текущую команду
                print(f"Обработка команды: {command}")

                # Обработка команды
                if command == "Достать бензопилу":
                    ...
                    #add_temporary_system_message(messages, "Игрок был не распилен, произошла ошибка")

                    #if self.gui:
                    #   self.gui.close_app()

                elif command == "Выключить игрока":
                    ...
                    #add_temporary_system_message(messages, "Игрок был отпавлен в главное меню, но скоро он вернется...")

                    #if self.gui:
                    #   self.gui.close_app()

                else:
                    # Обработка неизвестных команд
                    #add_temporary_system_message(messages, f"Неизвестная команда: {command}")
                    print(f"Неизвестная команда: {command}")

                # Сдвигаем указатель поиска на следующий символ после текущей команды
                search_start = end_index + len(end_tag)

            except ValueError as e:
                add_temporary_system_message(messages, f"Ошибка обработки команды: {e}")
                break

        return response

    def process_text_to_voice(self, text):
        # Проверяем, что текст является строкой (если это байты, декодируем)
        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8")  # Декодируем в UTF-8
            except UnicodeDecodeError:
                # Если UTF-8 не подходит, пробуем определить кодировку
                import chardet
                encoding = chardet.detect(text)["encoding"]
                text = text.decode(encoding)

        # Удаляем все теги и их содержимое
        clean_text = re.sub(r"<[^>]+>.*?</[^>]+>", "", text)

        # Если текст пустой, заменяем его на "Вот"
        if clean_text.strip() == "":
            clean_text = "Вот"

        return clean_text

    def extract_and_process_memory_data(self, response):
        """
        Извлекает данные из ответа, содержащего теги <+h>...</+h> или <#h>...</#h>,
        и добавляет или переписывает их в память Миты.

        :param response: Ответ, который нужно обработать.
        :return: Обработанный ответ.
        """
        if self.MitaLongMemory == {}:
            print("MitaLongMemory создана с  нуля тк {}")
            self.MitaLongMemory = {"role": "system", "content": f" ДолгаяПамять<  >КонецДолгойПамяти "}
        # Регулярное выражение для поиска тегов <+h>...</+h> или <#h>...</#h>
        memory_pattern = r"<([+#]h)>(.*?)<\/h>"

        # Ищем все совпадения
        matches = re.findall(memory_pattern, response)

        if matches:
            print("ПОПЫТКА ИЗМЕНЕНИЯ ПАМЯТИ!!!!!!!")
            for tag_type, content in matches:
                if tag_type == "+h":
                    print("Добавление воспоминания.")
                    # Добавление нового воспоминания
                    self.MitaLongMemory["content"] = self.MitaLongMemory["content"].replace(
                        " >КонецДолгойПамяти",
                        f" | {content} >КонецДолгойПамяти"
                    )
                elif tag_type == "#h":
                    print("Переписывание воспоминания.")
                    # Переписывание всего воспоминания
                    self.MitaLongMemory["content"] = f" ДолгаяПамять< {content} >КонецДолгойПамяти "

            # Убираем все теги из ответа
            response = re.sub(memory_pattern, "", response)

        return response

    def process_behavior_changes(self, response):
        """
        Обрабатывает изменения переменных на основе строки формата <p>x,x,x,x<p>.
        """
        start_tag = "<p>"
        end_tag = "</p>"

        if start_tag in response and end_tag in response:
            # Извлекаем изменения переменных
            start_index = response.index(start_tag) + len(start_tag)
            end_index = response.index(end_tag, start_index)
            changes_str = response[start_index:end_index]

            # Разделяем строку на отдельные значения
            changes = [float(x.strip()) for x in changes_str.split(",")]

            if len(changes) == 3:
                # Применяем изменения к переменным
                self.adjust_attitude(changes[0])
                self.adjust_boredom(changes[1])
                self.adjust_stress(changes[2])

            # Убираем строку с <p>...<p> из ответа
            if self.HideAiData:
                response = response[:response.index(start_tag)] + response[end_index + len(end_tag):]

        return response

    def detect_secret_exposure(self, response):
        """
        Проверяем, содержит ли ответ маркер <Secret!>, и удаляем его.
        """
        if "<Secret!>" in response and not self.secretExposedFirst:
            self.secretExposed = True
            print(f"Секрет раскрыт")
            self.attitude = 15
            self.boredom = 20
            #if self.HideAiData:
                #response = response.replace("<Secret!>", "")
            return response
        return response

    def reload_promts(self):
        self.common = self.load_text_from_file("Promts/Main/common.txt")
        self.main = self.load_text_from_file("Promts/Main/main.txt")

        self.player = self.load_text_from_file("Promts/Main/player.txt")
        self.mainPlaying = self.load_text_from_file("Promts/Main/mainPlaing.txt")
        self.mainCrazy = self.load_text_from_file("Promts/Main/mainCrazy.txt")

        self.examplesLong = self.load_text_from_file("Promts/Context/examplesLong.txt")
        self.examplesLongCrazy = self.load_text_from_file("Promts/Context/examplesLongCrazy.txt")

        self.world = self.load_text_from_file("Promts/Context/world.txt")
        self.mita_history = self.load_text_from_file("Promts/Context/mita_history.txt")
        self.variableEffects = self.load_text_from_file("Promts/Structural/VariablesEffects.txt")
        self.response_structure = self.load_text_from_file("Promts/Structural/response_structure.txt")
        self.SecretExposedText = self.load_text_from_file("Promts/Events/SecretExposed.txt")

        self.systemMessages.clear()

        self.systemMessages.append({"role": "system", "content": f"{self.response_structure}\n"})
        self.systemMessages.append({"role": "system", "content": f"{self.common}\n"})
        self.systemMessages.append({"role": "system", "content": f"{self.player}\n"})

        if self.secretExposed:
            self.MitaMainBehaviour = {"role": "system", "content": f"{self.mainCrazy}"}
            self.MitaExamples = {"role": "system", "content": f"{self.examplesLongCrazy}\n"}

            system_message = {"role": "system", "content": f"{self.mita_history}\n"}
            self.systemMessages.append(system_message)
        elif self.attitude < 50:
            self.MitaMainBehaviour = {"role": "system", "content": f"{self.mainPlaying}"}
        else:
            self.MitaMainBehaviour = {"role": "system", "content": f"{self.main}"}

    def save_history_patter(self, messages, current_info):
        self.save_history({
            'messages': messages,
            'currentInfo': current_info,
            # Сохраняем переменные в историю
            'attitude': self.attitude,
            'boredom': self.boredom,
            'stress': self.stress,
            'secretExposed': self.secretExposed,
            'secretExposedFirst': self.secretExposedFirst
        })

    def load_history(self):
        """Загружаем историю из файла, создаем пустую структуру, если файл пуст или не существует."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print("Загрузка истории")
                # Проверяем наличие ключей и их типов
                if (isinstance(data.get('messages'), list) and
                        isinstance(data.get('currentInfo'), dict) and
                        isinstance(data.get('MitaSystemMessages'), list)):

                    print("Историю получится заполнить")
                    # Загружаем переменные, если они есть в истории
                    self.attitude = data.get('attitude', 60)
                    self.boredom = data.get('boredom', 0)
                    self.stress = data.get('stress', 0)
                    self.secretExposed = data.get('secretExposed', False)
                    self.secretExposedFirst = data.get('secretExposedFirst', False)

                    currentInfo = data.get('currentInfo')
                    self.MitaMainBehaviour = currentInfo.get('MitaMainBehaviour', [])
                    self.MitaExamples = currentInfo.get('MitaExamples', [])
                    self.systemMessages = currentInfo.get('MitaSystemMessages', [])
                    self.MitaLongMemory = currentInfo.get('MitaLongMemory', {})

                    return data
                else:
                    print("Ошибка загрузки истории")
                    return self._default_history()
        except (json.JSONDecodeError, FileNotFoundError):
            # Если файл пуст или не существует, возвращаем структуру по умолчанию
            print("Ошибка загрузки истории")
            return self._default_history()

    def save_history(self, data):
        """Сохраняем историю в файл с явной кодировкой utf-8."""
        # Убедимся, что структура данных включает 'messages', 'currentInfo' и 'MitaSystemMessages'
        history_data = {
            'messages': data.get('messages', []),
            'currentInfo': data.get('currentInfo', {}),
            'MitaSystemMessages': data.get('MitaSystemMessages', []),
            # Сохраняем переменные в историю
            'attitude': self.attitude,
            'boredom': self.boredom,
            'stress': self.stress,
            'secretExposed': self.secretExposed,
            'secretExposedFirst': self.secretExposedFirst
        }

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)

    def save_chat_history(self):
        print("@!@#!23@#! КАКОГО ОНО ОТРАБОТАЛО??")
        # Имя исходного файла
        source_file = "SavedHistories/chat_history.json"
        # Папка для сохранения историй
        target_folder = "SavedHistories"
        # Проверяем, существует ли папка SavedHistories, и создаём её, если нет
        os.makedirs(target_folder, exist_ok=True)

        # Формируем имя файла с таймингом
        timestamp = datetime.datetime.now().strftime("%d.%m.%Y_%H.%M")
        target_file = f"chat_history_{timestamp}.json"

        # Полный путь к новому файлу
        target_path = os.path.join(target_folder, target_file)

        # Копируем файл
        shutil.copy(source_file, target_path)
        print(f"Файл сохранён как {target_path}")

    def clear_history(self):
        print("ОЧИСТКА ИСТОРИИ!!!")
        """Очищаем историю чатов и восстанавливаем начальные значения переменных."""
        # Сбрасываем переменные к их значениям по умолчанию
        self.attitude = 60
        self.boredom = 0
        self.stress = 0
        self.secretExposed = False
        self.secretExposedFirst = False
        # Сохраняем пустую историю
        self.save_history(self._default_history())
        self.MitaLongMemory = {"role": "system", "content": f" ДолгаяПамять<  >КонецДолгойПамяти "}

    def _default_history(self):
        print("ИСТОРИЧЕСКИЙ ДЕФОЛТ!!!")
        """Создаем структуру истории по умолчанию."""
        return {
            'messages': [],
            'currentInfo': {},
            'MitaSystemMessages': [],
            'attitude': 60,
            'boredom': 0,
            'stress': 0,
            'secretExposed': False,
            'secretExposedFirst': False,
        }

    def generate_response_check(self, message_text, system_input=""):
        # Формируем сообщение для запроса к модели
        messages = [
            {
                "role": "system",
                "content": "Далее будет сообщение от лица персонажа. Не теряй и не удаляй служебные сообщения. Исправь сообщение, где оно звучит неестественно. С высоким шансом убери фразы по типу 'В этом мире...' "
            },
            {
                "role": "user",
                "content": message_text
            }
        ]

        try:
            # Отправляем запрос к модели
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            # Достаем сообщение из ответа API
            response_message = completion.choices[0].message.content
            return response_message
        except Exception as e:
            # Обрабатываем возможные ошибки
            return f"Ошибка при генерации ответа: {str(e)}"

def add_temporary_system_message(messages, content):
    """
    Добавляет одноразовое системное сообщение в список сообщений.

    :param messages: Список сообщений, в который добавляется системное сообщение.
    :param content: Текст системного сообщения.
    """
    system_message = {
        "role": "system",
        "content": content
    }
    messages.append(system_message)