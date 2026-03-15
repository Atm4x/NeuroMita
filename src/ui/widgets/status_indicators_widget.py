from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCheckBox
from PyQt6.QtCore import Qt
from utils.translation_manager import t

def create_status_indicators(gui, parent_layout):
    status_frame = QWidget()
    status_layout = QHBoxLayout(status_frame)
    status_layout.setContentsMargins(0, 0, 0, 0)
    status_layout.setSpacing(15) # Увеличим расстояние между индикаторами
    status_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def create_indicator(text):
        checkbox = QCheckBox(text)
        checkbox.setObjectName("StatusIndicator")
        checkbox.setEnabled(False) # Нельзя кликать
        checkbox.setStyleSheet("color: #ffffff; spacing: 5px;") # Уменьшим расстояние между галкой и текстом
        return checkbox

    gui.game_status_checkbox = create_indicator(t('ui.widgets.status_indicators.game'))
    status_layout.addWidget(gui.game_status_checkbox)

    gui.silero_status_checkbox = create_indicator(t('ui.widgets.status_indicators.telegram'))
    status_layout.addWidget(gui.silero_status_checkbox)

    gui.mic_status_checkbox = create_indicator(t('ui.widgets.status_indicators.recognition'))
    status_layout.addWidget(gui.mic_status_checkbox)

    gui.screen_capture_status_checkbox = create_indicator(t('ui.widgets.status_indicators.screen_capture'))
    status_layout.addWidget(gui.screen_capture_status_checkbox)

    gui.camera_capture_status_checkbox = create_indicator(t('ui.widgets.status_indicators.camera'))
    status_layout.addWidget(gui.camera_capture_status_checkbox)
    
    status_layout.addStretch() # Добавляем растяжение, чтобы индикаторы не занимали всю ширину

    parent_layout.addWidget(status_frame)
    
    gui.update_status_colors()

def create_status_indicators_inline(gui, layout):
    """Создает статус индикаторы для верхней панели чата"""
    def create_indicator(text):
        checkbox = QCheckBox(text)
        checkbox.setObjectName("StatusIndicator")
        checkbox.setEnabled(False)
        checkbox.setStyleSheet("color: #ffffff; spacing: 5px;")
        return checkbox

    gui.game_status_checkbox = create_indicator(t('ui.widgets.status_indicators.game'))
    layout.addWidget(gui.game_status_checkbox)

    gui.silero_status_checkbox = create_indicator(t('ui.widgets.status_indicators.telegram'))
    layout.addWidget(gui.silero_status_checkbox)

    gui.mic_status_checkbox = create_indicator(t('ui.widgets.status_indicators.recognition'))
    layout.addWidget(gui.mic_status_checkbox)

    gui.screen_capture_status_checkbox = create_indicator(t('ui.widgets.status_indicators.screen_capture'))
    layout.addWidget(gui.screen_capture_status_checkbox)

    gui.camera_capture_status_checkbox = create_indicator(t('ui.widgets.status_indicators.camera'))
    layout.addWidget(gui.camera_capture_status_checkbox)
    
    gui.update_status_colors()