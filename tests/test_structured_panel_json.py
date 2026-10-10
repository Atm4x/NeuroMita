import json

from PyQt6.QtWidgets import QApplication, QLabel

from ui.chat.structured_panel import StructuredOutputPanel


def test_compact_raw_json_is_pretty_printed_without_changing_data():
    app = QApplication.instance() or QApplication([])
    raw = '{"segments":[{"text":"Привет"}],"attitude_change":0}'
    data = {'segments': [{'text': 'Привет'}], '_raw_json': raw}
    panel = StructuredOutputPanel(data, mode='json', start_expanded=True)
    labels = [label.text() for label in panel.findChildren(QLabel)]
    formatted = next(text for text in labels if text.startswith('{'))
    assert '\n  "segments": [' in formatted
    assert json.loads(formatted) == json.loads(raw)
    assert data['_raw_json'] == raw
    panel.close()
