from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout

from localization.live import register, tr_set
from styles.theme import THEME
from utils import _


class SubscriptionInfo(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName('ApiSubscriptionInfo')
        self.setStyleSheet(
            f'QFrame#ApiSubscriptionInfo {{ border: 1px solid {THEME["panel_border"]}; '
            'border-radius: 10px; }'
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        self.cache_notice = QLabel()
        self.cache_notice.setWordWrap(True)
        self.cache_notice.setStyleSheet(f'color: {THEME["warn_text"]};')
        layout.addWidget(self.cache_notice)
        register(self.cache_notice, lambda label: label.setText(_(*(
            label.property('noticeText') or ('', '')
        ))))
        self.limit_bars = []
        for ru, en in (
            ('Краткосрочный лимит (часы)', 'Short-term limit (hours)'),
            ('Недельный лимит', 'Weekly limit'),
        ):
            layout.addWidget(tr_set(QLabel(), ru, en))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setEnabled(False)
            bar.setMinimumHeight(24)
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tr_set(bar, 'Данные недоступны', 'Data unavailable', 'setFormat')
            tr_set(bar, ru, en, 'setAccessibleName')
            tr_set(bar, 'Провайдер не передаёт процент расхода этого лимита.',
                   'The provider does not report usage percentages for this limit.', 'setToolTip')
            self.limit_bars.append(bar)
            layout.addWidget(bar)
        self.usage_help = tr_set(
            QLabel(),
            'Это подключение не предоставляет остатки лимитов и время сброса. Проверьте их в ChatGPT.',
            'This connection does not provide remaining limits or reset times. Check them in ChatGPT.',
        )
        self.usage_help.setWordWrap(True)
        layout.addWidget(self.usage_help)
        self.dashboard_link = QLabel()
        self.dashboard_link.setObjectName('LinkLabel')
        self.dashboard_link.setOpenExternalLinks(True)
        register(self.dashboard_link, lambda label: label.setText(
            f'<a href="{label.property("dashboardUrl") or ""}" style="color: {THEME["link"]};">'
            + str(_('Открыть лимиты ChatGPT', 'Open ChatGPT usage limits')) + '</a>'
        ))
        layout.addWidget(self.dashboard_link)
        self.hide()

    def configure(self, descriptor):
        self.cache_notice.setProperty('noticeText', descriptor.cache_notice)
        self.cache_notice.setText(_(*descriptor.cache_notice))
        self.cache_notice.setVisible(bool(descriptor.cache_notice[0]))
        self.dashboard_link.setProperty('dashboardUrl', descriptor.usage_dashboard_url)
        self.dashboard_link.setText(
            f'<a href="{descriptor.usage_dashboard_url}" style="color: {THEME["link"]};">'
            + str(_('Открыть лимиты ChatGPT', 'Open ChatGPT usage limits')) + '</a>'
        )
        self.setVisible(bool(descriptor.usage_dashboard_url))
