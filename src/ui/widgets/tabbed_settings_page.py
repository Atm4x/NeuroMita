"""TabbedSettingsPage — replacement for the accordion-style settings layout.

A category page (e.g. "Общие", "Игра") used to be a vertical stack of
`CollapsibleSection`s. This widget renders the same data as a horizontal
tab bar + a `QStackedWidget` where each page is its own scrollable form.

Public API that `create_settings_section` relies on:

    page = TabbedSettingsPage(parent)
    header_layout = page.header_layout()   # QVBoxLayout for inline pre-tab widgets
    section = page.add_section("Игра", icon_name="fa5s.gamepad")
    section.add_widget(some_widget)
    section.content                          # parent QWidget for setting widgets

Layout:

    +---------------------------------------------+
    |  [optional header widgets here]             |
    +---------------------------------------------+
    |  [ Tab 1 ] [ Tab 2 ] [ Tab 3 ] ...          |
    +---------------------------------------------+
    |                                             |
    |   <scrollable page for the active tab>      |
    |                                             |
    +---------------------------------------------+

The class also tags the layout it exposes so `create_settings_section`
can route a tab call by inspecting the layout it received.
"""
from __future__ import annotations

from typing import Optional

try:
    import qtawesome as qta
except Exception:  # pragma: no cover - qtawesome is a soft dep
    qta = None

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SectionHolder(QWidget):
    """Adapter that exposes the same surface as `CollapsibleSection`:
    `.content` (QWidget) and `.add_widget(w)`.

    Each holder hosts the controls of one section/tab inside a scrollable
    page. From the schema-rendering side it's indistinguishable from a
    `CollapsibleSection`.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self.content = self  # so cfg.parent = section.content works as-is

    def add_widget(self, w: QWidget) -> None:
        self._layout.addWidget(w)

    # --- legacy CollapsibleSection API stubs (we're not collapsible) ---
    def collapse(self):  # pragma: no cover - noop in tab layout
        pass

    def expand(self):  # pragma: no cover - noop in tab layout
        pass


class _TabButton(QPushButton):
    def __init__(self, label: str, icon_name: Optional[str] = None, parent=None):
        super().__init__(label, parent)
        self.setObjectName("SettingsTabButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", "false")
        if icon_name and qta is not None:
            try:
                self.setIcon(qta.icon(icon_name, color="#f3edf6"))
                self.setIconSize(QSize(14, 14))
            except Exception:
                pass

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.setChecked(active)
        self.style().unpolish(self)
        self.style().polish(self)


class TabbedSettingsPage(QWidget):
    """Scrollable-pages-with-top-tabs container.

    Sections are added via `add_section()` (typically by `create_settings_section`).
    If only zero or one section is added, the tab bar hides and the content
    renders flat — no point in a single tab.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TabbedSettingsPage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Pre-tab "header" zone for inline widgets that the legacy setup_*_controls
        # add directly via parent_layout.addWidget(...). We expose this layout
        # through header_layout() and tag it with a back-pointer so
        # create_settings_section() can find the page from the layout.
        self._header_host = QWidget(self)
        self._header_layout = QVBoxLayout(self._header_host)
        self._header_layout.setContentsMargins(10, 10, 10, 0)
        self._header_layout.setSpacing(5)
        # Back-reference: gui_templates.create_settings_section looks for this.
        self._header_layout._tabbed_settings_page = self  # type: ignore[attr-defined]
        outer.addWidget(self._header_host, 0)

        # Tab bar
        self._tab_bar_host = QFrame(self)
        self._tab_bar_host.setObjectName("SettingsTabBar")
        self._tab_bar_layout = QHBoxLayout(self._tab_bar_host)
        self._tab_bar_layout.setContentsMargins(10, 8, 10, 0)
        self._tab_bar_layout.setSpacing(4)
        self._tab_bar_layout.addStretch(1)
        self._tab_bar_host.setVisible(False)
        outer.addWidget(self._tab_bar_host, 0)

        # Stacked scrollable bodies
        self._stack = QStackedWidget(self)
        self._stack.setObjectName("SettingsTabStack")
        outer.addWidget(self._stack, 1)

        self._tabs: list[tuple[_TabButton, QWidget, SectionHolder]] = []

    # ------------------------------------------------------------------ public

    def header_layout(self) -> QVBoxLayout:
        """Layout for widgets that should sit above the tab bar.

        `_init_settings_containers` passes this to `setup_*_controls` so that
        direct `parent_layout.addWidget(...)` calls land at the top while
        `create_settings_section(...)` calls add tabs below.
        """
        return self._header_layout

    def add_section(self, title: str, *, icon_name: Optional[str] = None) -> SectionHolder:
        """Append a new section as a tab. Returns a SectionHolder so the
        caller can pour widgets into it the same way it does for
        CollapsibleSection."""
        # Build button
        btn = _TabButton(title, icon_name=icon_name, parent=self._tab_bar_host)
        idx = len(self._tabs)
        btn.clicked.connect(lambda _checked=False, i=idx: self._activate(i))
        # Insert before the trailing stretch
        self._tab_bar_layout.insertWidget(self._tab_bar_layout.count() - 1, btn)

        # Build scrollable body page
        page = QScrollArea(self._stack)
        page.setObjectName("SettingsTabPage")
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("SettingsTabPageBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(10)

        holder = SectionHolder(body)
        body_layout.addWidget(holder)
        body_layout.addStretch(1)

        page.setWidget(body)

        self._stack.addWidget(page)
        self._tabs.append((btn, page, holder))

        # Show tab bar once there's >=2 tabs; first one is auto-active
        if idx == 0:
            btn.set_active(True)
            self._stack.setCurrentIndex(0)
        if len(self._tabs) >= 2:
            self._tab_bar_host.setVisible(True)

        return holder

    def section_count(self) -> int:
        return len(self._tabs)

    def switch_to(self, index_or_title) -> None:
        if isinstance(index_or_title, int):
            self._activate(index_or_title)
            return
        for i, (btn, _page, _holder) in enumerate(self._tabs):
            if btn.text() == str(index_or_title):
                self._activate(i)
                return

    # ------------------------------------------------------------------ private

    def _activate(self, index: int) -> None:
        if not (0 <= index < len(self._tabs)):
            return
        for i, (btn, _page, _holder) in enumerate(self._tabs):
            btn.set_active(i == index)
        self._stack.setCurrentIndex(index)


def attach_to_layout(parent_layout) -> TabbedSettingsPage:
    """Helper used by main_view: create a TabbedSettingsPage hosted by the
    QScrollArea content widget the legacy code already provides, and return
    it. The returned page's header_layout() is what should be passed onward
    to setup_*_controls(self, parent_layout)."""
    page = TabbedSettingsPage()
    parent_layout.addWidget(page)
    return page
