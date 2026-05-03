from __future__ import annotations

import os
from typing import Optional
import glob

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from core.backends import Backend, normalize_backend, vendor_to_backend
from core.install_types import InstallAction, InstallCallbacks, InstallPlan
from main_logger import logger
from managers.settings_manager import SettingsManager
from utils.gpu_utils import check_gpu_provider
from utils.pip_installer import PipInstaller


class BackendManager:
    CUDA_CORE_PACKAGES = ["onnxruntime"]
    CUDA_TORCH_PACKAGES = ["torch==2.7.1+cu128", "torchvision", "torchaudio"]
    CUDA_EXTRA_ARGS = ["--index-url", "https://download.pytorch.org/whl/cu128"]

    ONNX_TORCH_PACKAGES = ["torch", "torchvision", "torchaudio"]
    ONNX_TORCH_EXTRA_ARGS = ["--index-url", "https://download.pytorch.org/whl/cpu"]
    ONNX_CORE_PACKAGES = ["onnxruntime-directml", "onnx", "numpy<2"]

    _detected_backend: Optional[Backend] = None

    @classmethod
    def _libs_dir(cls) -> str:
        return os.environ.get("NEUROMITA_LIB_DIR", os.path.abspath("Lib"))

    @classmethod
    def _marker_path(cls) -> str:
        return os.path.join(cls._libs_dir(), ".backend")

    @classmethod
    def _installed_package_names(cls) -> set[str]:
        libs_dir = cls._libs_dir()
        if not os.path.isdir(libs_dir):
            return set()

        installed: set[str] = set()
        for name in os.listdir(libs_dir):
            if not name.endswith(".dist-info"):
                continue
            try:
                dist_name = name.split("-")[0]
                installed.add(canonicalize_name(dist_name))
            except Exception:
                continue
        return installed

    @classmethod
    def _core_specs(cls, backend: Backend) -> list[str]:
        if backend == Backend.CUDA:
            return list(cls.CUDA_CORE_PACKAGES)
        return list(cls.ONNX_CORE_PACKAGES)

    @classmethod
    def _model_specs(cls, backend: Backend) -> list[str]:
        if backend == Backend.CUDA:
            return list(cls.CUDA_TORCH_PACKAGES)
        return list(cls.ONNX_TORCH_PACKAGES)

    @classmethod
    def _full_specs(cls, backend: Backend) -> list[str]:
        return cls._core_specs(backend) + cls._model_specs(backend)

    @classmethod
    def _spec_names_for_backend(cls, backend: Backend, *, include_models: bool = True) -> set[str]:
        specs = cls._full_specs(backend) if include_models else cls._core_specs(backend)
        names: set[str] = set()
        for spec in specs:
            try:
                names.add(canonicalize_name(Requirement(spec).name))
            except Exception:
                raw = str(spec or "").split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].strip()
                if raw:
                    names.add(canonicalize_name(raw))
        return names

    @classmethod
    def _spec_name(cls, spec: str) -> str:
        try:
            return canonicalize_name(Requirement(spec).name)
        except Exception:
            raw = str(spec or "").split("[", 1)[0].split("=", 1)[0].split("<", 1)[0].strip()
            return canonicalize_name(raw) if raw else ""

    @classmethod
    def _missing_specs(cls, specs: list[str]) -> list[str]:
        installed = cls._installed_package_names()
        missing: list[str] = []
        for spec in specs:
            name = cls._spec_name(spec)
            if name and name not in installed:
                missing.append(spec)
        return missing

    @classmethod
    def _installed_torch_variant(cls) -> Optional[str]:
        libs_dir = cls._libs_dir()
        if os.path.isdir(libs_dir):
            matches = glob.glob(os.path.join(libs_dir, "torch-*.dist-info"))
            if matches:
                matches.sort(key=os.path.getmtime, reverse=True)
                dist_name = os.path.basename(matches[0])
                version = dist_name[len("torch-"):-len(".dist-info")]
                return "cuda" if "+cu" in version else "cpu"
        return None

    @classmethod
    def _torch_install_mode(cls, backend: Backend) -> str:
        installed = cls._installed_torch_variant()
        if backend == Backend.CUDA:
            if installed == "cuda":
                return "skip"
            if installed == "cpu":
                return "reinstall"
            return "install"
        if installed is None:
            return "install"
        return "skip"

    @classmethod
    def is_backend_ready(cls, backend: Backend | str | None = None, *, include_models: bool = True) -> bool:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        required = cls._spec_names_for_backend(resolved, include_models=include_models)
        installed = cls._installed_package_names()
        return required.issubset(installed)

    @classmethod
    def is_backend_core_ready(cls, backend: Backend | str | None = None) -> bool:
        return cls.is_backend_ready(backend, include_models=False)

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
        return set(cls._full_specs(resolved))

    @classmethod
    def desired_core_specs(cls, backend: Backend | str | None = None) -> set[str]:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        return set(cls._core_specs(resolved))

    @classmethod
    def _conflicting_runtime_packages(cls, backend: Backend) -> list[str]:
        installed = cls._installed_package_names()
        if backend == Backend.CUDA:
            return ["onnxruntime-directml"] if "onnxruntime-directml" in installed else []
        return ["onnxruntime"] if "onnxruntime" in installed else []

    @classmethod
    def _guess_conflicting_backend(cls, backend: Backend) -> Backend:
        return Backend.ONNX if backend == Backend.CUDA else Backend.CUDA

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
    def _install_actions(cls, backend: Backend, *, include_models: bool = True) -> list[InstallAction]:
        actions: list[InstallAction] = []
        core_missing = cls._missing_specs(cls._core_specs(backend))

        if core_missing:
            actions.append(
                InstallAction(
                    type="pip",
                    description="Installing ONNX Runtime" if backend == Backend.CUDA else "Installing ONNX Runtime DirectML",
                    progress=10 if include_models else 20,
                    packages=list(core_missing),
                    backend=backend,
                )
            )

        if include_models:
            model_missing = cls._missing_specs(cls._model_specs(backend))
            torch_name = cls._spec_name("torch")
            non_torch_missing = [spec for spec in model_missing if cls._spec_name(spec) != torch_name]
            torch_mode = cls._torch_install_mode(backend)

            if torch_mode == "reinstall":
                actions.append(
                    InstallAction(
                        type="call",
                        description="Removing existing PyTorch packages",
                        progress=35 if backend == Backend.CUDA else 45,
                        fn=lambda *, pip_installer=None, **_kwargs: bool(
                            pip_installer and pip_installer.uninstall_packages(
                                ["torch", "torchvision", "torchaudio"],
                                description="Removing existing PyTorch packages",
                                include_dependencies=False,
                            )
                        ),
                    )
                )

            torch_packages: list[str] = []
            if torch_mode in ("install", "reinstall"):
                torch_packages = list(cls._model_specs(backend))
            elif non_torch_missing:
                torch_packages = list(non_torch_missing)

            if torch_packages:
                actions.append(
                    InstallAction(
                        type="pip",
                        description="Installing PyTorch CUDA 12.8" if backend == Backend.CUDA else "Installing CPU PyTorch",
                        progress=45 if backend == Backend.CUDA else 55,
                        packages=torch_packages,
                        extra_args=list(cls.CUDA_EXTRA_ARGS) if backend == Backend.CUDA else list(cls.ONNX_TORCH_EXTRA_ARGS),
                        backend=backend,
                    )
                )

        actions.append(cls._write_marker_action(backend))
        return actions

    @classmethod
    def _core_activate_actions(cls, backend: Backend, *, persist_setting: bool = False) -> list[InstallAction]:
        actions = cls._install_actions(backend, include_models=False)
        if actions:
            actions[-1] = cls._write_marker_action(backend, persist_setting=persist_setting)
        return actions

    @classmethod
    def build_install_plan(cls, backend: Backend | str | None = None, *, force: bool = False) -> InstallPlan:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        current = cls.current_backend_from_marker()
        if not force and current == resolved and cls.is_backend_ready(resolved):
            return InstallPlan(actions=[], already_installed=True, already_installed_status=f"{resolved.value} already active")
        if force or current not in (None, resolved) or cls._conflicting_runtime_packages(resolved):
            switch_from = current if current not in (None, resolved) else cls._guess_conflicting_backend(resolved)
            return cls.build_switch_plan(switch_from, resolved)
        return InstallPlan(actions=cls._install_actions(resolved, include_models=True), ok_status=f"{resolved.value} ready")

    @classmethod
    def build_core_install_plan(
        cls,
        backend: Backend | str | None = None,
        *,
        force: bool = False,
        persist_setting: bool = False,
    ) -> InstallPlan:
        resolved = normalize_backend(backend, cls.active()) or cls.active()
        current = cls.current_backend_from_marker()
        if not force and current == resolved and cls.is_backend_core_ready(resolved):
            return InstallPlan(actions=[], already_installed=True, already_installed_status=f"{resolved.value} core already active")
        if force or current not in (None, resolved) or cls._conflicting_runtime_packages(resolved):
            switch_from = current if current not in (None, resolved) else cls._guess_conflicting_backend(resolved)
            return cls.build_core_switch_plan(switch_from, resolved, persist_setting=persist_setting)
        return InstallPlan(
            actions=cls._core_activate_actions(resolved, persist_setting=persist_setting),
            ok_status=f"{resolved.value} core ready",
        )

    @classmethod
    def build_core_switch_plan(
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
                    description="Removing CUDA runtime packages",
                    progress=5,
                    fn=lambda *, pip_installer=None, **_kwargs: bool(
                        pip_installer and pip_installer.uninstall_packages(
                            ["onnxruntime"],
                            description="Removing CUDA runtime packages",
                            include_dependencies=False,
                        )
                    ),
                )
            )
        elif old_resolved == Backend.ONNX and new_resolved == Backend.CUDA:
            actions.append(
                InstallAction(
                    type="call",
                    description="Removing ONNX runtime packages",
                    progress=5,
                    fn=lambda *, pip_installer=None, **_kwargs: bool(
                        pip_installer and pip_installer.uninstall_packages(
                            ["onnxruntime-directml"],
                            description="Removing ONNX runtime packages",
                            include_dependencies=False,
                        )
                    ),
                )
            )

        actions.extend(cls._core_activate_actions(new_resolved)[:-1])
        actions.append(cls._write_marker_action(new_resolved, persist_setting=persist_setting))
        return InstallPlan(actions=actions, ok_status=f"{new_resolved.value} core ready")

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
                            ["onnxruntime", "torch", "torchvision", "torchaudio"],
                            description="Removing CUDA backend packages",
                            include_dependencies=False,
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
                            include_dependencies=False,
                        )
                    ),
                )
            )

        actions.extend(cls._install_actions(new_resolved, include_models=True)[:-1])
        actions.append(cls._write_marker_action(new_resolved, persist_setting=persist_setting))
        return InstallPlan(actions=actions, ok_status=f"{new_resolved.value} ready")

    @classmethod
    def build_activate_plan(cls, backend: Backend | str | None) -> InstallPlan:
        target = normalize_backend(backend, cls.active()) or cls.active()
        return cls.build_core_install_plan(target, persist_setting=True)

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
        if current == target and cls.is_backend_ready(target):
            return True

        if current is None:
            libs_dir = cls._libs_dir()
            has_torch_dist = False
            if os.path.isdir(libs_dir):
                has_torch_dist = any(name.startswith("torch-") and name.endswith(".dist-info") for name in os.listdir(libs_dir))
            if has_torch_dist and cls.is_backend_ready(target):
                marker = cls._marker_path()
                os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
                with open(marker, "w", encoding="utf-8") as f:
                    f.write(target.value)
                SettingsManager.set("ACTIVE_BACKEND", target.value)
                return True

        return cls._run_plan(cls.build_switch_plan(current, target, persist_setting=True), callbacks=callbacks, use_cache=use_cache)

    @classmethod
    def ensure_backend_core(
        cls,
        backend: Backend | str | None = None,
        *,
        callbacks: InstallCallbacks | None = None,
        use_cache: bool | None = None,
    ) -> bool:
        target = normalize_backend(backend, cls.active()) or cls.active()
        current = cls.current_backend_from_marker()
        if current == target and cls.is_backend_core_ready(target):
            return True

        if cls.is_backend_core_ready(target):
            marker = cls._marker_path()
            os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(target.value)
            SettingsManager.set("ACTIVE_BACKEND", target.value)
            return True

        return cls._run_plan(
            cls.build_core_install_plan(target, persist_setting=True),
            callbacks=callbacks,
            use_cache=use_cache,
        )
