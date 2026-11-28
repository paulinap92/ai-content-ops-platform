from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MenuParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "button" and "data-nav-key" in attrs:
            self.current = [attrs["data-nav-key"], ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if tag == "button" and self.current is not None:
            self.buttons.append(tuple(self.current))
            self.current = None


def menu(path):
    parser = MenuParser()
    parser.feed(path.read_text())
    return parser.buttons


def test_primary_menu_has_identical_labels_and_order():
    site = menu(ROOT / "canarias_site/studio/index.html")
    tools = menu(ROOT / "static/index.html")
    assert site == tools
    assert [key for key, _ in site] == [
        "preview", "lugares", "events", "calendar", "noticias", "guide",
        "photos", "templates", "database", "editor", "social", "settings", "monitor",
    ]
