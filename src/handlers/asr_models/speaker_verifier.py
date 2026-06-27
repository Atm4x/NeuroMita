"""
Верификация спикера по голосу (speaker verification).

Назначение: отличать голос пользователя от чужого — в первую очередь от
собственного голоса Миты, который доносится из колонок и попадает в микрофон,
а также от телевизора/других людей в комнате. В отличие от тайм-гейта
(SpeechController._is_mita_speaking) этот механизм работает и при перебивании
(barge-in): пользователь может говорить поверх Миты, и его всё равно засчитают.

Как работает:
  1. Энроллмент — один раз считаем эмбеддинг голоса пользователя и сохраняем
     в Settings/speaker_profile.json (референс).
  2. На каждую распознанную фразу считаем эмбеддинг сегмента и сравниваем с
     референсом по косинусной близости. Если ниже порога — не наш голос.

Модель — Resemblyzer (VoiceEncoder, ECAPA-подобные d-vector эмбеддинги). Веса
идут внутри пакета, отдельной загрузки артефактов не требуется. Считаем на CPU,
чтобы не конкурировать с ASR за видеопамять — на фразу это единицы/десятки мс.

ВАЖНО: модуль рассчитан на запуск в процессе ai_engine-воркера (где есть torch).
Во встроенном python игры (libs/python без torch) недоступен — это нормально,
верификация просто отключается (см. is_available()).

Все методы максимально оборонительны: при любой неудаче возвращаем None и НЕ
блокируем распознавание (лучше пропустить фразу, чем молча съесть речь юзера).
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

import numpy as np


def _profile_path() -> str:
    return os.path.join("Settings", "speaker_profile.json")


class SpeakerVerifier:
    # Порог косинусной близости по умолчанию. Для Resemblyzer тот же спикер
    # обычно даёт 0.8+, разные голоса — около 0.4–0.6. 0.70 — разумный старт.
    DEFAULT_THRESHOLD = 0.70

    # Слишком короткий сегмент не даёт надёжный эмбеддинг — на таких не гейтим.
    MIN_SECONDS = 0.6

    def __init__(self, threshold: float = DEFAULT_THRESHOLD, logger=None):
        self.threshold = float(threshold or self.DEFAULT_THRESHOLD)
        self.logger = logger
        self._encoder = None
        self._reference: Optional[np.ndarray] = None
        self._reference_loaded = False

    # ——— доступность / готовность
    @staticmethod
    def is_available() -> bool:
        """Можно ли вообще считать эмбеддинги (установлен ли resemblyzer + torch)."""
        try:
            import importlib.util
            return importlib.util.find_spec("resemblyzer") is not None
        except Exception:
            return False

    def _ensure_encoder(self) -> bool:
        if self._encoder is not None:
            return True
        try:
            from resemblyzer import VoiceEncoder
            # CPU намеренно: эмбеддинг быстрый, а GPU занят ASR-моделью.
            self._encoder = VoiceEncoder("cpu", verbose=False)
            return True
        except Exception as e:
            self._log("error", f"SpeakerVerifier: не удалось загрузить VoiceEncoder: {e}")
            return False

    # ——— эмбеддинг
    def embed(self, audio: np.ndarray, sample_rate: int) -> Optional[np.ndarray]:
        if audio is None:
            return None
        try:
            wav = np.asarray(audio, dtype=np.float32).reshape(-1)
        except Exception:
            return None

        if sample_rate <= 0 or wav.size < int(self.MIN_SECONDS * sample_rate):
            return None

        if not self._ensure_encoder():
            return None

        try:
            from resemblyzer import preprocess_wav
            processed = preprocess_wav(wav, source_sr=int(sample_rate))
            if processed is None or len(processed) == 0:
                return None
            emb = self._encoder.embed_utterance(processed)
            emb = np.asarray(emb, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(emb))
            if norm <= 0:
                return None
            return emb / norm
        except Exception as e:
            self._log("warning", f"SpeakerVerifier.embed error: {e}")
            return None

    # ——— энроллмент (референс пользователя)
    def is_enrolled(self) -> bool:
        return self._load_reference() is not None

    def enroll(self, audio: np.ndarray, sample_rate: int) -> bool:
        """Добавить образец голоса в референс. Повторные вызовы усредняют
        эмбеддинги (можно «доучить» профиль несколькими фразами)."""
        emb = self.embed(audio, sample_rate)
        if emb is None:
            return False

        existing = self._load_reference()
        samples = 1
        try:
            if os.path.exists(_profile_path()):
                with open(_profile_path(), "r", encoding="utf-8") as f:
                    prev = json.load(f)
                samples = int(prev.get("samples", 1)) if isinstance(prev, dict) else 1
        except Exception:
            samples = 1

        if existing is not None:
            merged = existing * samples + emb
            norm = float(np.linalg.norm(merged))
            if norm > 0:
                emb = merged / norm
            samples += 1

        return self._save_reference(emb, samples)

    def reset(self) -> bool:
        self._reference = None
        self._reference_loaded = False
        try:
            if os.path.exists(_profile_path()):
                os.remove(_profile_path())
            return True
        except Exception as e:
            self._log("warning", f"SpeakerVerifier.reset error: {e}")
            return False

    # ——— проверка
    def score(self, audio: np.ndarray, sample_rate: int) -> Optional[float]:
        """Косинусная близость сегмента к референсу (None — решить нельзя)."""
        ref = self._load_reference()
        if ref is None:
            return None
        emb = self.embed(audio, sample_rate)
        if emb is None:
            return None
        return float(np.dot(ref, emb))

    def accept(self, audio: np.ndarray, sample_rate: int) -> Optional[bool]:
        """True — наш голос, False — чужой, None — решить нельзя (не гейтить)."""
        s = self.score(audio, sample_rate)
        if s is None:
            return None
        return s >= self.threshold

    # ——— persistence
    def _load_reference(self) -> Optional[np.ndarray]:
        if self._reference_loaded:
            return self._reference
        self._reference_loaded = True
        try:
            path = _profile_path()
            if not os.path.exists(path):
                self._reference = None
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            vec = np.asarray((data or {}).get("embedding", []), dtype=np.float32).reshape(-1)
            if vec.size == 0:
                self._reference = None
                return None
            norm = float(np.linalg.norm(vec))
            self._reference = vec / norm if norm > 0 else None
        except Exception as e:
            self._log("warning", f"SpeakerVerifier: не удалось прочитать профиль: {e}")
            self._reference = None
        return self._reference

    def _save_reference(self, emb: np.ndarray, samples: int) -> bool:
        try:
            path = _profile_path()
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            payload = {
                "embedding": [float(x) for x in emb.tolist()],
                "dim": int(emb.size),
                "samples": int(samples),
                "created": time.time(),
            }
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, path)
            self._reference = emb
            self._reference_loaded = True
            return True
        except Exception as e:
            self._log("error", f"SpeakerVerifier: не удалось сохранить профиль: {e}")
            return False

    def _log(self, level: str, msg: str):
        if self.logger is not None:
            try:
                getattr(self.logger, level, self.logger.info)(msg)
                return
            except Exception:
                pass


def profile_exists() -> bool:
    """Дешёвая проверка (для GUI/основного процесса) — есть ли референс на диске."""
    try:
        return os.path.exists(_profile_path()) and os.path.getsize(_profile_path()) > 0
    except Exception:
        return False
