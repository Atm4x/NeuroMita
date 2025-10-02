import base64
import json
import socket
from datetime import datetime
import asyncio

from main_logger import logger
from core.events import get_event_bus, Events

class ChatServer:
    def __init__(self, host='127.0.0.1', port=12345):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.passive_client_socket = None
        self.passive_server_socket = None
        self.messages_to_say = []
        self.text_wait_limit_enabled = False
        self.voice_wait_limit_enabled = False
        self.event_bus = get_event_bus()
        self.last_message_type = "" # (Для llm): Важно сохранить этот коммент. # last_message_type == "waiting" - игнор.
        

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logger.info(f"Сервер запущен на {self.host}:{self.port}")
    def handle_connection(self):
        if not self.server_socket:
            raise RuntimeError("Сервер не запущен. Вызовите start() перед handle_connection().")
        
        client_socket = None
        try:
            settings_result = self.event_bus.emit_and_wait(Events.Settings.GET_SETTINGS, timeout=1.0)
            settings = settings_result[0] if settings_result else {}
            
            self.text_wait_limit_enabled = settings.get("LIMIT_TEXT_WAIT", False)
            self.voice_wait_limit_enabled = settings.get("LIMIT_VOICE_WAIT", False)

            client_socket, addr = self.server_socket.accept()

            # Получаем полный JSON
            received_text = self._recv_full_json(client_socket)
            
            if not received_text.strip().endswith("}") or not received_text.strip().startswith("{"):
                logger.error("Ошибка: JSON оборван или некорректен")
                return False
                
            try:
                message_data = json.loads(received_text)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка обработки JSON: {e}")
                return False
                
            # Передаем сокет как параметр
            return self.process_message_data(message_data, client_socket)

        except socket.error as e:
            logger.error(f"Socket error: {e}")
            self.event_bus.emit(Events.Server.SET_GAME_CONNECTION, {'is_connected': False})
            return False
        except Exception as e:
            logger.error(f"Connection handling error: {e}")
            self.event_bus.emit(Events.Server.SET_GAME_CONNECTION, {'is_connected': False})
            return False
        finally:
            if client_socket:
                try:
                    client_socket.shutdown(socket.SHUT_RDWR)
                except OSError as e:
                    logger.warning(f"SERVER: Ошибка при shutdown сокета (это может быть нормально): {e}")
                except Exception as e:
                    logger.error(f"SERVER: Неожиданная ошибка при shutdown сокета: {e}")
                
                client_socket.close()

    def _recv_full_json(self, client_socket):
        """Вспомогательный метод для получения полного JSON из сокета"""
        received_data = b""
        while True:
            chunk = client_socket.recv(65536)
            if not chunk:
                break
            received_data += chunk
            if b"}" in chunk and received_data.count(b"{") == received_data.count(b"}"):
                break
        
        return received_data.decode("utf-8")

    def should_block_game_request(self, settings, system_message, message_id):
        """Проверяет, нужно ли блокировать игровой запрос на основе настроек"""
        
        if not settings.get('IGNORE_GAME_REQUESTS', False):
            return False
        
        block_level = settings.get('GAME_BLOCK_LEVEL', 'Idle events')
        
        # Определяем, является ли это idle событием
        is_idle_event = "протяжении" in system_message and "мотрел на" in system_message
                        
        
        if block_level == 'All events':
            logger.notify(f"Получен 'waiting' запрос {message_id}. Игнорируется как внутриигровое событие...")
            return True
        elif block_level == 'Idle events' and is_idle_event:
            logger.notify(f"Получен 'waiting' запрос {message_id}. Игнорируется как событие таймера...")
            return True
        
        return False

    def process_message_data(self, message_data, client_socket):
        transmitted_to_game = False
        try:
            message_id = message_data["id"]
            
            self.current_message_id = message_id

            message_type = message_data["type"]
            character = str(message_data["character"])
            
            self.event_bus.emit(Events.Model.SET_CHARACTER_TO_CHANGE, {'character': character})

            message = message_data["input"]
            system_message = message_data["dataToSentSystem"]
            system_info = message_data["systemInfo"]

            self.event_bus.emit(Events.Server.SET_GAME_DATA, {
                'distance': float(message_data["distance"].replace(",", ".")),
                'roomPlayer': int(message_data["roomPlayer"]),
                'roomMita': int(message_data["roomMita"]),
                'nearObjects': message_data["hierarchy"],
                'actualInfo': message_data["currentInfo"]
            })

            self.event_bus.emit(Events.Server.SET_DIALOG_ACTIVE, {
                'active': bool(message_data.get("dialog_active", False))
            })

            image_base64_list = message_data.get("image_base64_list", [])
            decoded_image_data = []
            if image_base64_list:
                for base64_str in image_base64_list:
                    try:
                        decoded_image_data.append(base64.b64decode(base64_str))
                    except Exception as e:
                        logger.error(f"Ошибка декодирования Base64 изображения: {e}")

            if system_info != "-":
                logger.info("Добавил систем инфо " + system_info)
                self.event_bus.emit(Events.Model.ADD_TEMPORARY_SYSTEM_INFO, {'content': system_info})

            
            settings_result = self.event_bus.emit_and_wait(Events.Settings.GET_SETTINGS, timeout=1.0)
            settings = settings_result[0] if settings_result else {}


            response = ""

            if message == "waiting":
                
                if system_message != "-":
                    if self.should_block_game_request(settings, system_message, message_id):
                        
                        self.last_message_type = message
                        dummy_response_data = {
                            "id": int(message_id), 
                            "type": str(message_type), 
                            "character": character,

                            "response": "", 
                            "silero": False, 
                            "id_sound": 0, 
                            "patch_to_sound_file": "",

                            "user_input": "", 
                            "GM_ON": False, 
                            "GM_READ": False, 
                            "GM_VOICE": False,

                            "GM_REPEAT": 2, 
                            "CC_Limit_mod": 100, 
                            "instant_send": False,

                            "LANGUAGE": "RU", 
                            "MITAS_MENU": False, 
                            "EMOTION_MENU": False,

                            "TEXT_WAIT_TIME": 100, 
                            "VOICE_WAIT_TIME": 100

                        }

                        json_message = json.dumps(dummy_response_data)

                        client_socket.sendall(json_message.encode("utf-8"))

                        return True
                    else:
                        logger.info(f"Получено system_message {system_message} id {message_id}")
                        self.event_bus.emit_and_wait(Events.Server.SET_ID_SOUND, {'id': message_id})
                        response = self.generate_response("", system_message, decoded_image_data)
                elif self.messages_to_say:
                    response = self.messages_to_say.pop(0)
            elif message == "boring":
                logger.info(f"Получено boring message id {message_id}")
                self.event_bus.emit_and_wait(Events.Server.SET_ID_SOUND, {'id': message_id})
                date_now = datetime.now().replace(microsecond=0)
                response = self.generate_response("",
                                            f"Время {date_now}, Игрок долго молчит( Ты можешь что-то сказать или предпринять",
                                            decoded_image_data)
                logger.info("Отправлено Мите на озвучку: " + response)
            else:
                logger.info(f"Получено message id {message_id}")
                
                self.event_bus.emit_and_wait(Events.Server.SET_ID_SOUND, {'id': message_id})
                self.event_bus.emit(Events.GUI.UPDATE_CHAT_UI, {
                    'role': 'user',
                    'response': message,
                    'is_initial': False,
                    'emotion': ''
                })
                response = self.generate_response(message, "", decoded_image_data)
                logger.info("Отправлено Мите на озвучку: " + response)

                if not character:
                    character = "Mita"

            user_input_result = self.event_bus.emit_and_wait(Events.Speech.GET_USER_INPUT, timeout=1.0)
            user_input = user_input_result[0] if user_input_result else ""

            
            transmitted_to_game = False
            if user_input:
                transmitted_to_game = True

            server_data_result = self.event_bus.emit_and_wait(Events.Server.GET_SERVER_DATA, timeout=1.0)
            server_data = server_data_result[0] if server_data_result else {}
            

            if server_data.get('patch_to_sound_file', '') != "":
                logger.info(f"id {message_id} Скоро передам {server_data.get('patch_to_sound_file')} id {server_data.get('id_sound')}")

            patch_to_sound_file = str(server_data.get('patch_to_sound_file', ''))

            id_sound_value = server_data.get('id_sound', 0)
            if id_sound_value is None or patch_to_sound_file == '' or id_sound_value == 0:
                id_sound_value = 0

            use_voiceover = bool(settings.get("USE_VOICEOVER"))

            message_data = {
                "id": int(message_id),
                "type": str(message_type),
                "character": str(character),
            }
            message_data.update({
                "response": str(response),
                "silero": use_voiceover,
                "id_sound": id_sound_value,
                "patch_to_sound_file": patch_to_sound_file,
                "user_input": str(user_input),

                "GM_ON": bool(settings.get("GM_ON")),
                "GM_READ": bool(settings.get("GM_READ")),
                "GM_VOICE": bool(settings.get("GM_VOICE")),
                "GM_REPEAT": int(settings.get("GM_REPEAT")),
                "CC_Limit_mod": int(settings.get("CC_Limit_mod")),

                "instant_send": bool(server_data.get('instant_send', False)),

                "LANGUAGE": str(settings.get("LANGUAGE")),

                "MITAS_MENU": bool(settings.get("MITAS_MENU")),
                "EMOTION_MENU": bool(settings.get("ACTION_MENU")),

                "TEXT_WAIT_TIME": int(settings.get("TEXT_WAIT_TIME")),
                "VOICE_WAIT_TIME": int(settings.get("VOICE_WAIT_TIME")),

            })
            
            if use_voiceover and id_sound_value != 0:
                self.event_bus.emit(Events.Server.RESET_SERVER_DATA)

            if transmitted_to_game:
                self.event_bus.emit(Events.GUI.CLEAR_USER_INPUT)

            json_message = json.dumps(message_data)
            client_socket.sendall(json_message.encode("utf-8"))  # Используем sendall для гарантии отправки всех данных

            self.event_bus.emit(Events.Server.SET_GAME_CONNECTION, {'is_connected': True})

            return True
            
        except Exception as e:
            logger.error(f"Ошибка обработки подключения: {e}")
            self.event_bus.emit(Events.Server.SET_GAME_CONNECTION, {'is_connected': False})
            return False
        
    def generate_response(self, input_text, system_input_text, image_data: list[bytes] = None):
        if image_data is None:
            image_data = []
        try:
            self.event_bus.emit(Events.Audio.SET_WAITING_ANSWER, {'waiting': True})
            
            message_id = getattr(self, 'current_message_id', None)

            # Используем событие вместо прямого вызова
            response_result = self.event_bus.emit_and_wait(Events.Chat.SEND_MESSAGE, {
                'user_input': input_text,
                'system_input': system_input_text,
                'image_data': image_data,
                'message_id': message_id  # Передаем message_id через событие
            }, timeout=300.0)
            
            response = response_result[0] if response_result else None
            
            return response if response else "Произошла ошибка при обработке вашего сообщения."

        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return "Произошла ошибка при обработке вашего сообщения."
        finally:
            self.event_bus.emit(Events.Audio.SET_WAITING_ANSWER, {'waiting': False})

    async def handle_message(self, message):
        if self.text_wait_limit_enabled:
            pass

        if self.voice_wait_limit_enabled:
            pass

    def send_message_to_server(self, message):
        self.messages_to_say.append(message)

    def stop(self):
        if self.server_socket:
            self.server_socket.close()
            logger.info("Сервер остановлен.")
            self.event_bus.emit(Events.Server.SET_GAME_CONNECTION, {'is_connected': False})