"""
v7.12: the "?" pages on the classic SeedSigner (KEY1 on every screen that has one). The
texts are the Seed Max ones (guide.TOPICS), translated the same way; first, what the
keys do here. The joystick scrolls; KEY3, LEFT or the center go back to the same screen.
"""
from nonceverify import guide, ui_classic as u
from nonceverify.hw import Event
from nonceverify.hw_classic import HEIGHT

KEYS_TEXT = "Joystick: move, push to choose. KEY1: this page. KEY2: delete or zoom. KEY3: back."


class HelpScreen(u.Screen):
    header_label = "HELP"
    back_value = "back"

    def __init__(self, topic: str):
        super().__init__()
        self.title_text, sections = guide.TOPICS[topic]
        lines = []
        width = u.RIGHT - u.PAD - 6
        for name, text in [("KEYS", KEYS_TEXT)] + list(sections):
            lines.append((name, u.ACCENT, 11, True))
            for line in u.wrap(text, u.font(13), width):
                lines.append((line, u.TEXT, 13, False))
            lines.append(("", u.TEXT, 1, False))
        self.list = u.ScrollList(lines, u.TOP + 22, HEIGHT - 4)
        self.selected = None

    def draw(self, d, image):
        u.title(d, self.title_text, color=u.ACCENT, size=15)
        self.list.draw(d)

    def draw_tabs(self, d):
        u.key_tab(d, Event.KEY3, "back", u.TEXT)

    def on_event(self, event):
        if event.kind in (Event.UP, Event.DOWN):
            self.list.scroll(-51 if event.kind == Event.UP else 51)
            return "__redraw__"
        if event.kind in (Event.LEFT, Event.PRESS, Event.KEY3, Event.KEY1):
            return "back"
        return None


def show(hw, topic: str):
    HelpScreen(topic).run(hw)
