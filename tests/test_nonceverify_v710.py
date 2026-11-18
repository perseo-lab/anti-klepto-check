"""
v7.10: five languages (EN default, IT, FR, ES, DE) and two hosts
(Sparrow default, Nunchuk on the phone), chosen on the splash, kept only in RAM.
"""
import builtins
import importlib
import io
import os
import re

import pytest
from PIL import Image

from nonceverify import app, guide, i18n, ui, wordentry
from nonceverify.hw import HEIGHT, WIDTH, Event
from nonceverify.i18n_keys import KEYS
from test_nonceverify_v79 import green_report

LANGS = [code for code, _ in i18n.LANGUAGES]
OTHER = [code for code in LANGS if code != "en"]


@pytest.fixture(autouse=True)
def english_after():
    yield
    i18n.reset()


def placeholders(text):
    return sorted(re.findall(r"\{\d\}", text))


@pytest.mark.parametrize("lang", OTHER)
def test_every_key_translated_with_the_same_placeholders(lang):
    by_id = importlib.import_module(f"nonceverify.i18n_{lang}").BY_ID
    assert set(by_id) == set(KEYS), "every id, and no other, in every catalog"
    for k, english in KEYS.items():
        text = by_id[k]
        assert text.strip(), k
        assert placeholders(text) == placeholders(english), k
        assert text.count("\n") == english.count("\n"), k
        assert text.startswith(" ") == english.startswith(" "), k


def test_english_and_sparrow_look_nothing_up(monkeypatch):
    monkeypatch.setattr(i18n, "_translate", lambda *a: pytest.fail("looked up"))
    for english in KEYS.values():
        assert i18n.t(english) is english


def test_template_values_are_translated_in_turn():
    i18n.set_language("it")
    assert i18n.t("Change 0.001 BTC: YOURS, change #3") == "Resto 0.001 BTC: TUO, resto #3"
    assert i18n.t("not complete; nonces verified") == "non completa; nonce verificati"
    i18n.set_language("de")
    assert i18n.t("12 words · with passphrase") == "12 Wörter · mit Passphrase"


def tap_chip(screen, kind, code):
    for b in screen.buttons[1:]:
        if b.value == (kind, code):
            x1, y1, x2, y2 = b.rect
            return screen.on_event(Event(Event.TAP, (x1 + x2) // 2, (y1 + y2) // 2))
    pytest.fail(f"no chip {kind} {code}")


def test_splash_chips_set_ram_only_state(monkeypatch):
    real_open = builtins.open

    def no_writes(path, mode="r", *a, **k):
        assert not any(m in mode for m in "wax+"), f"wrote {path}"
        return real_open(path, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", no_writes)
    monkeypatch.setattr(io, "open", no_writes)
    monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("os.open"))
    s = app.SplashScreen()
    assert (i18n.language(), i18n.host()) == ("en", "sparrow"), "English and Sparrow at power-on"
    for lang in OTHER + ["en", "de"]:
        assert tap_chip(s, "lang", lang) == "__redraw__"
        assert i18n.language() == lang
        s.render()
    assert tap_chip(s, "host", "nunchuk") == "__redraw__"
    assert i18n.host() == "nunchuk"
    image = s.render()
    assert image.size == (WIDTH, HEIGHT)
    primary = [b.value for b in s.buttons[1:] if b.primary]
    assert primary == [("host", "nunchuk"), ("lang", "de")]
    i18n.reset()
    assert (i18n.language(), i18n.host()) == ("en", "sparrow")


def test_language_lives_only_in_the_module():
    """ i18n imports nothing that could persist a choice, and calls nothing that writes """
    import ast
    src = os.path.dirname(app.__file__)
    for name in ["i18n.py", "i18n_host.py", "i18n_keys.py"] + [f"i18n_{lang}.py" for lang in OTHER]:
        tree = ast.parse(open(os.path.join(src, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert {a.name for a in node.names} <= {"importlib", "re"}, name
            if isinstance(node, ast.ImportFrom):
                assert node.module.startswith("nonceverify.i18n"), name
            if isinstance(node, ast.Name):
                assert node.id not in ("open", "os", "storage", "subprocess"), name
            if isinstance(node, ast.Attribute):
                assert node.attr not in ("write", "dump", "save"), name


def drawn_texts(monkeypatch):
    seen = []
    orig = ui.Draw.text

    def text(self, xy, txt, *a, **k):
        seen.append(i18n.t(txt))
        return orig(self, xy, txt, *a, **k)
    monkeypatch.setattr(ui.Draw, "text", text)
    return seen


@pytest.mark.parametrize("lang", LANGS)
def test_nunchuk_broadcast_shows_the_txid_and_no_qr(monkeypatch, lang):
    i18n.set_language(lang)
    i18n.set_host("nunchuk")
    g = green_report()
    seen = drawn_texts(monkeypatch)
    screen = app.BroadcastScreen(g)
    image = screen.render()
    rows = app.txid_rows(g.txid)
    assert all(row in seen for row in rows), "the whole txid, row by row"
    from pyzbar import pyzbar
    assert pyzbar.decode(image.convert("L")) == [], "no Tx QR with Nunchuk"
    assert not any("Load Transaction" in s for s in seen)


def test_sparrow_broadcast_still_has_the_qr(monkeypatch):
    i18n.set_language("es")
    monkeypatch.setattr(app, "decode_qr", lambda im: __import__("pyzbar.pyzbar", fromlist=["x"]).decode(im.convert("L"))[0].data)
    screen = app.BroadcastScreen(green_report())
    assert screen.ok and screen.frames


def test_user_text_is_never_translated(monkeypatch):
    """ a passphrase, typed text and BIP39 words that happen to be English keys stay as they are """
    i18n.set_language("it")
    assert i18n.t("space") == "spazio" and i18n.t("Back") == "Indietro"
    seen = drawn_texts(monkeypatch)
    ui.KeyboardScreen("Back").render()
    assert any(x.rstrip("_") == "Back" for x in seen), "typed text"
    seen.clear()
    s = app.ConfirmPassphraseScreen("Back", "73c5da0a")
    s.revealed = True
    s.render()
    assert "Back" in seen, "the passphrase"
    seen.clear()
    s = wordentry.SeedReviewScreen(["space"] * 11 + ["about"])
    s.revealed = True
    s.render()
    assert seen.count("space") == 11 and "spazio" not in seen, "BIP39 words"
    seen.clear()
    wordentry.WordEntryScreen(0, 12, "spac").render()
    assert "space" in seen and "spazio" not in seen, "candidate words"


def screens():
    g = green_report()
    qr = Image.new("RGB", (320, 320), (90, 90, 90))
    yield "splash", lambda: app.SplashScreen().render()
    yield "home", lambda: app.HomeScreen().render()
    yield "passphrase", lambda: app.PassphraseQuestionScreen("73c5da0a", 24).render()
    yield "seed ready", lambda: app.SeedReadyScreen("73c5da0a", 24, True, "seedsigner").render()
    yield "scan", lambda: app.ScanScreen("Scan the signed PSBT", lambda p: (False, 0, ""),
                                         help_topic="scan_psbt").compose(qr)
    yield "txid", lambda: app.TxidCheckScreen(g).render()
    yield "result", lambda: app.ResultScreen(g, "seedsigner", txid_confirmed=True).render()
    yield "details", lambda: app.ResultScreen(g, "seedsigner", txid_confirmed=True, details=True).render()
    yield "broadcast", lambda: app.BroadcastScreen(g).render()
    yield "address", lambda: app.AddressModeScreen().render()
    yield "words", lambda: wordentry.WordEntryScreen(4, 24, "ab").render()
    yield "review", lambda: wordentry.SeedReviewScreen(["able"] * 11 + ["about"]).render()
    for topic in guide.TOPICS:
        yield "help " + topic, lambda topic=topic: guide.HelpScreen(topic).render()


@pytest.mark.parametrize("host", [code for code, _ in i18n.HOSTS])
@pytest.mark.parametrize("lang", OTHER)
def test_every_screen_fits_and_is_translated(monkeypatch, lang, host):
    i18n.set_language(lang)
    i18n.set_host(host)
    monkeypatch.setattr(app, "decode_qr", lambda im: __import__("pyzbar.pyzbar", fromlist=["x"]).decode(im.convert("L"))[0].data)
    problems, english = [], set()
    orig_draw, orig_tr = ui.Draw.text, i18n._translate
    keys = set(KEYS.values())

    def tr(text, depth=0):
        out = orig_tr(text, depth)
        if depth == 0 and out == text and text in keys and i18n.catalog(lang).get(text) != text:
            english.add(text)
        return out

    def text(self, xy, txt, *a, **k):
        out = i18n.t(txt)
        f = k.get("font")
        if out and f is not None and "\n" not in out:
            x1, y1, x2, y2 = self.textbbox(xy, out, font=f, anchor=k.get("anchor"))
            if x1 < -1 or x2 > self.im.size[0] + 1:
                problems.append(f"off the screen: {out}")
            boxes = self.__dict__.setdefault("_boxes", [])
            for bx1, by1, bx2, by2, other in boxes:
                if min(x2, bx2) - max(x1, bx1) > 3 and min(y2, by2) - max(y1, by1) > 3 and other != out:
                    problems.append(f"overlap: {other} / {out}")
            boxes.append((x1, y1, x2, y2, out))
        return orig_draw(self, xy, txt, *a, **k)
    monkeypatch.setattr(i18n, "_translate", tr)
    monkeypatch.setattr(ui.Draw, "text", text)
    for name, render in screens():
        i18n._cache.clear()
        image = render()
        assert image.size == (WIDTH, HEIGHT), name
    problems = [p for p in problems if not p.endswith(" / k") and not p.startswith("overlap:   /")]
    assert problems == []
    assert english == set(), "a text with a translation was drawn in English"


def test_steps_shrink_but_never_reach_the_help_button(monkeypatch):
    i18n.set_language("es")
    boxes = []
    orig = ui.Draw.text

    def text(self, xy, txt, *a, **k):
        out = i18n.t(txt)
        if out in ("SEMILLA", "PSBT", "RESULTADO"):
            boxes.append(self.textbbox(xy, out, font=k["font"], anchor=k.get("anchor")))
        return orig(self, xy, txt, *a, **k)
    monkeypatch.setattr(ui.Draw, "text", text)
    image, d = ui.new_canvas()
    ui.header(d, 2, help=True)
    assert len(boxes) == 3
    assert min(b[0] for b in boxes) > ui.HELP_RECT[2]


def test_version():
    assert app.VERSION == "7.10"
