from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from utils import _
from core.events import Events
from ui.settings.api_settings.dialogs.models_loaded_dialog import ModelsLoadedDialog
from handlers.llm_providers.chatgpt_plan_auth import get_chatgpt_plan_auth
from .bus_async import bus_call_async


_CHATGPT_PLAN_TEMPLATE_ID = 12


class TestMixin:
    def _test_connection(self) -> None:
        v = self.view
        base_id = v.template_combo.currentData()
        try:
            base_id = int(base_id) if base_id is not None else None
        except Exception:
            base_id = None

        if not self.current_preset_id and not base_id:
            QMessageBox.warning(
                v,
                _("Предупреждение", "Warning"),
                _("Выберите пресет или шаблон для тестирования", "Select a preset or template to test"),
            )
            return

        v.test_button.setEnabled(False)
        v.test_button.setProperty("apiTesting", True)
        v.test_button.setText(_("Проверка…", "Checking…"))

        if base_id == _CHATGPT_PLAN_TEMPLATE_ID:
            self._sign_in_chatgpt_plan()
            return

        self.event_bus.emit(Events.ApiPresets.TEST_CONNECTION, {
            "id": self.current_preset_id,
            "base": base_id,
            "key": v.api_key_row.text(),
        })

    def _sign_in_chatgpt_plan(self) -> None:
        preset_id = self.current_preset_id

        def run():
            auth = get_chatgpt_plan_auth()
            status = auth.sign_in()
            model_infos = auth.list_models()
            email = str(status.get("email") or "ChatGPT")
            return {
                "id": preset_id,
                "success": True,
                "message": _(
                    "Вход выполнен: {email}. Найдено моделей: {count}",
                    "Signed in: {email}. Models found: {count}",
                ).format(email=email, count=len(model_infos)),
                "models": [str(item.get("id") or "") for item in model_infos if item.get("id")],
                "model_infos": model_infos,
            }

        def failed(exc):
            self._process_test_failed({
                "id": preset_id,
                "message": _(
                    "Не удалось войти через ChatGPT: {error}",
                    "Could not sign in with ChatGPT: {error}",
                ).format(error=str(exc)),
            })

        bus_call_async(
            run,
            self._process_test_result,
            failed,
            name="chatgpt-plan-sign-in",
            dispatch=self._dispatch_to_gui,
        )

    def _on_test_result(self, event):
        data = event.data or {}
        if data.get("id") != self.current_preset_id:
            return
        self.test_result_received.emit(dict(data))

    def _on_test_failed(self, event):
        data = event.data or {}
        if data.get("id") != self.current_preset_id:
            return
        self.test_result_failed.emit(dict(data))

    def _reset_test_button(self):
        v = self.view
        v.test_button.setEnabled(True)
        v.test_button.setProperty("apiTesting", False)
        if bool(v.test_button.property("chatgptPlan")):
            v.test_button.setText(_("Войти через ChatGPT", "Continue with ChatGPT"))
        else:
            v.test_button.setText(_("Проверить", "Check"))

    def _process_test_result(self, data: dict):
        v = self.view
        self._reset_test_button()

        success = bool(data.get("success"))
        msg = str(data.get("message") or (_("Успешно", "Success") if success else _("Неизвестная ошибка", "Unknown error")))
        models = data.get("models") or []
        model_infos = data.get("model_infos") or []
        if not isinstance(models, list):
            models = []
        if not isinstance(model_infos, list):
            model_infos = []

        # нормализуем список
        cleaned: list[str] = []
        seen = set()
        for m in models:
            s = str(m or "").strip()
            if s and s not in seen:
                seen.add(s)
                cleaned.append(s)

        if success and cleaned:
            try:
                v.api_model_list_model.setStringList(cleaned)
            except Exception:
                pass

            try:
                dlg = ModelsLoadedDialog(v, models=cleaned, model_infos=model_infos, message=msg)
                if dlg.exec() == dlg.DialogCode.Accepted:
                    chosen = dlg.selected_model()
                    if chosen:
                        v.api_model_row.set_text(chosen)
                        try:
                            self._on_field_changed()
                        except Exception:
                            pass
                return
            except Exception:
                QMessageBox.information(v, _("Результат тестирования", "Test Result"), msg + "\n\n" + "\n".join(cleaned))
                return

        if success:
            QMessageBox.information(v, _("Результат тестирования", "Test Result"), msg)
        else:
            QMessageBox.warning(v, _("Ошибка подключения", "Connection Error"), msg)

    def _process_test_failed(self, data: dict):
        self._reset_test_button()
        msg = str(data.get("message") or _("Неизвестная ошибка", "Unknown error"))
        QMessageBox.warning(self.view, _("Ошибка тестирования", "Test Error"), msg)
