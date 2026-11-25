"""
v7.12: Anti-Klepto Check on the classic SeedSigner (Pi Zero, Waveshare 1.3" 240x240 HAT
with joystick and three keys, Pi camera). The same verifier as on the Seed Max hardware:
the same core (crypto, psbt, verify, address, transport, seedqr) and the same steps and
rules (flow.py). Only the screens are drawn here, for 240x240 and the joystick, with the
Anti-Klepto Check look.

In this version: seed (SeedQR or words, passphrase), signer, PSBT (Coldcard Q included),
txid, result, Broadcast, the "?" pages, languages and host. The address checks (single-sig,
multisig descriptor, explorer) come in a later version.

This image never signs, never exports a key and never shows a seed unasked. Nothing is
written to the microSD: it is remounted read-only before anything else (storage.py).
"""
import logging
import time

from nonceverify import address, app, flow, i18n, storage, ui_classic as u, wordentry_classic
from nonceverify.flow import btc, btc_amount, signer_name, txid_rows
from nonceverify.hw import Event, QRDecoderError, decode_qr
from nonceverify.hw_classic import HEIGHT, WIDTH
from nonceverify.verify import (OWNER__EXTERNAL, OWNER__FAKE, OWNER__OURS, OWNER__UNVERIFIED, STATUS__FAIL,
    STATUS__FOREIGN, STATUS__OK, STATUS__UNSIGNED, STATUS__UNVERIFIABLE, VERDICT__FAIL, VERDICT__OK, VERDICT__PARTIAL)

logger = logging.getLogger(__name__)

VERSION = app.VERSION                 # one version for every target: the same code
TARGET_NAME = "SeedSigner 1.3\""

LEVEL_COLORS = {flow.LEVEL__GREEN: u.GREEN, flow.LEVEL__YELLOW: u.YELLOW, flow.LEVEL__RED: u.RED}
TONES = {flow.TONE__ACCENT: u.ACCENT, flow.TONE__YELLOW: u.YELLOW, flow.TONE__RED: u.RED}


def colored(decision):
    return (LEVEL_COLORS[decision[0]],) + tuple(decision[1:])


# ---------------------------------------------------------------------------------------
# Splash
# ---------------------------------------------------------------------------------------
def _blend(c0, c1, t: float):
    return tuple(int(round(c0[i] + (c1[i] - c0[i]) * t)) for i in range(3))


def splash_background():
    """ The Seed Max splash, drawn for 240x240: grid sky, teal floor, the emblem, the name """
    from PIL import Image
    hz = SplashScreen.HORIZON
    image = Image.new("RGBA", (WIDTH, HEIGHT))
    d = u.draw_on(image)
    sky_top, sky_bottom, floor_bottom = u.BACKGROUND, (16, 26, 40), (8, 34, 38)
    for y in range(HEIGHT):
        color = _blend(sky_top, sky_bottom, y / hz) if y < hz else _blend(sky_bottom, floor_bottom,
                                                                         (y - hz) / (HEIGHT - hz))
        d.line((0, y, WIDTH, y), fill=color + (255,))
    lines = Image.new("RGBA", image.size, (0, 0, 0, 0))
    g = u.draw_on(lines)
    for x in range(0, WIDTH, 16):
        g.line((x, 0, x, hz), fill=(60, 84, 112, 70))
    for y in range(0, hz, 16):
        g.line((0, y, WIDTH, y), fill=(60, 84, 112, 70))
    vx = WIDTH / 2
    for i in range(-12, 13):
        g.line((vx + i * 4, hz, vx + i * 26, HEIGHT), fill=u.ACCENT + (100,))
    y, step = float(hz), 2.5
    while y < HEIGHT:
        g.line((0, int(y), WIDTH, int(y)), fill=u.ACCENT + (int(60 + 140 * (y - hz) / (HEIGHT - hz)),))
        step *= 1.3
        y += step
    for width, alpha in ((9, 22), (6, 40), (3, 90), (1, 255)):
        g.line((0, hz, WIDTH, hz), fill=u.ACCENT + (alpha,), width=width)
    image.alpha_composite(lines)
    halo = Image.new("RGBA", image.size, (0, 0, 0, 0))
    h = u.draw_on(halo)
    cx, cy = WIDTH // 2, SplashScreen.EMBLEM_CY
    for r, alpha in ((38, 10), (32, 16), (27, 24), (22, 34)):
        h.ellipse((cx - r, cy - r, cx + r, cy + r), fill=u.ACCENT + (alpha,))
    image.alpha_composite(halo)
    d = u.draw_on(image)
    u.emblem(d, cx, cy, SplashScreen.EMBLEM_SIZE)
    u.spaced(d, (WIDTH / 2, 68), "ANTI-KLEPTO", u.font(21, bold=True), u.TEXT, 1)
    u.spaced(d, (WIDTH / 2, 86), "CHECK", u.font(11, bold=True, mono=True), u.ACCENT, 6)
    return image.convert("RGB")


class SplashScreen(u.Screen):
    """
    The tool's name, unmistakably not SeedSigner; language and host (RAM only, as on the
    Seed Max: English and Sparrow again at power-on); START. UP/DOWN move between the three
    rows, LEFT/RIGHT change language or host, the center on START starts.
    """
    HORIZON = 98
    EMBLEM_CY = 32
    EMBLEM_SIZE = 44
    PANEL = (14, 106, 226, 168)
    START = (66, 178, 174, 208)
    sd_status = None
    _backgrounds = {}

    def __init__(self):
        super().__init__()
        self.selected = 2                          # START

    @classmethod
    def background(cls):
        lang = i18n.language()
        if lang not in cls._backgrounds:
            cls._backgrounds[lang] = splash_background()
        return cls._backgrounds[lang]

    def render(self):
        image = self.background().copy()
        d = u.draw_on(image)
        x1, y1, x2, y2 = self.PANEL
        d.rounded_rectangle(self.PANEL, radius=8, fill=u.PANEL, outline=(70, 96, 124), width=1)
        rows = (("Language", dict(i18n.LANGUAGES)[i18n.language()]), ("Host", i18n.host_name()))
        for i, (label, value) in enumerate(rows):
            cy = y1 + 16 + i * 30
            selected = self.selected == i
            if selected:
                d.rounded_rectangle((x1 + 3, cy - 12, x2 - 3, cy + 12), radius=5, fill=u.PANEL_HI, outline=u.ACCENT)
            d.text((x1 + 10, cy), label, fill=u.DIM, font=u.fit_font(label, 13, 90, smallest=9), anchor="lm")
            f = u.font(14, bold=True)
            vx = x2 - 50
            d.text((vx, cy), i18n.Translated(value), fill=u.ACCENT if selected else u.TEXT, font=f, anchor="mm")
            if selected:
                for dx in (-1, 1):
                    ax = vx + dx * 38
                    d.polygon(((ax, cy - 5), (ax + dx * 6, cy), (ax, cy + 5)), fill=u.ACCENT)
        sx1, sy1, sx2, sy2 = self.START
        cy, radius = (sy1 + sy2) / 2, (sy2 - sy1) // 2
        if self.selected == 2:
            d.rounded_rectangle((sx1 - 3, sy1 - 3, sx2 + 3, sy2 + 3), radius=radius + 3, outline=u.ACCENT_DARK, width=3)
            d.rounded_rectangle(self.START, radius=radius, fill=u.ACCENT)
            d.rounded_rectangle((sx1, sy1, sx2, cy), radius=radius, fill=(110, 240, 224))
            d.rectangle((sx1 + radius, cy - 4, sx2 - radius, cy), fill=(70, 234, 212))
            fg = u.BACKGROUND
        else:
            d.rounded_rectangle(self.START, radius=radius, fill=u.PANEL, outline=u.ACCENT, width=2)
            fg = u.ACCENT
        f = u.font(15, bold=True)
        text_w = u.text_width("START", f)
        tx = (sx1 + sx2) / 2 - (text_w + 14) / 2
        d.text((tx, cy + 1), "START", fill=fg, font=f, anchor="lm")
        ax = tx + text_w + 6
        d.polygon(((ax, cy - 5), (ax + 8, cy), (ax, cy + 5)), fill=fg)
        if self.sd_status:
            writable = self.sd_status == storage.STATUS__WRITABLE
            text = "microSD WRITABLE: remount failed" if writable else f"microSD {self.sd_status}"
            d.text((WIDTH / 2, 219), text, fill=u.YELLOW if writable else u.DIM,
                   font=u.fit_font(text, 10, WIDTH - 12, bold=writable, mono=True, smallest=8), anchor="mm")
        d.text((WIDTH / 2, 232), f"Anti-Klepto Check · verifier SD v{VERSION}", fill=u.DIM,
               font=u.fit_font(f"Anti-Klepto Check · verifier SD v{VERSION}", 10, WIDTH - 12, mono=True, smallest=8),
               anchor="mm")
        return image

    def on_event(self, event):
        if event.kind == Event.UP:
            self.selected = max(0, self.selected - 1)
            return "__redraw__"
        if event.kind == Event.DOWN:
            self.selected = min(2, self.selected + 1)
            return "__redraw__"
        if event.kind in (Event.LEFT, Event.RIGHT) and self.selected < 2:
            options = i18n.LANGUAGES if self.selected == 0 else i18n.HOSTS
            codes = [c for c, _n in options]
            current = i18n.language() if self.selected == 0 else i18n.host()
            code = codes[(codes.index(current) + (1 if event.kind == Event.RIGHT else -1)) % len(codes)]
            (i18n.set_language if self.selected == 0 else i18n.set_host)(code)
            return "__redraw__"
        if event.kind == Event.PRESS and self.selected == 2:
            return "go"
        return None


# ---------------------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------------------
class HomeScreen(u.Screen):
    help_topic = "home"
    step = 0

    def __init__(self):
        super().__init__()
        self.items = u.column(["SeedQR", "Words"], 92, values=["scan_seed", "type_seed"], icons=["camera", "keyboard"],
                              height=38, gap=8, size=16)

    def draw(self, d, image):
        u.title(d, "Load the seed")
        u.paragraph(d, "SeedQR or words, and passphrase: RAM only", u.TOP + 22, size=13, color=u.DIM, max_lines=3)
        y = 190
        for n, head in ((2, "Scan the signed PSBT"), (3, "Read the result")):
            d.text((u.PAD + 6, y), str(n), fill=u.ACCENT, font=u.font(12, bold=True, mono=True), anchor="mm")
            d.text((u.PAD + 16, y), head, fill=u.DIM, font=u.fit_font(head, 12, u.RIGHT - u.PAD - 16, smallest=9),
                   anchor="lm")
            y += 20


class PassphraseQuestionScreen(u.Screen):
    help_topic = "seed"
    step = 0

    def __init__(self, fingerprint: str, words: int):
        super().__init__()
        self.fingerprint, self.words = fingerprint, words
        self.items = u.bottom_row(["None", "Passphrase"], values=["none", "enter"], icons=[None, "key"], primary_index=1)
        self.selected = 1

    def draw(self, d, image):
        u.icon(d, "ok_circle", (u.PAD + 8, u.TOP + 9), 15, u.GREEN)
        text = f"Seed read: {self.words} words, checksum OK"
        d.text((u.PAD + 20, u.TOP + 9), text, fill=u.TEXT, font=u.fit_font(text, 14, u.RIGHT - u.PAD - 20, bold=True,
                                                                          smallest=9), anchor="lm")
        u.panel(d, (u.PAD, u.TOP + 24, u.RIGHT, u.TOP + 82))
        u.spaced(d, (u.PAD + 8, u.TOP + 32), "XFP WITHOUT PASSPHRASE", u.font(9, bold=True, mono=True), u.DIM, 1,
                 anchor="lt")
        d.text((u.PAD + 8, u.TOP + 46), self.fingerprint, fill=u.TEXT, font=u.font(28, bold=True, mono=True))
        u.paragraph(d, "Does the wallet use a BIP39 passphrase?", u.TOP + 96, size=15, max_lines=3)


class ConfirmPassphraseScreen(u.Screen):
    help_topic = "seed"
    step = 0

    def __init__(self, passphrase: str, fingerprint: str):
        super().__init__()
        self.passphrase, self.fingerprint = passphrase, fingerprint
        self.revealed = False
        self.make_items()
        self.selected = 2

    def make_items(self):
        self.items = u.bottom_row(["Edit", "Hide" if self.revealed else "Show", "Confirm"], values=["edit", "reveal", "ok"],
                                  primary_index=2, size=13)

    def on_event(self, event):
        value = super().on_event(event)
        if value == "reveal":
            self.revealed = not self.revealed
            self.make_items()
            return "__redraw__"
        return value

    def draw(self, d, image):
        u.title(d, "Check the passphrase", size=15)
        u.panel(d, (u.PAD, u.TOP + 20, u.RIGHT, u.TOP + 92))
        u.spaced(d, (u.PAD + 8, u.TOP + 26), "PASSPHRASE", u.font(9, bold=True, mono=True), u.DIM, 1, anchor="lt")
        info = f"{len(self.passphrase)} characters · spaces = ·"
        d.text((u.RIGHT - 6, u.TOP + 26), info, fill=u.DIM, font=u.fit_font(info, 9, 120, mono=True, smallest=7),
               anchor="rt")
        f = u.font(14, mono=True)
        shown = flow.show_spaces(self.passphrase) if self.revealed else "•" * min(len(self.passphrase), 40)
        lines = u.wrap(i18n.Translated(shown) if self.passphrase else "(empty)", f, u.RIGHT - u.PAD - 16)
        if len(lines) > 3:
            lines = lines[:2] + [i18n.Translated("… " + lines[-1][-20:])]
        for i, line in enumerate(lines):
            d.text((u.PAD + 8, u.TOP + 40 + i * 16), line, fill=u.TEXT, font=f)
        u.spaced(d, (u.PAD + 2, u.TOP + 100), "RESULTING XFP", u.font(9, bold=True, mono=True), u.DIM, 1, anchor="lt")
        d.text((u.PAD, u.TOP + 112), self.fingerprint, fill=u.ACCENT, font=u.font(28, bold=True, mono=True))
        if not self.revealed:
            note, color = "hidden: Show to check it", u.DIM
        elif self.passphrase != self.passphrase.strip():
            note, color = "careful: spaces at the start or the end", u.YELLOW
        else:
            note = None
        if note:
            d.text((u.PAD, u.TOP + 156), note, fill=color, font=u.fit_font(note, 12, u.RIGHT - u.PAD, smallest=9),
                   anchor="lm")


class SeedReadyScreen(u.Screen):
    """
    The XFP, the device that signed (no default: named after every seed load, fixed at
    the first scan), then Scan PSBT or Change seed.
    """
    help_topic = "signer"
    step = 1
    SIGNERS_TOP = 148

    def __init__(self, fingerprint: str, words: int, has_passphrase: bool, signer: str = None, locked: bool = False):
        super().__init__()
        self.fingerprint, self.words, self.has_passphrase = fingerprint, words, has_passphrase
        self.locked = locked and signer in flow.SIGNERS
        self.signer = signer if signer in flow.SIGNERS else None
        self.locked_hint = False
        self.must_choose = False
        self.make_items()
        self.selected = len(flow.SIGNER_ORDER) + 1 if self.signer else 0

    def make_items(self):
        width = (u.RIGHT - u.PAD - 8) / 3
        self.items = []
        for i, signer in enumerate(flow.SIGNER_ORDER):
            x1 = u.PAD + i * (width + 4)
            item = u.Item((x1, self.SIGNERS_TOP, x1 + width, self.SIGNERS_TOP + 30), signer_name(signer),
                          value=("signer", signer), size=12, primary=(signer == self.signer))
            item.enabled = not (self.locked and signer != self.signer)
            self.items.append(item)
        self.items += u.bottom_row(["Change seed", "Scan PSBT"], values=["change_seed", "scan_psbt"],
                                   icons=[None, "camera"], primary_index=1, size=13)

    def on_event(self, event):
        value = super().on_event(event)
        if isinstance(value, tuple) and value[0] == "signer":
            if self.locked:
                self.locked_hint = value[1] != self.signer
                return "__redraw__"
            self.signer = value[1]
            self.must_choose = False
            keep = self.selected
            self.make_items()
            self.selected = keep
            return "__redraw__"
        if value == "scan_psbt" and self.signer is None:
            self.must_choose = True
            self.selected = 0
            return "__redraw__"
        return value

    def draw(self, d, image):
        u.panel(d, (u.PAD, u.TOP, u.RIGHT, u.TOP + 58), outline=u.ACCENT)
        u.icon(d, "fingerprint", (u.PAD + 20, u.TOP + 29), 24, u.ACCENT)
        u.spaced(d, (u.PAD + 40, u.TOP + 6), "SEED READY · XFP", u.font(9, bold=True, mono=True), u.DIM, 1, anchor="lt")
        d.text((u.PAD + 40, u.TOP + 16), self.fingerprint, fill=u.ACCENT, font=u.font(26, bold=True, mono=True))
        words = f"{self.words} words · " + ("with passphrase" if self.has_passphrase else "no passphrase")
        d.text((u.RIGHT - 6, u.TOP + 50), words, fill=u.DIM, font=u.fit_font(words, 10, 150, smallest=8), anchor="rm")
        y = u.paragraph(d, "It must match the XFP on your wallet backup.", u.TOP + 62, size=11, max_lines=2,
                        line_gap=1)
        if self.locked_hint:
            hint, color = "Locked for this session: to change it, Change seed", u.YELLOW
        elif self.locked:
            hint, color = "Who signed? (fixed for this session)", u.DIM
        elif self.must_choose:
            hint, color = "First choose the device you signed with:", u.YELLOW
        else:
            hint, color = "Which device signed? (fixed once you press Scan PSBT)", u.DIM
        u.paragraph(d, hint, y + 3, size=11, color=color, max_lines=2, line_gap=1)
        for item in self.items[:3]:
            if item.value[1] == self.signer:
                x1, y1, x2, y2 = item.rect
                u.check_mark(d, (x1 + x2) / 2, y1 - 9, 6, u.GREEN)       # the device chosen


# ---------------------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------------------
class ScanScreen:
    """
    The camera picture on the whole screen, every frame to the QR decoder. A thin band on
    top says what to scan; a progress bar at the bottom fills as the parts of an animated
    QR come in. KEY1 help (the camera keeps running), KEY2 zoom, KEY3 or LEFT back.
    """
    NO_FRAME_TIMEOUT_S = 8
    BAND_H = 18

    def __init__(self, heading: str, handle_payload, errors=(), help_topic: str = None):
        from nonceverify import seedqr, transport
        self.heading = heading
        self.help_topic = help_topic
        self.handle_payload = handle_payload
        self.errors = (transport.TransportError, seedqr.SeedQRError) + tuple(errors)
        self.progress = 0.0
        self.status = ""

    def compose(self, frame, zoom: int = 1):
        image, d = u.new_canvas()
        if frame is not None:
            if frame.size != (WIDTH, HEIGHT):
                frame = frame.resize((WIDTH, HEIGHT))
            image.paste(frame, (0, 0))
        L, R, T, B, k = 26, WIDTH - 26 - u.TAB_W, 30, HEIGHT - 22, 20
        for (x, y, dx, dy) in ((L, T, 1, 1), (R, T, -1, 1), (L, B, 1, -1), (R, B, -1, -1)):
            d.line((x, y, x + dx * k, y), fill=u.ACCENT, width=3)
            d.line((x, y, x, y + dy * k), fill=u.ACCENT, width=3)
        d.rectangle((0, 0, WIDTH, self.BAND_H), fill=u.PANEL)
        u.icon(d, "shield", (10, self.BAND_H / 2), 12, u.ACCENT)
        heading = i18n.t(self.heading)
        d.text((22, self.BAND_H / 2), i18n.Translated(heading), fill=u.ACCENT,
               font=u.fit_font(i18n.Translated(heading), 12, WIDTH - 22 - 30, bold=True, smallest=8), anchor="lm")
        d.text((WIDTH - 6, self.BAND_H / 2), f"{zoom}x", fill=u.TEXT if zoom > 1 else u.DIM,
               font=u.font(11, bold=True, mono=True), anchor="rm")
        d.rectangle((0, HEIGHT - 6, WIDTH, HEIGHT), fill=u.PANEL)
        if self.progress > 0:
            d.rectangle((0, HEIGHT - 6, int(WIDTH * min(1.0, self.progress)), HEIGHT), fill=u.ACCENT)
        if self.status:
            lines = u.wrap(self.status, u.font(12), WIDTH - 12 - u.TAB_W)[:4]
            top = HEIGHT - 10 - 15 * len(lines)
            d.rectangle((0, top - 5, WIDTH, HEIGHT - 6), fill=u.BACKGROUND)
            d.line((0, top - 5, WIDTH, top - 5), fill=u.YELLOW, width=2)
            for i, line in enumerate(lines):
                d.text((6, top + i * 15), line, fill=u.YELLOW, font=u.font(12))
        if self.help_topic:
            u.key_tab(d, Event.KEY1, "?", is_icon=False)
        u.key_tab(d, Event.KEY2, "search")
        u.key_tab(d, Event.KEY3, "back", u.TEXT)
        return image

    def _keys(self, hw):
        """ "back", "help" or None; handles the zoom """
        for event in hw.poll():
            if event.kind in (Event.KEY3, Event.LEFT):
                return "back"
            if event.kind == Event.KEY1 and self.help_topic:
                return "help"
            if event.kind == Event.KEY2:
                steps = (1, 2, 3)
                hw.camera_set_zoom(steps[(steps.index(hw.zoom) + 1) % len(steps)] if hw.zoom in steps else 1)
        return None

    def run(self, hw):
        self.status = "starting the camera…"
        hw.show(self.compose(None, hw.zoom))
        try:
            try:
                hw.camera_start()
            except Exception as e:
                logger.info(f"camera: {type(e).__name__}: {e}")
                u.MessageScreen("Camera not available", "Check the camera cable (with the device switched off) and "
                                "try again.", heading_color=u.RED, icon_name="camera").run(hw)
                return None
            started = time.monotonic()
            got_frame = False
            while True:
                u.housekeeping(hw)
                pressed = self._keys(hw)
                if pressed == "back":
                    return None
                if pressed == "help":
                    u.open_help(hw, self.help_topic)
                    hw.show(self.compose(None, hw.zoom))
                    continue
                frame = hw.camera_frame()
                if frame is None:
                    if not got_frame and time.monotonic() - started > self.NO_FRAME_TIMEOUT_S:
                        self.status = "no picture from the camera: go back and try again"
                        hw.show(self.compose(None, hw.zoom))
                        started = time.monotonic()
                    hw.wait()
                    continue
                if not got_frame:
                    got_frame = True
                    self.status = ""
                payload = decode_qr(frame)
                if payload is not None:
                    try:
                        done, self.progress, note = self.handle_payload(payload)
                        self.status = note or ""
                    except self.errors as e:
                        self.status = str(e)
                        done = False
                    except QRDecoderError:
                        raise
                    except Exception as e:
                        logger.info(f"QR rejected: {type(e).__name__}")       # never costs the loaded seed
                        self.status = "invalid QR, ignored"
                        done = False
                    if done:
                        return True
                hw.show(self.compose(frame, hw.zoom))
        finally:
            hw.camera_stop()


class WorkingScreen:
    def __init__(self, hw):
        self.hw = hw

    def _show(self, headline, counter, note, fraction, step=2):
        image, d = u.new_canvas()
        u.header(d, step)
        u.emblem(d, WIDTH // 2, 74, 56)
        d.text((WIDTH / 2, 124), headline, fill=u.TEXT, font=u.fit_font(headline, 15, WIDTH - 16, bold=True, smallest=9),
               anchor="mm")
        d.text((WIDTH / 2, 148), counter, fill=u.ACCENT, font=u.font(15, bold=True, mono=True), anchor="mm")
        x1, x2, y = 30, WIDTH - 30, 166
        d.rounded_rectangle((x1, y, x2, y + 6), radius=3, fill=u.PANEL)
        d.rounded_rectangle((x1, y, x1 + max(6, (x2 - x1) * min(1.0, fraction)), y + 6), radius=3, fill=u.ACCENT)
        u.paragraph(d, note, 184, size=11, color=u.DIM, x=10, width=WIDTH - 20, max_lines=3)
        self.hw.show(image)

    def scan(self, index: int, total: int):
        self._show("Looking for the seed's keys", f"branch {index + 1} / {total}",
                   "a key is not at the paths given in the PSBT", (index + 1) / total)

    def __call__(self, index: int, total: int):
        self._show("Recomputing the RFC 6979 nonces", f"input {index + 1} / {total}",
                   "signature by signature, with code independent of the signer", (index + 1) / total)


# ---------------------------------------------------------------------------------------
# Txid and result
# ---------------------------------------------------------------------------------------
class TxidCheckScreen(u.Screen):
    """
    v7 rule: green only after the txid is compared with the host's. On this hardware a
    push of the joystick is easy to give without reading: neither answer is selected
    until the joystick moves.
    """
    help_topic = "txid"
    step = 2

    def __init__(self, report):
        super().__init__()
        self.report = report
        self.items = u.bottom_row(["Different", "Same txid"], values=["different", "same"], primary_index=1)
        self.items[0].color = u.RED
        self.selected = None

    def draw(self, d, image):
        u.icon(d, "ok_circle", (u.PAD + 8, u.TOP + 8), 15, u.GREEN)
        head = "Nonces OK. Last step: compare the txid"
        d.text((u.PAD + 20, u.TOP + 8), head, fill=u.TEXT, font=u.fit_font(head, 13, u.RIGHT - u.PAD - 20, bold=True,
                                                                          smallest=8), anchor="lm")
        sub = "Sparrow, transaction tab: is it the same, all of it?"
        u.paragraph(d, sub, u.TOP + 20, size=11, color=u.DIM, max_lines=2, line_gap=0)
        u.panel(d, (u.PAD, u.TOP + 48, u.RIGHT, u.TOP + 162), outline=u.ACCENT)
        rows = txid_rows(self.report.txid)
        f = u.fit_font(max(rows, key=len), 22, u.RIGHT - u.PAD - 12, bold=True, mono=True)
        for i, r in enumerate(rows):
            d.text(((u.PAD + u.RIGHT) / 2, u.TOP + 63 + i * 28), r, fill=u.ACCENT if i % 2 == 0 else u.TEXT, font=f,
                   anchor="mm")
        if self.selected is None:
            d.text(((u.PAD + u.RIGHT) / 2, u.TOP + 172), "Move the joystick to answer", fill=u.DIM,
                   font=u.fit_font("Move the joystick to answer", 11, u.RIGHT - u.PAD, smallest=8), anchor="mm")


    def on_event(self, event):
        # LEFT is the left answer, RIGHT the right one: no answer by a single careless push
        if event.kind in (Event.LEFT, Event.RIGHT):
            self.selected = 0 if event.kind == Event.LEFT else 1
            return "__redraw__"
        if event.kind in (Event.UP, Event.DOWN):
            return None
        return super().on_event(event)


def address_groups(text: str, per_line: int = 5) -> list:
    groups = address.grouped(text).split(" ")
    return [" ".join(groups[i:i + per_line]) for i in range(0, len(groups), per_line)]


class ResultScreen(u.Screen):
    """
    The verdict. With the txid confirmed and clean nonces: one fixed page (as on the Seed
    Max): where the money goes (amount and the WHOLE address), the change and whether it
    is proven yours, the fee. Otherwise, and in Details: the reason first, then txid,
    inputs, outputs, scrolled with UP/DOWN. The buttons are chosen with LEFT/RIGHT.
    """
    help_topic = "result"
    step = 2
    BANNER = (u.HEADER_H + 2, u.HEADER_H + 34)
    LIST_TOP = u.HEADER_H + 38

    def __init__(self, report, signer: str = None, txid_confirmed: bool = False, details: bool = False):
        super().__init__()
        self.report, self.signer, self.txid_confirmed, self.details = report, signer, txid_confirmed, details
        self.summary = flow.shows_summary(report, txid_confirmed, details)
        self.can_export = flow.can_export(report, txid_confirmed)
        actions, primary = flow.result_actions(report, txid_confirmed, self.summary, details)
        self.items = u.bottom_row([a[0] for a in actions], values=[a[1] for a in actions], primary_index=primary,
                                  size=12, height=28)
        self.selected = primary
        self.list = None if self.summary else u.ScrollList(self.lines(), self.LIST_TOP, self.items[0].rect[1] - 4)

    def banner(self):
        if self.summary:
            return colored(flow.summary_banner(self.report, self.signer))
        if self.details and self.report.verdict == VERDICT__OK and self.txid_confirmed:
            return colored(flow.summary_banner(self.report, self.signer))
        return colored(flow.result_banner(self.report, self.signer, self.txid_confirmed))

    def lines(self):
        """ The list of the Seed Max result, for 240 pixels """
        r = self.report
        lines = []
        width = u.RIGHT - u.PAD - 6

        def add(text, color=u.TEXT, size=13, mono=False):
            lines.append((text, color, size, mono))

        def para(text, color, size=13, indent=""):
            for line in u.wrap(text, u.font(size), width - (8 if indent else 0)):
                add(i18n.Translated(indent + line) if indent else line, color, size)

        colors = {STATUS__OK: u.GREEN, STATUS__FAIL: u.RED, STATUS__UNSIGNED: u.YELLOW,
                  STATUS__UNVERIFIABLE: u.YELLOW, STATUS__FOREIGN: u.DIM}
        rule = flow.GRINDING_SHORT.get(r.grinding, r.grinding)
        who = f"{signer_name(self.signer)} ({rule})" if self.signer in flow.SIGNERS else f"grinding {rule}"
        if r.verdict == VERDICT__FAIL:
            if r.tx_problem:
                para(r.tx_problem, u.RED)
            for i in r.inputs:
                if i.status == STATUS__FAIL:
                    para(f"input #{i.index}: {i.message}", u.RED)
        if r.verdict == VERDICT__PARTIAL and r.unchecked_cosigners:
            para(f"Do not broadcast yet: {r.unchecked_cosigners} cosigner signature(s) not checked. Their nonce needs "
                 "their seed: Change seed, load that seed, pick its device, scan this same PSBT.", u.YELLOW, 12)
        elif r.verdict == VERDICT__PARTIAL:
            para("Not complete: some input is not signed yet. When the transaction is fully signed, scan it again "
                 "here: only then broadcast, with the Tx QR.", u.YELLOW, 12)
        if r.extra_fields:
            para(f"The PSBT carries {r.extra_fields} field(s) the check doesn't need: data that could leave with the "
                 "PSBT file. Broadcast with the Tx QR, don't pass the PSBT on.", u.YELLOW, 12)
        external, ours, unverified = flow.outputs_by_owner(r)
        para(f"Sends {btc(sum(o.amount for o in external))} to {len(external)} other address(es)", u.TEXT)
        for o in ours:
            para(f"Change {btc(o.amount)}: YOURS, {o.label}", u.GREEN)
            if o.note:
                para(o.note, u.YELLOW, 12)
        for o in unverified:
            para(f"Maybe NOT yours: {btc(o.amount)} (change not verified)", u.YELLOW)
            para(o.note, u.YELLOW, 12)
        if not ours and not unverified and r.verdict != VERDICT__FAIL:
            add("No change back to this wallet", u.DIM, 12)
        add(f"XFP {r.fingerprint} · {who}", u.DIM, 12, True)
        add("txid" + (" (same as Sparrow's)" if self.txid_confirmed else ""), u.DIM, 12, True)
        for row in txid_rows(r.txid):
            add(f" {row}", u.TEXT, 15, True)
        all_tag = " · sighash ALL" if r.verdict == VERDICT__OK else ""
        para(f"locktime {r.locktime} · version {r.version}{all_tag}", u.DIM, 11)
        if r.tx_problem and r.verdict != VERDICT__FAIL:
            para(r.tx_problem, u.RED)
        if flow.seed_mismatch(r):
            para("No input of this PSBT belongs to this XFP: check seed and passphrase.", u.YELLOW)
        for i in r.inputs:
            marker = {STATUS__OK: "OK", STATUS__FAIL: "!!", STATUS__FOREIGN: "--"}.get(i.status, "??")
            add(f"[{marker}] input #{i.index}  {btc(i.amount)}", colors[i.status], 13)
            if i.path:
                add(f"   {i.path}", u.DIM, 11, True)
            para(i.message, colors[i.status], 12, indent="   ")
        add("OUTPUTS", u.DIM, 11, True)
        tags = {OWNER__OURS: ("YOURS", u.GREEN), OWNER__UNVERIFIED: ("not verified", u.YELLOW),
                OWNER__FAKE: ("NOT YOURS", u.RED), OWNER__EXTERNAL: ("", u.TEXT)}
        for o in r.outputs:
            tag, color = tags[o.owner]
            para(f"#{o.index}  {btc(o.amount)}" + (f"  {tag}" if tag else "") + (f" · {o.label}" if o.label else ""),
                 color, 13)
            if o.path:
                add(f"   {o.path}", u.DIM, 11, True)
            for chunk in address_groups(o.address, 4):
                add(i18n.Translated(f"   {chunk}"), u.DIM if o.owner == OWNER__EXTERNAL else color, 13, True)
        add(f"Fee: {btc(r.fee)}", u.TEXT, 13)
        return lines

    def draw_banner(self, d):
        color, icon_name, headline, subline = self.banner()
        y1, y2 = self.BANNER
        d.rectangle((0, y1, WIDTH, y2), fill=color)
        u.icon(d, icon_name, (u.PAD + 9, (y1 + y2) / 2), 17, u.BACKGROUND)
        room = u.RIGHT - u.PAD - 22                   # clear of the key tabs on the right edge
        d.text((u.PAD + 22, y1 + 10), headline, fill=u.BACKGROUND,
               font=u.fit_font(headline, 15, room, bold=True, smallest=9), anchor="lm")
        sub = u.wrap(subline, u.font(10, bold=True), room)
        if len(sub) > 1:
            sub = [i18n.Translated(sub[0].rstrip(":,. ") + "…")]
        d.text((u.PAD + 22, y1 + 24), sub[0], fill=u.BACKGROUND, font=u.font(10, bold=True), anchor="lm")

    def draw_summary(self, d):
        r = self.report
        external, ours, unverified = flow.outputs_by_owner(r)
        x1, x2 = u.PAD, u.RIGHT
        f_amount, f_unit = u.font(17, bold=True, mono=True), u.font(10, bold=True)
        # SENDS TO
        top, bottom = 62, 140
        u.panel(d, (x1, top, x2, bottom))
        sats = sum(o.amount for o in external) if external else 0
        d.text((x1 + 6, top + 10), "SENDS TO", fill=u.TEXT, font=u.fit_font("SENDS TO", 11, 70, bold=True, smallest=8),
               anchor="lm")
        d.text((x2 - 6, top + 11), "BTC", fill=u.DIM, font=f_unit, anchor="rm")
        d.text((x2 - 32, top + 10), btc_amount(sats), fill=u.TEXT, font=f_amount, anchor="rm")
        if len(external) == 1:
            rows = [i18n.Translated(r) for r in address_groups(external[0].address, 5)]     # an address: never translated
            f = u.fit_font(max(rows, key=len), 14, x2 - x1 - 12, mono=True, smallest=10)
            for i, line in enumerate(rows[:4]):
                d.text((x1 + 6, top + 24 + i * 13), i18n.Translated(line), fill=u.TEXT, font=f)
        elif external:
            u.paragraph(d, f"{len(external)} addresses: each one in Details", top + 26, size=12, x=x1 + 6,
                        width=x2 - x1 - 12, max_lines=2)
        else:
            u.paragraph(d, "no other address: it all stays in this wallet", top + 26, size=12, color=u.DIM, x=x1 + 6,
                        width=x2 - x1 - 12, max_lines=2)
        # CHANGE
        top, bottom = 144, 180
        if unverified:
            label, lcolor, sats, outline = "CHANGE NOT VERIFIED", u.YELLOW, sum(o.amount for o in unverified), u.YELLOW
            note, ncolor = "Not proven yours. Load the descriptor (Address > Multisig), scan again", u.YELLOW
        elif ours:
            label, lcolor, sats = "CHANGE", u.GREEN, sum(o.amount for o in ours)
            notes = "; ".join(o.note for o in ours if o.note)
            if notes:
                note, ncolor, outline = notes, u.YELLOW, u.YELLOW
            else:
                o = ours[0]
                note = f"{o.label} · proven from your seed" if len(ours) == 1 else f"{len(ours)} outputs, all yours: see Details"
                ncolor, outline = u.DIM, u.LINE
        else:
            label, lcolor, sats, outline = "CHANGE", u.DIM, None, u.LINE
            note, ncolor = "no change back to this wallet", u.DIM
        u.panel(d, (x1, top, x2, bottom), outline=outline, width=1 if outline == u.LINE else 2)
        yours = lcolor == u.GREEN
        both = i18n.Translated(i18n.t(label) + " xxxx " + i18n.t("YOURS")) if yours else label
        f_label = u.fit_font(both, 11, 110, bold=True, smallest=7)
        d.text((x1 + 6, top + 10), label, fill=lcolor, font=f_label, anchor="lm")
        if yours:
            x = x1 + 6 + u.text_width(label, f_label) + 10
            u.check_mark(d, x, top + 10, 5, u.GREEN)
            d.text((x + 8, top + 10), "YOURS", fill=u.GREEN, font=f_label, anchor="lm")
        if sats is not None:
            d.text((x2 - 6, top + 11), "BTC", fill=u.DIM, font=f_unit, anchor="rm")
            d.text((x2 - 32, top + 10), btc_amount(sats), fill=u.TEXT, font=u.font(14, bold=True, mono=True),
                   anchor="rm")
        lines = u.wrap(note, u.font(10), x2 - x1 - 12)
        if len(lines) > 1:
            lines = [i18n.Translated(lines[0][:-1] + "…")]
        d.text((x1 + 6, top + 26), lines[0], fill=ncolor, font=u.font(10), anchor="lm")
        # Fee and the one note
        d.text((x1 + 6, 190), "Fee", fill=u.DIM, font=u.font(12), anchor="lm")
        d.text((x2 - 6, 190), btc(r.fee), fill=u.TEXT, font=u.font(12, mono=True), anchor="rm")
        note, level = flow.summary_note(r)
        if note:
            d.text((WIDTH / 2, 202), note, fill=LEVEL_COLORS[level], font=u.fit_font(note, 10, WIDTH - 12, smallest=7),
                   anchor="mm")

    def draw(self, d, image):
        self.draw_banner(d)
        if self.summary:
            self.draw_summary(d)
        else:
            self.list.draw(d)

    def on_event(self, event):
        if event.kind in (Event.UP, Event.DOWN) and self.list is not None:
            self.list.scroll(-45 if event.kind == Event.UP else 45)
            return "__redraw__"
        if event.kind in (Event.UP, Event.DOWN):
            return None
        return super().on_event(event)


class BroadcastScreen(u.Screen):
    """
    The transaction checked here, as an animated BBQr: the whole screen is the QR, for the
    webcam. The joystick center shows how to load it in Sparrow (and back to the QR).
    Nunchuk can't load a second copy: the whole txid, to find in Nunchuk (as on the Seed Max).
    """
    help_topic = "broadcast"
    back_value = "back"
    QR_BOX = 216
    FRAME_S = 0.6

    def __init__(self, report):
        super().__init__()
        self.report = report
        self.nunchuk = i18n.host() == "nunchuk"
        self.parts = [] if self.nunchuk else flow.bbqr_parts(report.broadcast_tx)
        self.frames = [app.checked_qr(p, self.QR_BOX) for p in self.parts]
        self.ok = bool(self.frames) and all(f is not None for f in self.frames)
        self.index = 0
        self.info = False
        self.selected = None

    def render(self):
        image, d = u.new_canvas()
        if self.nunchuk or self.info or not self.ok:
            u.header(d, self.step)
            self.draw_text(d)
        else:
            frame = self.frames[self.index]
            box = self.QR_BOX
            x, y = (WIDTH - u.TAB_W - box) // 2, 2
            d.rectangle((x, y, x + box, y + box), fill=(255, 255, 255))
            image.paste(frame, (x + (box - frame.size[0]) // 2, y + (box - frame.size[1]) // 2))
            text = f"QR {self.index + 1} / {len(self.parts)} · BBQr"
            d.text((x, 230), text, fill=u.DIM, font=u.font(10, mono=True), anchor="lm")
            hint = "push: instructions"
            d.text((x + box, 230), hint, fill=u.ACCENT, font=u.fit_font(hint, 10, box - 100, smallest=7), anchor="rm")
        self.draw_tabs(d)
        return image

    def draw_text(self, d):
        if self.nunchuk:
            from nonceverify.i18n_host import NUNCHUK_BROADCAST_TEXT, NUNCHUK_BROADCAST_TITLE
            u.title(d, NUNCHUK_BROADCAST_TITLE, color=u.GREEN, size=15)
            y = u.paragraph(d, NUNCHUK_BROADCAST_TEXT, u.TOP + 20, size=11, max_lines=6, line_gap=1)
        else:
            u.title(d, "Broadcast THIS", color=u.GREEN, size=15)
            if not self.ok:
                d.text((u.PAD, u.TOP + 28), "QR not available", fill=u.RED, font=u.font(14, bold=True), anchor="lm")
            y = u.paragraph(d, "Sparrow: File > Load Transaction > From QR. It opens a NEW tab: same txid? "
                            "Broadcast from that tab, close the old one.", u.TOP + 40, size=12, max_lines=7, line_gap=1)
        d.text((u.PAD, y + 4), "txid", fill=u.DIM, font=u.font(11, mono=True))
        f = u.font(16, bold=True, mono=True)
        for i, r in enumerate(txid_rows(self.report.txid)):
            d.text(((u.PAD + u.RIGHT) / 2, y + 26 + i * 19), r, fill=u.ACCENT if i % 2 == 0 else u.TEXT, font=f,
                   anchor="mm")

    def on_event(self, event):
        if event.kind == Event.PRESS and not self.nunchuk and self.ok:
            self.info = not self.info
            return "__redraw__"
        if event.kind == Event.LEFT:
            return "back"
        return super().on_event(event)

    def run(self, hw, timeout: float = None):
        hw.show(self.render())
        shown = time.monotonic()
        while True:
            u.housekeeping(hw)
            for event in hw.poll():
                if event.kind == Event.KEY1:
                    u.open_help(hw, self.help_topic)
                    hw.show(self.render())
                    continue
                result = self.on_event(event)
                if result == "__redraw__":
                    hw.show(self.render())
                elif result is not None:
                    return result
            if len(self.frames) > 1 and not self.info and time.monotonic() - shown >= self.FRAME_S:
                self.index = (self.index + 1) % len(self.frames)
                hw.show(self.render())
                shown = time.monotonic()
            hw.wait()


# ---------------------------------------------------------------------------------------
# The front end and the start
# ---------------------------------------------------------------------------------------
class ClassicFrontEnd:
    """ The steps of flow.run() drawn on the classic SeedSigner """
    SWITCH_OFF = "Unplug the power: that clears the RAM completely."

    def __init__(self, hw):
        self.hw = hw

    def splash(self):
        SplashScreen().run(self.hw)

    def home(self):
        return HomeScreen().run(self.hw)

    def scan(self, heading, on_payload, topic, errors=()):
        return ScanScreen(heading, on_payload, errors=errors, help_topic=topic).run(self.hw)

    def type_mnemonic(self):
        return wordentry_classic.enter_mnemonic(self.hw)

    def passphrase_question(self, xfp, words):
        return PassphraseQuestionScreen(xfp, words).run(self.hw)

    def passphrase_keyboard(self, text):
        return wordentry_classic.KeyboardScreen(text).run(self.hw)[1]

    def confirm_passphrase(self, passphrase, xfp):
        return ConfirmPassphraseScreen(passphrase, xfp).run(self.hw)

    def seed_ready(self, xfp, words, has_passphrase, signer, locked):
        ready = SeedReadyScreen(xfp, words, has_passphrase, signer, locked)
        return ready.run(self.hw), ready.signer

    def message(self, heading, body, tone, icon, buttons=("OK",), values=None, primary=0):
        return u.MessageScreen(heading, body, buttons=buttons, heading_color=TONES[tone], primary_index=primary,
                               values=values, icon_name=icon).run(self.hw)

    def working(self):
        return WorkingScreen(self.hw)

    def txid_check(self, report):
        return TxidCheckScreen(report).run(self.hw)

    def result(self, report, signer, txid_confirmed, details):
        return ResultScreen(report, signer, txid_confirmed=txid_confirmed, details=details).run(self.hw)

    def broadcast(self, report):
        BroadcastScreen(report).run(self.hw)


def run(hw, session: flow.Session = None, splash: bool = True):
    flow.run(ClassicFrontEnd(hw), session, splash, logger)


def boot_error(hw, text: str):
    """ A fatal problem with the image itself: say so and stop (never run unguarded) """
    logger.error(text)
    if hw is not None:
        try:
            u.MessageScreen("Image not valid", text, buttons=("Switch the device off",), heading_color=u.RED,
                            icon_name="warning").run(hw)
        except Exception:
            pass
    while True:
        time.sleep(60)


def main():
    logging.basicConfig(level=logging.INFO)
    # before anything else, the microSD read-only (storage.py), then checked every second
    SplashScreen.sd_status = storage.protect_microsd()
    logger.info(f"microSD: {SplashScreen.sd_status}")
    guard = storage.MicroSDGuard(on_change=lambda status: setattr(SplashScreen, "sd_status", status))
    u.ui.housekeeping_hooks.append(guard.tick)
    from nonceverify.hw import ImportGuard, loaded_blocked_modules
    from nonceverify.hw_classic import Hardware

    # Drivers first, then the guard: if a driver pulled in the signer's crypto, the screen
    # says so instead of staying black, and the verifier does not run.
    hw = None
    try:
        hw = Hardware()
    except Exception as e:
        logger.exception("hardware")
        boot_error(None, f"driver: {type(e).__name__}: {e}")
    leaked = loaded_blocked_modules()
    if leaked:
        boot_error(hw, "the drivers load signer code: " + ", ".join(leaked[:4]))
    ImportGuard.install()

    session = flow.Session()
    splash = True
    while True:
        try:
            first, splash = splash, False
            run(hw, session, first)
        except QRDecoderError as e:
            boot_error(hw, str(e))
        except Exception as e:
            logger.exception("verifier error")              # the seed is kept: Change seed or Finish
            try:
                u.MessageScreen("Error", f"{type(e).__name__}: {str(e)[:160]}", heading_color=u.RED,
                                icon_name="warning").run(hw)
            except Exception:
                time.sleep(1)
