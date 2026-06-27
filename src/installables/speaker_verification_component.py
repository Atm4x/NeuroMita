"""
Installable-компонент «Распознавание спикера» для AI Hub (раздел ASR).

Ставит Resemblyzer (VoiceEncoder) — лёгкую модель d-vector эмбеддингов голоса,
которой пользуется handlers/asr_models/speaker_verifier.py, чтобы засчитывать
только голос пользователя и не реагировать на голос Миты из колонок.

Веса модели идут внутри пакета resemblyzer, поэтому «установка» = pip install;
отдельной загрузки артефактов нет. torch тянется как зависимость, но в среде, где
работают нейронные ASR-движки (Venv / ai_engine), он уже есть.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from core.backends import BackendKind
from core.install_types import InstallAction, InstallPlan
from core.installables import (
    ComponentCategory,
    ComponentMetadata,
    ComponentStatus,
    make_component_id,
)
from core.installables.helpers import build_runtime_ctx, noop_plan, status_from_installed
from utils import getTranslationVariant as _


class SpeakerVerificationInstallable:
    """Компонент AI Hub категории ASR (не распознаватель — отдельная фича)."""

    category = ComponentCategory.ASR
    legacy_kind = "asr"
    item_id = "speaker_verification"

    @property
    def id(self) -> str:
        return make_component_id(self.category, self.item_id)

    def _is_installed(self) -> bool:
        try:
            return importlib.util.find_spec("resemblyzer") is not None
        except Exception:
            return False

    def metadata(self) -> ComponentMetadata:
        return ComponentMetadata(
            id=self.id,
            item_id=self.item_id,
            category=self.category,
            title=_("Распознавание спикера (мой голос)", "Speaker verification (my voice)"),
            description=_(
                "Засчитывать только голос пользователя: отсекает голос Миты из колонок, "
                "телевизор и посторонних. Нужен один раз записать образец своего голоса. "
                "Работает с нейронными ASR-движками (GigaAM/Whisper).",
                "Recognize only the user's voice: filters out Mita's voice from the speakers, "
                "TV and bystanders. Requires a one-time voice enrollment. "
                "Works with neural ASR engines (GigaAM/Whisper).",
            ),
            backend=BackendKind.NONE,
            legacy_kind=self.legacy_kind,
            tags=(_("Голос", "Voice"), _("Нейросеть", "Neural")),
        )

    def status(self, ctx: dict[str, Any] | None = None) -> ComponentStatus:
        return status_from_installed(
            component_id=self.id,
            installed=self._is_installed(),
            backend=BackendKind.NONE,
            ctx=build_runtime_ctx(ctx),
        )

    def build_install_plan(self, ctx: dict[str, Any] | None = None) -> InstallPlan:
        run_ctx = build_runtime_ctx(ctx)
        if self._is_installed() and not run_ctx.get("clean"):
            return InstallPlan(actions=[], already_installed=True, already_installed_status="Already installed")

        actions = [
            InstallAction(
                type="pip",
                description=_("Установка Resemblyzer...", "Installing Resemblyzer..."),
                progress=70,
                packages=["resemblyzer"],
            ),
            InstallAction(
                type="call",
                description=_("Проверка...", "Finalizing..."),
                progress=99,
                fn=lambda **_kwargs: self._is_installed(),
            ),
        ]
        return InstallPlan(actions=actions, already_installed=False, ok_status="Done")

    def build_uninstall_plan(self, ctx: dict[str, Any] | None = None) -> InstallPlan:
        return noop_plan("Speaker verification uninstall is not implemented yet.")

    def build_initialize_plan(self, ctx: dict[str, Any] | None = None) -> InstallPlan | None:
        return None


def create_speaker_verification_components() -> list:
    return [SpeakerVerificationInstallable()]
