"""
v7.12: the "?" pages on the classic SeedSigner (KEY1 on every screen that has one). The
texts are the Seed Max ones (guide.TOPICS), translated the same way; first, what the
keys do here. The joystick scrolls; KEY3, LEFT or the center go back to the same screen.
"""
from nonceverify import guide, ui_classic as u
from nonceverify.hw import Event
from nonceverify.hw_classic import HEIGHT

KEYS_TEXT = "Joystick: move, push to choose. KEY1: this page. KEY2: delete or zoom. KEY3: back."

# v7.13: the Seed Max pages say "tap"; here the same sentences with the joystick's verb
CLASSIC_TEXTS = {
    ("home", "STEPS"): "1. Load the seed: SeedQR or words, then the passphrase.\n"
                       "2. Choose the device that signed; scan the signed PSBT from Sparrow.\n"
                       "3. Compare the txid, read the result, choose Broadcast and load that QR in Sparrow.",
    ("txid", "DO"): "In Sparrow, the transaction tab shows the Transaction ID. Compare all four rows with this "
                    "screen. Same: choose Same txid. Different: choose Different.",
    ("signer", "NEXT"): "Scan PSBT: the signed transaction, from Sparrow. Change seed wipes this seed to load another (multisig: a cosigner's).",
    # v7.16: on the classic the host stays on the splash, and the donation is the heart
    ("start", "LANGUAGE"): "Language and host are chosen here, before START. RAM only: at every power-on the device starts again in English, with Sparrow.",
    ("start", "DONATE"): "The heart top left (joystick UP from Language): how to support the project, as QR codes. Nothing to do with the checks.",
    ("result", "GREEN"): "Every signature of this seed uses the nonce it had to use, sighash ALL, low S, and the txid "
                         "is Sparrow's. Choose Broadcast.",
}


class HelpScreen(u.Screen):
    header_label = "HELP"
    back_value = "back"

    def __init__(self, topic: str):
        super().__init__()
        self.title_text, sections = guide.TOPICS[topic]
        lines = []
        width = u.RIGHT - u.PAD - 6
        # v7.14: what the keys do, on the first pages only (start, home); the others go straight to the point
        keys = [("KEYS", KEYS_TEXT)] if topic in ("start", "home") else []
        for name, text in keys + list(sections):
            text = CLASSIC_TEXTS.get((topic, name), text)
            lines.append((name, u.ACCENT, 14, True))
            for line in u.wrap(text, u.font(16), width):
                lines.append((line, u.TEXT, 16, False))
            lines.append(("", u.TEXT, 1, False))
        self.list = u.ScrollList(lines, u.TOP + 26, HEIGHT - 4)
        self.selected = None

    def draw(self, d, image):
        u.title(d, self.title_text, color=u.ACCENT, size=u.LARGE - 2)
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
