from main_logger import logger
from core.events import Event
from utils.translation_manager import t
from .base_controller import BaseController

class ViewEventController(BaseController):
    def subscribe_to_events(self):
        self.event_bus.subscribe("history_loaded", self._on_history_loaded_event, weak=False)
        self.event_bus.subscribe("more_history_loaded", self._on_more_history_loaded_event, weak=False)
        self.event_bus.subscribe("model_initialized", self._on_model_initialized_event, weak=False)
        self.event_bus.subscribe("model_init_cancelled", self._on_model_init_cancelled_event, weak=False)
        self.event_bus.subscribe("model_init_failed", self._on_model_init_failed_event, weak=False)
        self.event_bus.subscribe("reload_prompts_success", self._on_reload_prompts_success_event, weak=False)
        self.event_bus.subscribe("reload_prompts_failed", self._on_reload_prompts_failed_event, weak=False)
        self.event_bus.subscribe("display_loading_popup", self._on_display_loading_popup_event, weak=False)
        self.event_bus.subscribe("hide_loading_popup", self._on_hide_loading_popup_event, weak=False)
        
    def _on_history_loaded_event(self, event: Event):
        logger.debug(t("controllers.view_event.history_loaded"))
        if self.view:
            self.view.history_loaded_signal.emit(event.data)
    
    def _on_more_history_loaded_event(self, event: Event):
        logger.debug(t("controllers.view_event.more_history_loaded"))
        if self.view:
            self.view.more_history_loaded_signal.emit(event.data)
    
    def _on_model_initialized_event(self, event: Event):
        logger.debug(t("controllers.view_event.model_initialized"))
        if self.view:
            self.view.model_initialized_signal.emit(event.data)
    
    def _on_model_init_cancelled_event(self, event: Event):
        logger.debug(t("controllers.view_event.model_init_cancelled"))
        if self.view:
            self.view.model_init_cancelled_signal.emit(event.data)
    
    def _on_model_init_failed_event(self, event: Event):
        logger.debug(t("controllers.view_event.model_init_failed"))
        if self.view:
            self.view.model_init_failed_signal.emit(event.data)
    
    def _on_reload_prompts_success_event(self, event: Event):
        logger.debug(t("controllers.view_event.reload_prompts_success"))
        if self.view:
            self.view.reload_prompts_success_signal.emit()
    
    def _on_reload_prompts_failed_event(self, event: Event):
        logger.debug(t("controllers.view_event.reload_prompts_failed"))
        if self.view:
            self.view.reload_prompts_failed_signal.emit(event.data)
    
    def _on_display_loading_popup_event(self, event: Event):
        logger.debug(t("controllers.view_event.display_loading_popup"))
        if self.view:
            self.view.display_loading_popup_signal.emit(event.data)
    
    def _on_hide_loading_popup_event(self, event: Event):
        logger.debug(t("controllers.view_event.hide_loading_popup"))
        if self.view:
            self.view.hide_loading_popup_signal.emit()