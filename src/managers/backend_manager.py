from __future__ import annotations

import os
from typing import Optional

from core.backends import Backend, normalize_backend, vendor_to_backend
from core.install_types import InstallAction, InstallCallbacks, InstallPlan
from main_logger import logger
from managers.settings_manager import SettingsManager
from utils.gpu_utils import check_gpu_provider
from utils.pip_installer import PipInstaller


class BackendManager:
    CUDA_TORCH_PACKAGES = ["torch==2.7.1+cu128", "torchvision", "torchaudio"]
    CUDA_EXTRA_ARGS = ["--index-url", "https://download.pytorch.org/whl/cu128"]

    ONNX_TORCH_PACKAGES = ["torch", "torchvision", "torchaudio"]
    ONNX_TORCH_EXTRA_ARGS = ["--index-url", "https://download.pytorch.org/whl/cpu"]
    ONNX_RUNTIME_PACKAGES = ["onnxruntime-directml", "onnx", "numpy<2"]

    _detected_backend: Optional[Backend] = None

    @classmethod
    def _libs_dir(cls) -> str:
        return os.environ.get("NEUROMITA_LIB_DIR", os.path.abspath("Lib"))

    @classmethod
    def _marker_path(cls) -> str:
        return os.path.join(cls._libs_dir(), ".backend")

    @classmethod
    def detect(cls) -> Backend:
        if cls._detected_backend is None:
            cls._detected_backend = vendor_to_backend(check_gpu_provider())
        return cls._detected_backend

    @classmethod
    def active(cls) -> Backend:
        forced = normalize_backend(
            os.environ.get("NEUROMITA_ACTIVE_BACKEND")
            or os.environ.get("ACTIVE_BACKEND")
            or os.environ.get("BACKEND")
        )
        if forced is not None:
            return forced

        saved = normalize_backend(SettingsManager.get("ACTIVE_BACKEND"))
        if saved is not None:
            return saved

        marked = cls.current_backend_from_marker()
        return marked or cls.detect()

    @classmethod
    def current_backend_from_marker(cls) -> Backend | None:
        marker = cls._marker_path()
        if not os.path.exists(marker):
            return None
        try:
            with open(marker, "r", encoding="utf-8") as f:
                return normalize_backend(f.read().strip())
        except Exception as ex:
            logger.warning(f"Failed to read backend marker: {ex}")
            return None

    @classmethod
    def desired_specs(cls, backend: Backend | str | None = None) -> set[str]:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        if resolved == Backend.CUDA:
            return set(cls.CUDA_TORCH_PACKAGES)
        return set(cls.ONNX_TORCH_PACKAGES) | set(cls.ONNX_RUNTIME_PACKAGES)

    @classmethod
    def _write_marker_action(cls, backend: Backend, *, persist_setting: bool = False) -> InstallAction:
        def _write(**_kwargs) -> bool:
            marker = cls._marker_path()
            os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(backend.value)
            if persist_setting:
                SettingsManager.set("ACTIVE_BACKEND", backend.value)
            return True

        return InstallAction(
            type="call",
            description=f"Activating backend: {backend.value}",
            progress=95,
            fn=_write,
            backend=backend,
        )

    @classmethod
    def _install_actions(cls, backend: Backend) -> list[InstallAction]:
        if backend == Backend.CUDA:
            return [
                InstallAction(
                    type="pip",
                    description="Installing PyTorch CUDA 12.8",
                    progress=15,
                    packages=list(cls.CUDA_TORCH_PACKAGES),
                    extra_args=list(cls.CUDA_EXTRA_ARGS),
                    backend=backend,
                ),
                cls._write_marker_action(backend),
            ]

        return [
            InstallAction(
                type="pip",
                description="Installing ONNX runtime + CPU PyTorch",
                progress=15,
                packages=list(cls.ONNX_TORCH_PACKAGES),
                extra_args=list(cls.ONNX_TORCH_EXTRA_ARGS),
                backend=backend,
            ),
            InstallAction(
                type="pip",
                description="Installing ONNX Runtime DirectML",
                progress=55,
                packages=list(cls.ONNX_RUNTIME_PACKAGES),
                backend=backend,
            ),
            cls._write_marker_action(backend),
        ]

    @classmethod
    def build_install_plan(cls, backend: Backend | str | None = None, *, force: bool = False) -> InstallPlan:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        current = cls.current_backend_from_marker()
        if not force and current == resolved:
            return InstallPlan(actions=[], already_installed=True, already_installed_status=f"{resolved.value} already active")
        if force or current not in (None, resolved):
            return cls.build_switch_plan(current, resolved)
        return InstallPlan(actions=cls._install_actions(resolved), ok_status=f"{resolved.value} ready")

    @classmethod
    def build_switch_plan(
        cls,
        old_backend: Backend | str | None,
        new_backend: Backend | str | None,
        *,
        persist_setting: bool = False,
    ) -> InstallPlan:
        old_resolved = normalize_backend(old_backend)
        new_resolved = normalize_backend(new_backend, cls.active()) or cls.active()

        actions: list[InstallAction] = []
        if old_resolved == Backend.CUDA and new_resolved == Backend.ONNX:
            actions.append(
                InstallAction(
                    type="call",
                    description="Removing CUDA backend packages",
                    progress=5,
                    fn=lambda *, pip_installer=None, **_kwargs: bool(
                        pip_installer and pip_installer.uninstall_packages(
                            ["torch", "torchvision", "torchaudio"],
                            description="Removing CUDA backend packages",
                        )
                    ),
                )
            )
        elif old_resolved == Backend.ONNX and new_resolved == Backend.CUDA:
            actions.append(
                InstallAction(
                    type="call",
                    description="Removing ONNX backend packages",
                    progress=5,
                    fn=lambda *, pip_installer=None, **_kwargs: bool(
                        pip_installer and pip_installer.uninstall_packages(
                            ["onnxruntime-directml", "onnx", "torch", "torchvision", "torchaudio"],
                            description="Removing ONNX backend packages",
                        )
                    ),
                )
            )

        actions.extend(cls._install_actions(new_resolved)[:-1])
        actions.append(cls._write_marker_action(new_resolved, persist_setting=persist_setting))
        return InstallPlan(actions=actions, ok_status=f"{new_resolved.value} ready")

    @classmethod
    def build_activate_plan(cls, backend: Backend | str | None) -> InstallPlan:
        target = normalize_backend(backend, cls.active()) or cls.active()
        return cls.build_switch_plan(cls.current_backend_from_marker(), target, persist_setting=True)

    @classmethod
    def _run_plan(cls, plan: InstallPlan, *, callbacks: InstallCallbacks | None = None, use_cache: bool | None = None) -> bool:
        cb = callbacks or InstallCallbacks(
            progress=lambda *_: None,
            status=lambda s: logger.info(str(s)),
            log=lambda m: logger.info(str(m)),
        )
        pip_installer = PipInstaller(update_status=cb.status, update_log=cb.log, update_progress=cb.progress)
        use_cache = bool(SettingsManager.get("PKG_USE_CACHE", False) if use_cache is None else use_cache)

        if plan.already_installed:
            cb.status(plan.already_installed_status)
            cb.progress(100)
            return True

        for action in plan.actions or []:
            if action.description:
                cb.status(action.description)
            if action.progress:
                cb.progress(int(action.progress))

            if action.type == "pip":
                ok = pip_installer.install_package(
                    action.packages or [],
                    description=action.description or "Installing packages",
                    extra_args=action.extra_args,
                    use_cache=use_cache,
                )
            elif action.type == "call" and callable(action.fn):
                ok = action.fn(pip_installer=pip_installer, callbacks=cb, ctx={"required_backend": action.backend})
            else:
                ok = False

            if ok is False:
                return False

        cb.progress(100)
        cb.status(plan.ok_status or "Done")
        return True

    @classmethod
    def ensure_backend(
        cls,
        backend: Backend | str | None = None,
        *,
        callbacks: InstallCallbacks | None = None,
        use_cache: bool | None = None,
    ) -> bool:
        target = normalize_backend(backend, cls.active()) or cls.active()
        current = cls.current_backend_from_marker()
        if current == target:
            return True

        if current is None:
            libs_dir = cls._libs_dir()
            has_torch_dist = False
            if os.path.isdir(libs_dir):
                has_torch_dist = any(name.startswith("torch-") and name.endswith(".dist-info") for name in os.listdir(libs_dir))
            if has_torch_dist:
                marker = cls._marker_path()
                os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(target.value)
                SettingsManager.set("ACTIVE_BACKEND", target.value)
                return True

        return cls._run_plan(cls.build_switch_plan(current, target, persist_setting=True), callbacks=callbacks, use_cache=use_cache)
