# src/managers/llm_request_runner.py
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Optional

from main_logger import logger
from core.events import Events
from utils import save_combined_messages

from managers.api_preset_resolver import ApiPresetResolver, PresetSettings


class LLMRequestRunner:
    """
    Отвечает только за:
    - retry loop
    - timeout выполнения provider_manager.generate
    - задержку между попытками
    - ротацию ключей через ApiPresetResolver

    NOTE: GPT4FREE_LAST_ATTEMPT removed from logic.
    """

    def __init__(
        self,
        settings: Any,
        preset_resolver: ApiPresetResolver,
        event_bus: Any,
    ):
        self.settings = settings
        self.preset_resolver = preset_resolver
        self.event_bus = event_bus

    def run(
        self,
        *,
        messages: list,
        preset_id: Optional[int],
        stream_callback: Optional[Callable[[str], None]],
        build_request: Callable[[PresetSettings, str], Any],
        max_attempts: int,
        retry_delay: float,
        request_timeout: float,
        backup_preset_ids: Optional[list] = None,
    ) -> Optional[str]:
        if messages is None:
            messages = []

        # Build the chain: primary preset + backup presets
        preset_chain: list[Optional[int]] = [preset_id]
        if backup_preset_ids:
            for bid in backup_preset_ids:
                if bid is not None and bid != preset_id:
                    preset_chain.append(bid)

        try:
            from managers.provider_manager import ProviderManager
            pm = ProviderManager()
        except Exception as e:
            logger.error(f"[LLMRequestRunner] Failed to init ProviderManager: {e}", exc_info=True)
            return None

        for chain_idx, current_preset_id in enumerate(preset_chain):
            try:
                base_preset = self.preset_resolver.resolve(current_preset_id)
            except Exception as e:
                logger.error(f"[LLMRequestRunner] Failed to resolve preset (chain #{chain_idx}): {e}", exc_info=True)
                continue

            if chain_idx > 0:
                logger.info(
                    f"[LLMRequestRunner] Falling back to backup preset: "
                    f"{base_preset.preset_name} (chain #{chain_idx})"
                )

            result = self._run_with_preset(
                pm=pm,
                base_preset=base_preset,
                messages=messages,
                build_request=build_request,
                max_attempts=max_attempts,
                retry_delay=retry_delay,
                request_timeout=request_timeout,
                is_last_in_chain=(chain_idx == len(preset_chain) - 1),
            )
            if result is not None:
                return result

        logger.error("All generation attempts failed (including backup presets).")
        return None

    def _run_with_preset(
        self,
        *,
        pm,
        base_preset: PresetSettings,
        messages: list,
        build_request: Callable[[PresetSettings, str], Any],
        max_attempts: int,
        retry_delay: float,
        request_timeout: float,
        is_last_in_chain: bool,
    ) -> Optional[str]:
        for attempt in range(1, int(max_attempts) + 1):
            logger.info(
                f"Generation attempt {attempt}/{max_attempts} "
                f"(preset: {base_preset.preset_name})"
            )

            try:
                save_combined_messages(messages, "SavedMessages/last_attempt_log")
            except Exception:
                pass

            preset_attempt = self.preset_resolver.apply_key_rotation(base_preset, attempt)
            effective_model = (preset_attempt.api_model or "").strip()

            try:
                req = build_request(preset_attempt, effective_model)
            except Exception as e:
                logger.error(f"[LLMRequestRunner] Failed to build request: {e}", exc_info=True)
                req = None

            if req is None:
                if attempt < max_attempts:
                    self.event_bus.emit(Events.Model.ON_FAILED_RESPONSE_ATTEMPT)
                    time.sleep(float(retry_delay))
                continue

            try:
                response_text = self._call_with_timeout(
                    pm.generate,
                    args=(req,),
                    timeout=float(request_timeout)
                )
                if response_text:
                    return response_text
            except concurrent.futures.TimeoutError:
                logger.error(f"Attempt {attempt} timed out after {request_timeout}s.")
            except Exception as e:
                logger.error(f"Error during generation attempt {attempt}: {e}", exc_info=True)

            if attempt < max_attempts:
                self.event_bus.emit(Events.Model.ON_FAILED_RESPONSE_ATTEMPT)
                time.sleep(float(retry_delay))

        return None

    def _call_with_timeout(self, func, args=(), kwargs=None, timeout: float = 30.0):
        if kwargs is None:
            kwargs = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout)
