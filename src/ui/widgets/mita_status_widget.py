import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QSize, pyqtProperty, QSequentialAnimationGroup
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from utils.translation_manager import t

class AnimatedDots(QWidget):
    """Виджет с анимированными точками (как в мессенджерах)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 20)
        
        self.dot_count = 3
        self.dot_size = 4
        self.dot_spacing = 6
        self.current_dot = 0
        self.animation_step = 0
        
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_dots)
        
        self.smooth_timer = QTimer()
        self.smooth_timer.timeout.connect(self._smooth_animation)
        
    def _animate_dots(self):
        self.current_dot = (self.current_dot + 1) % self.dot_count
        self.animation_step = 0
        self.update()
        
    def _smooth_animation(self):
        self.animation_step += 1
        self.update()
        if self.animation_step >= 10:
            self.animation_step = 0
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        total_width = self.dot_count * self.dot_size + (self.dot_count - 1) * self.dot_spacing
        start_x = (self.width() - total_width) // 2
        y = self.height() // 2
        
        for i in range(self.dot_count):
            x = start_x + i * (self.dot_size + self.dot_spacing)
            
            if i == self.current_dot:
                scale_factor = 1.0 + 0.5 * abs(5 - self.animation_step) / 5.0
                size = int(self.dot_size * scale_factor)
                color = QColor("#7a7a7a")
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(x - size//2 + self.dot_size//2, 
                                   y - size//2, size, size)
            else:
                painter.setBrush(QBrush(QColor("#4a4a4a")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(x, y - self.dot_size//2, 
                                   self.dot_size, self.dot_size)
    
    def stop_animation(self):
        self.animation_timer.stop()
        self.smooth_timer.stop()
        
    def start_animation(self):
        self.animation_timer.start(600)
        self.smooth_timer.start(60)


class MitaStatusWidget(QWidget):
    """Виджет статуса Миты - overlay поверх чата"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_state = "idle"
        self.is_animating = False
        self._pulse_intensity = 0.0
        self.normal_bg = QColor(45, 45, 45, 200)
        self.error_bg = QColor(74, 40, 40, 220)
        self.normal_border = QColor(74, 74, 74, 150)
        self.error_border = QColor(138, 48, 48, 180)
        self.normal_text = QColor(160, 160, 160, 180)
        self.error_text = QColor(255, 107, 107, 200)
        self.setup_ui()
        self.hide()
        
    def setup_ui(self):
        self.setObjectName("MitaStatusWidget")
        self.setFixedHeight(40)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        self.dots_widget = AnimatedDots()
        layout.addWidget(self.dots_widget)
        
        # Добавляем label для иконки
        self.icon_label = QLabel()
        self.icon_label.hide()
        layout.addWidget(self.icon_label)
        
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._apply_normal_style()
        
    @pyqtProperty(float)
    def pulseIntensity(self):
        return self._pulse_intensity

    @pulseIntensity.setter
    def pulseIntensity(self, value):
        self._pulse_intensity = value
        self.set_pulse_intensity(value)
        
    def set_pulse_intensity(self, factor):
        bg = self._interpolate_color(self.normal_bg, self.error_bg, factor)
        border = self._interpolate_color(self.normal_border, self.error_border, factor)
        text = self._interpolate_color(self.normal_text, self.error_text, factor)
        
        self.setStyleSheet(f"""
            #MitaStatusWidget {{
                background-color: {self._color_to_rgba(bg)};
                border: 1px solid {self._color_to_rgba(border)};
                border-radius: 8px;
                margin: 0px;
            }}
        """)
        
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {self._color_to_rgba(text)};
                font-size: 10pt;
                background: transparent;
                font-weight: 400;
            }}
        """)
        
    def _interpolate_color(self, c1, c2, factor):
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * factor),
            int(c1.green() + (c2.green() - c1.green()) * factor),
            int(c1.blue() + (c2.blue() - c1.blue()) * factor),
            int(c1.alpha() + (c2.alpha() - c1.alpha()) * factor)
        )
    
    def _color_to_rgba(self, c):
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"
        
    def _apply_normal_style(self):
        self.setStyleSheet("""
            #MitaStatusWidget {
                background-color: rgba(45, 45, 45, 200);
                border: 1px solid rgba(74, 74, 74, 150);
                border-radius: 8px;
                margin: 0px;
            }
        """)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(160, 160, 160, 180);
                font-size: 10pt;
                background: transparent;
                font-weight: 400;
            }
        """)
        
    def _apply_error_style(self):
        self.setStyleSheet("""
            #MitaStatusWidget {
                background-color: rgba(74, 40, 40, 220);
                border: 1px solid rgba(138, 48, 48, 180);
                border-radius: 8px;
                margin: 0px;
            }
        """)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 107, 107, 200);
                font-size: 10pt;
                font-weight: 500;
                background: transparent;
            }
        """)
        
    def _apply_success_style(self):
        self.setStyleSheet("""
            #MitaStatusWidget {
                background-color: rgba(42, 56, 42, 220);
                border: 1px solid rgba(74, 106, 74, 180);
                border-radius: 8px;
                margin: 0px;
            }
        """)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(76, 175, 80, 200);
                font-size: 10pt;
                font-weight: 500;
                background: transparent;
            }
        """)
        
    def _disconnect_fade_signal(self):
        try:
            self.fade_animation.finished.disconnect()
        except TypeError:
            pass
        
    def show_thinking(self, character_name="Мита"):
        if self.current_state == "thinking" and self.isVisible() and self.opacity_effect.opacity() > 0.5:
            return
            
        if hasattr(self, 'pulse_anim'):
            self.pulse_anim.stop()
        self.set_pulse_intensity(0.0)
            
        self.current_state = "thinking"
        self.is_animating = False
        
        self.fade_animation.stop()
        self._disconnect_fade_signal()
        
        self._apply_normal_style()
        
        # Скрываем иконку
        self.icon_label.hide()
        
        self.status_label.setText(_(f"{character_name} думает...", f"{character_name} is thinking..."))
        self.dots_widget.show()
        self.dots_widget.start_animation()
        
        self.show()
        self.raise_()
        self.opacity_effect.setOpacity(0.0)
        
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        
    def show_error(self, error_message=_("Произошла ошибка", "Error occurred")):
        if hasattr(self, 'pulse_anim'):
            self.pulse_anim.stop()
        self.set_pulse_intensity(0.0)
        
        self.current_state = "error"
        self.is_animating = False
        
        self.fade_animation.stop()
        self._disconnect_fade_signal()
        
        self._apply_error_style()
        
        # Устанавливаем иконку ошибки
        error_icon = qta.icon('fa5s.exclamation-triangle', color='#ff6b6b')  # Красный
        # Альтернативные варианты:
        # error_icon = qta.icon('fa5s.exclamation-triangle', color='#ffeb3b')  # Желтый
        # error_icon = qta.icon('fa5s.exclamation-triangle', color='#ffffff')  # Белый
        
        pixmap = error_icon.pixmap(16, 16)
        self.icon_label.setPixmap(pixmap)
        self.icon_label.show()
        
        self.status_label.setText(error_message)
        self.dots_widget.hide()
        self.dots_widget.stop_animation()
        
        self.show()
        self.raise_()
        self.opacity_effect.setOpacity(0.0)
        
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        
        QTimer.singleShot(5000, self.hide_animated)
        
    def show_success(self, message=_("Готово", "success")):
        if hasattr(self, 'pulse_anim'):
            self.pulse_anim.stop()
        self.set_pulse_intensity(0.0)
        
        self.current_state = "success"
        self.is_animating = False
        
        self.fade_animation.stop()
        self._disconnect_fade_signal()
        
        self._apply_success_style()
        
        # Устанавливаем иконку успеха
        success_icon = qta.icon('fa5s.check-circle', color='#4caf50')  # Зеленый
        pixmap = success_icon.pixmap(16, 16)
        self.icon_label.setPixmap(pixmap)
        self.icon_label.show()
        
        self.status_label.setText(message)
        self.dots_widget.hide()
        self.dots_widget.stop_animation()
        
        self.show()
        self.raise_()
        self.opacity_effect.setOpacity(0.0)
        
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
        
        QTimer.singleShot(2000, self.hide_animated)
        
    def pulse_error_animation(self):
        if self.current_state != "thinking" or not self.isVisible():
            return

        if hasattr(self, 'pulse_anim'):
            self.pulse_anim.stop()
        
        self.pulse_anim = QSequentialAnimationGroup()
        
        fade_in = QPropertyAnimation(self, b"pulseIntensity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        fade_out = QPropertyAnimation(self, b"pulseIntensity")
        fade_out.setDuration(400)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InQuad)
        
        self.pulse_anim.addAnimation(fade_in)
        self.pulse_anim.addPause(200)
        self.pulse_anim.addAnimation(fade_out)
        
        self.pulse_anim.start()

    def _revert_to_thinking_style(self):
        if self.current_state != "thinking":
            return
        self._apply_normal_style()

    def hide_animated(self):
        if self.current_state == "idle" or self.is_animating:
            return
        
        if hasattr(self, 'pulse_anim'):
            self.pulse_anim.stop()
        self.set_pulse_intensity(0.0)
            
        self.current_state = "idle"
        self.is_animating = True
        self.dots_widget.stop_animation()
        
        self.fade_animation.stop()
        self._disconnect_fade_signal()
        
        current_opacity = self.opacity_effect.opacity()
        self.fade_animation.setStartValue(current_opacity)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._on_hide_finished)
        
        self.fade_animation.start()
        
    def _on_hide_finished(self):
        self.hide()
        self.is_animating = False
        self._disconnect_fade_signal()