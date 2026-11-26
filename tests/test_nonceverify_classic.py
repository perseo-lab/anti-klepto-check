"""
v7.12: the verifier on the classic SeedSigner (240x240, joystick and three keys), driven
end to end on a fake device: scripted keys, camera frames that are real QR images, the
screens saved as screenshots.

    SEEDSIGNER_SCREENSHOT_DIR=/tmp/shots pytest tests/test_nonceverify_classic.py
"""
import os
import subprocess
import sys
from collections import deque

import pytest

from nonceverify import app, app_classic as ac, flow, i18n, ui, ui_classic as u, wordentry_classic as wc
from nonceverify.hw import Event
from nonceverify.hw_classic import HEIGHT, WIDTH, Keys, PINS

pytest.importorskip("embit")
qrcode = pytest.importorskip("qrcode")
pytest.importorskip("pyzbar.pyzbar")

from test_nonceverify import MNEMONIC, PASSPHRASE, embit_root, p2wpkh_psbt   # noqa: E402
from test_nonceverify_ui import compact_seedqr, ur_parts                     # noqa: E402

SHOTS = os.environ.get("SEEDSIGNER_SCREENSHOT_DIR")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def text_mode_zbar(monkeypatch):
    """ As in test_nonceverify_ui: upstream pyzbar has no binary mode, ASCII payloads read fine """
    import inspect
    from pyzbar import pyzbar
    if "binary" in inspect.signature(pyzbar.decode).parameters:
        return

    def decode(image):
        from pyzbar.pyzbar import ZBarSymbol
        found = pyzbar.decode(image.convert("L"), symbols=[ZBarSymbol.QRCODE])
        return found[0].data if found else None
    monkeypatch.setattr(ac, "decode_qr", decode)
    monkeypatch.setattr(app, "decode_qr", decode)


@pytest.fixture(autouse=True)
def english_after():
    yield
    i18n.reset()


class Stop(Exception):
    pass


def K(kind):
    return ("key", kind)


UP, DOWN, LEFT, RIGHT, PRESS = K(Event.UP), K(Event.DOWN), K(Event.LEFT), K(Event.RIGHT), K(Event.PRESS)
KEY1, KEY2, KEY3 = K(Event.KEY1), K(Event.KEY2), K(Event.KEY3)


class FakeKeys:
    """ Plays a script: ("key", kind), ("qr", payload), ("blank",), ("shot", name), ("stop",) """
    def __init__(self, script):
        self.script = deque(script)
        self.shown = []
        self.zoom = 1
        self.camera_on = False
        self.idle = 0
        self.shots = {}

    def _next(self, kinds):
        while self.script and self.script[0][0] == "shot":
            name = self.script.popleft()[1]
            self.shots[name] = self.shown[-1]
            if SHOTS:
                os.makedirs(SHOTS, exist_ok=True)
                self.shown[-1].save(os.path.join(SHOTS, f"classic_{name}.png"))
        if self.script and self.script[0][0] == "stop":
            raise Stop()
        if self.script and self.script[0][0] in kinds:
            self.idle = 0
            return self.script.popleft()
        self.idle += 1
        if self.idle > 2000:
            raise AssertionError(f"script stalled at {list(self.script)[:2]}")
        return None

    def show(self, image):
        assert image.size == (WIDTH, HEIGHT)
        self.shown.append(image.copy())

    def poll(self):
        step = self._next(("key",))
        return [] if step is None else [Event(step[1])]

    def wait(self, seconds=0):
        pass

    def camera_start(self):
        self.camera_on = True

    def camera_stop(self):
        self.camera_on = False
        while self.script and self.script[0][0] in ("qr", "blank"):
            self.script.popleft()

    def camera_set_zoom(self, factor):
        self.zoom = factor

    def camera_frame(self):
        assert self.camera_on
        step = self._next(("qr", "blank"))
        if step is None:
            return None
        from PIL import Image
        if step[0] == "blank":
            return Image.new("RGB", (320, 320), (90, 90, 90))
        qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(step[1])
        qr.make(fit=True)
        return qr.make_image().convert("RGB").resize((320, 320))


def type_passphrase(text):
    """ Joystick moves on the classic keyboard, switching pages as a person would """
    kb = wc.KeyboardScreen()
    moves = []

    def press(event_kind):
        moves.append(K(event_kind))
        kb.on_event(Event(event_kind))

    def go_to(value):
        target = next((rc for rc, (v, _label) in kb.cells.items() if v == value), None)
        if target is None:
            return False
        for _ in range(40):
            r, c = kb.grid.cursor
            if (r, c) == target:
                press(Event.PRESS)
                return True
            if r != target[0]:
                press(Event.DOWN if target[0] > r else Event.UP)
            else:
                press(Event.RIGHT if target[1] > c else Event.LEFT)
        raise AssertionError(f"can't reach {value}")

    for ch in text:
        for _ in range(4):
            if go_to(("char", ch)):
                break
            page = next(p for p, rows in wc.KeyboardScreen.PAGES.items() if any(ch in r for r in rows))
            if not go_to(("page", page)):
                go_to(("page", "123" if page == "#+=" else "abc"))
        else:
            raise AssertionError(f"can't type {ch!r}")
    assert kb.text == text
    return moves


def load_seed_script(passphrase=PASSPHRASE, shots=True):
    script = [("shot", "00_splash"), PRESS, ("shot", "01_home"), PRESS, ("blank",)]
    script += [("shot", "02_scan")] if shots else []
    script += [("qr", compact_seedqr(MNEMONIC))]
    script += [("shot", "03_passphrase_question")] if shots else []
    script += [PRESS]                                           # "Passphrase" (selected)
    script += [("shot", "04_keyboard")] if shots else []
    script += type_passphrase(passphrase)
    script += [("shot", "05_keyboard_typed")] if shots else []
    script += [KEY3]                                            # done
    script += [("shot", "06_confirm_passphrase")] if shots else []
    script += [PRESS]                                           # "Confirm" (selected)
    script += [("shot", "07_seed_ready")] if shots else []
    return script


SEEDSIGNER = [DOWN, PRESS]                  # second signer chosen: the bar is next, on "Scan PSBT"
TO_SCAN = []


def run(script):
    hw = FakeKeys(script + [("stop",)])
    with pytest.raises(Stop):
        ac.run(hw)
    return hw


def banner(shot):
    return shot.getpixel((WIDTH // 2, ac.ResultScreen.BANNER[0] + 3))


def test_full_flow_green_broadcast_details_finish():
    psbt, keys, amounts = p2wpkh_psbt(3)
    psbt.sign_with(embit_root())
    script = load_seed_script() + SEEDSIGNER + [("shot", "08_signer_chosen")] + TO_SCAN + [PRESS, ("blank",)]
    script += ur_parts(psbt.serialize())
    script += [("shot", "09_txid"), PRESS, ("shot", "09b_txid_push_ignored"), RIGHT, ("shot", "10_txid_same"), PRESS]
    script += [("shot", "11_result_green"), DOWN, ("shot", "11b_result_change_fee"), UP,
               PRESS, ("shot", "12_broadcast_qr"), PRESS, ("shot", "13_broadcast_how"),
               KEY3, LEFT, ("shot", "14_result_details_selected"), PRESS, ("shot", "15_details"), DOWN, DOWN,
               ("shot", "16_details_scrolled"), LEFT, PRESS, ("shot", "17_wipe"), LEFT, PRESS,
               ("shot", "18_seed_wiped"), PRESS, ("shot", "18b_donate_page"), RIGHT, ("shot", "18c_donate_lightning"),
               RIGHT, ("shot", "18d_donate_sp"), PRESS, ("shot", "19_home_again")]
    hw = run(script)
    assert hw.shots["09_txid"].tobytes() == hw.shots["09b_txid_push_ignored"].tobytes(), \
        "a push before moving the joystick answers nothing"
    assert banner(hw.shots["11_result_green"]) == u.GREEN
    for name in ("18b_donate_page", "18c_donate_lightning", "18d_donate_sp"):
        assert ac.decode_qr(hw.shots[name]) is not None, f"{name}: the QR reads"
    assert banner(hw.shots["15_details"]) == u.GREEN


def test_broadcast_qr_is_the_checked_transaction():
    psbt, keys, amounts = p2wpkh_psbt(2)
    psbt.sign_with(embit_root())
    from nonceverify.psbt import parse_psbt
    from nonceverify.verify import verify_psbt
    from nonceverify import crypto
    master = crypto.HDKey.from_seed(crypto.bip39_seed(MNEMONIC, PASSPHRASE))
    report = verify_psbt(parse_psbt(psbt.serialize()), master, grinding="embit")
    assert report.broadcast_tx
    screen = ac.BroadcastScreen(report)
    assert screen.ok and len(screen.parts) >= 1
    image = screen.render()
    payload = ac.decode_qr(image.crop((0, 0, WIDTH - u.TAB_W, 222)))
    assert payload is not None and payload.decode() == screen.parts[0]
    assert flow.bbqr_parts(report.broadcast_tx) == screen.parts


def test_wrong_txid_is_red_and_never_offers_broadcast():
    psbt, keys, amounts = p2wpkh_psbt(2)
    psbt.sign_with(embit_root())
    script = load_seed_script(shots=False) + SEEDSIGNER + TO_SCAN + [PRESS, ("blank",)] + ur_parts(psbt.serialize())
    script += [LEFT, PRESS, ("shot", "20_txid_different")]
    hw = run(script)
    assert banner(hw.shots["20_txid_different"]) == u.RED


def test_signer_is_required_and_fixed():
    s = ac.SeedReadyScreen("73c5da0a", 12, False)
    s.focus = "bar"                                  # Scan PSBT, no device chosen
    assert s.bar.value() == "scan_psbt"
    assert s.on_event(Event(Event.PRESS)) == "__redraw__" and s.must_choose and s.focus == 0
    locked = ac.SeedReadyScreen("73c5da0a", 12, False, signer=flow.SIGNER__TREZOR, locked=True)
    assert [locked.enabled(i) for i in range(3)] == [False, False, True]
    locked.on_event(Event(Event.UP))
    assert locked.focus == 2, "the locked-out signers can't be reached"
    locked.render()


def test_word_entry_types_a_whole_seed():
    """ The 12 words typed with the joystick, reviewed, Confirm """
    words = MNEMONIC.split()
    moves = []
    for i, word in enumerate(words):
        screen = wc.WordEntryScreen(i, len(words))
        for letter in word:
            if len(screen.candidates()) == 1:
                break
            target = next(rc for rc, (kind, v) in screen.cells.items() if kind == "letter" and v == letter)
            while screen.cursor != target:
                r, c = screen.cursor
                kind = (Event.DOWN if target[0] > r else Event.UP) if r != target[0] else \
                    (Event.RIGHT if target[1] > c else Event.LEFT)
                screen.on_event(Event(kind))
                moves.append(K(kind))
            assert screen.on_event(Event(Event.PRESS)) == "__redraw__"
            moves.append(PRESS)
        cands = screen.candidates()
        target = next(rc for rc, (kind, v) in screen.cells.items() if kind == "word" and v == word)
        while screen.cursor != target:
            r, c = screen.cursor
            kind = (Event.DOWN if target[0] > r else Event.UP) if r != target[0] else \
                (Event.RIGHT if target[1] > c else Event.LEFT)
            screen.on_event(Event(kind))
            moves.append(K(kind))
        assert screen.on_event(Event(Event.PRESS)) == ("word", word), (word, cands)
        moves.append(PRESS)
    script = [("shot", "30_splash"), PRESS, DOWN, PRESS, ("shot", "31_word_count"), PRESS, ("shot", "32_word_entry")]
    script += moves[:3] + [("shot", "33_word_typing")] + moves[3:]
    script += [("shot", "34_review"), PRESS, ("shot", "35_passphrase_question"), LEFT, PRESS,
               ("shot", "36_seed_ready_no_passphrase")]
    run(script)


def test_review_shows_words_only_on_show_and_wrong_checksum_blocks():
    words = MNEMONIC.split()
    s = wc.SeedReviewScreen(words)
    assert not s.revealed and s.bar.value() == "ok"
    s.on_event(Event(Event.LEFT))                    # Show
    s.on_event(Event(Event.PRESS))
    assert s.revealed
    s.on_event(Event(Event.UP))
    assert s.focus == 11 and s.on_event(Event(Event.PRESS)) == ("edit", 11)
    bad = wc.SeedReviewScreen(words[:-1] + ["zoo"])
    assert bad.revealed and "ok" not in bad.bar.values, "no Confirm with a wrong checksum"
    for n in (12, 24):
        wc.SeedReviewScreen((words * 2)[:n]).render()


def test_action_bar_and_screensaver(monkeypatch):
    bar = u.ActionBar(["Details", "Broadcast", "Next PSBT"], ["details", "txqr", "again"], 1)
    assert bar.value() == "txqr" and bar.move(1) and bar.value() == "again" and not bar.move(1)
    # no key for SCREENSAVER_S: the screensaver; the key that wakes it does nothing else
    clock = [0.0]
    monkeypatch.setattr(u.time, "monotonic", lambda: clock[0])

    class Hw:
        shown = []
        script = deque([[], [], [Event(Event.PRESS)], [Event(Event.PRESS)]])

        def show(self, image):
            self.shown.append(image)

        def poll(self):
            clock[0] += 70
            return self.script.popleft() if self.script else []

        def wait(self, s=0):
            pass
    hw = Hw()
    screen = ac.HomeScreen()
    assert screen.run(hw) == "scan_seed"
    dark = [im for im in hw.shown if im.getpixel((2, 2)) == (0, 0, 0) and im.getpixel((120, 230)) == (0, 0, 0)]
    assert dark, "the screensaver ran"
    assert not ac.BroadcastScreen.screensaver, "never over the Broadcast QR"


def test_keys_debounce_and_repeat():
    down = set()
    clock = [0.0]
    keys = Keys(lambda kind: kind in down, clock=lambda: clock[0])

    def at(ms):
        clock[0] = ms / 1000
        return [e.kind for e in keys.poll()]

    assert at(0) == []
    down.add(Event.DOWN)
    assert at(10) == []                              # the edge
    assert at(20) == []                              # bouncing still
    assert at(40) == [Event.DOWN]                    # steady: one press
    assert at(100) == []
    assert at(500) == [Event.DOWN]                   # held: repeats
    assert at(560) == [] and at(650) == [Event.DOWN]
    down.discard(Event.DOWN)
    down.add(Event.PRESS)
    at(700)
    assert at(740) == [Event.PRESS]
    assert at(2000) == [], "the center never repeats"
    assert set(PINS) == set(Event.KEYS)


def is_words(text: str) -> bool:
    """ Interface text (to be translated), not data: at least one word of 3+ letters that isn't hex or a name """
    import re
    names = {"Sparrow", "Nunchuk", "Coldcard", "SeedSigner", "Trezor", "BTC", "PSBT", "XFP", "SeedQR", "BBQr",
             "txid", "RFC", "START", "HELP", "CHECK", "ANTI", "KLEPTO", "Tor", "Tails"}
    if text.lstrip().startswith(("#", "XFP ", "locktime ", "[OK]", "[!!]", "[--]", "[??]")):
        return False                       # data lines the Seed Max draws the same way (values, not words)
    words = [w for w in re.findall(r"[A-Za-z]{3,}", text) if w not in names and not re.fullmatch(r"[0-9a-f]+", w)]
    return bool(words)


def unusual_change_report():
    import test_nonceverify_v79 as v79
    psbt, keys, amounts = p2wpkh_psbt(1)
    root = embit_root()
    path = "m/84h/0h/5h/1/3"
    pub = root.derive(path).key.get_public_key()
    psbt = v79.with_output_script(psbt, 1, v79.script.p2wpkh(pub))
    psbt.outputs[1].bip32_derivations = {pub: v79.DerivationPath(root.my_fingerprint, v79.bip32.parse_path(path))}
    v79.libsecp_sign_psbt(psbt, keys, amounts)
    report = v79.verify_psbt(v79.parse_psbt(psbt.serialize()), v79.master(), grinding="libsecp")
    assert report.change_warning
    return report


def screens():
    """ (name, render) of every classic screen, with the test data (also used by tools/akc_screenshots.py) """
    from test_nonceverify_v79 import green_report
    import test_nonceverify_v79 as v79
    from dataclasses import replace
    report = green_report()
    self_send = green_report()
    self_send.outputs = [o for o in self_send.outputs if o.owner == flow.OWNER__OURS]
    several = green_report()
    pay = next(o for o in several.outputs if o.owner == flow.OWNER__EXTERNAL)
    several.outputs = [pay, replace(pay, index=1, amount=1000)]
    several.extra_fields = 2
    unverified = v79.verify_psbt(v79.parse_psbt(v79._multisig_spend(xpubs=False).serialize()), v79.master(),
                                 grinding="embit")
    unusual = unusual_change_report()
    red = green_report()
    red.verdict = flow.VERDICT__FAIL
    red.tx_problem = "The txid is NOT the one in Sparrow: the transaction checked here is not the one Sparrow would " \
                     "broadcast. Do not broadcast."

    def _screens():
        yield "splash", lambda: ac.SplashScreen().render()
        yield "home", lambda: ac.HomeScreen().render()
        yield "count", lambda: wc.WordCountScreen().render()
        yield "entry", lambda: wc.WordEntryScreen(2, 12, "ab").render()
        yield "entry2", lambda: wc.WordEntryScreen(2, 24, "").render()
        yield "review", lambda: wc.SeedReviewScreen(MNEMONIC.split()).render()
        yield "review_bad", lambda: wc.SeedReviewScreen(MNEMONIC.split()[:-1] + ["zoo"]).render()
        yield "keyboard", lambda: wc.KeyboardScreen("abc def").render()
        yield "question", lambda: ac.PassphraseQuestionScreen("73c5da0a", 12).render()
        yield "confirm", lambda: ac.ConfirmPassphraseScreen("abc ", "0f056943").render()
        yield "ready", lambda: ac.SeedReadyScreen("73c5da0a", 24, True).render()
        yield "ready_locked", lambda: ac.SeedReadyScreen("73c5da0a", 12, False, flow.SIGNER__TREZOR, True).render()
        yield "txid", lambda: ac.TxidCheckScreen(report).render()
        for name, rep in (("green", report), ("self", self_send), ("several", several), ("unverified", unverified),
                          ("unusual", unusual)):
            for end in (False, True):
                def summary(rep=rep, end=end):
                    screen = ac.ResultScreen(rep, "coldcard_q", True)
                    screen.offset = screen.max_offset() if end else 0
                    return screen.render()
                yield f"result {name} {'end' if end else 'top'}", summary

            def to_address(rep=rep):
                screen = ac.ResultScreen(rep, "coldcard_q", True)
                screen.summary_sheet()
                screen.offset = min(screen.max_offset(), screen.sends_top - 2)
                return screen.render()
            yield f"result {name} address", to_address
        yield "details", lambda: ac.ResultScreen(report, "coldcard_q", True, details=True).render()
        yield "red", lambda: ac.ResultScreen(red, "coldcard_q", False).render()
        yield "broadcast", lambda: ac.BroadcastScreen(report).render()
        yield "scan", lambda: ac.ScanScreen("PSBT · Coldcard Q", lambda p: (False, 0, ""), help_topic="scan_psbt")\
            .compose(None, 2)
        for topic in __import__("nonceverify.guide", fromlist=["x"]).TOPICS:
            yield "help " + topic, lambda topic=topic: __import__("nonceverify.guide_classic", fromlist=["x"])\
                .HelpScreen(topic).render()
        yield "message", lambda: u.MessageScreen("Wipe the seed?", "Seed and passphrase are removed from memory: to "
                                                 "check anything else you will load them again.", buttons=("Wipe", "Keep"),
                                                 values=["wipe", "keep"], primary_index=1).render()
        for page in range(3):
            def donate_page(page=page):
                screen = ac.DonateScreen()
                screen.page = page
                return screen.render()
            yield f"donate {page}", donate_page
        yield "wiped", lambda: u.MessageScreen("Seed wiped", "Seed and passphrase have been removed from the app's "
                                               "memory.\n\n" + ac.ClassicFrontEnd.SWITCH_OFF,
                                               buttons=("Start again",)).render()


    return _screens()


def test_every_classic_screen_fits_and_is_translated(monkeypatch):
    """ Every screen, every language and host: 240x240, nothing off the screen, nothing left in English """
    orig_draw, orig_tr = ui.Draw.text, i18n._translate
    for lang in [c for c, _n in i18n.LANGUAGES]:
        for host in [c for c, _n in i18n.HOSTS]:
            i18n.set_language(lang)
            i18n.set_host(host)
            problems, english = [], set()

            def tr(text, depth=0):
                out = orig_tr(text, depth)
                if lang != "en" and depth == 0 and out == text and is_words(text) and \
                        i18n.catalog(lang).get(text) != text:
                    english.add(text)                # no key, or a key left untranslated
                return out

            def text(self, xy, txt, *a, **k):
                out = i18n.t(txt)
                f = k.get("font")
                if out and f is not None and "\n" not in out:
                    x1, y1, x2, y2 = self.textbbox(xy, out, font=f, anchor=k.get("anchor"))
                    if x1 < -1 or x2 > self.im.size[0] + 1:
                        problems.append(f"off the screen: {out}")
                return orig_draw(self, xy, txt, *a, **k)
            monkeypatch.setattr(i18n, "_translate", tr)
            monkeypatch.setattr(ui.Draw, "text", text)
            for name, render in screens():
                i18n._cache.clear()
                ac.SplashScreen._backgrounds.clear()
                image = render()
                assert image.size == (WIDTH, HEIGHT), name
            monkeypatch.setattr(i18n, "_translate", orig_tr)
            monkeypatch.setattr(ui.Draw, "text", orig_draw)
            assert problems == [], (lang, host, problems)
            assert english == set(), "\n".join([f"{lang} {host}: drawn in English, no translation key:"] + sorted(english))


def test_classic_front_end_loads_no_signer_code():
    """ What main() loads on the classic image pulls in no SeedSigner GUI, view, seed code, embit or urtypes """
    code = (
        "import sys; sys.path.insert(0, 'src'); import main, nonceverify.app_classic, nonceverify.hw_classic; "
        "bad = [m for m in sys.modules if m.startswith(('seedsigner.controller', 'seedsigner.views', 'seedsigner.gui', "
        "'seedsigner.models', 'embit', 'urtypes'))]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr


def test_target_selects_the_front_end(monkeypatch):
    sys.path.insert(0, os.path.join(REPO, "src"))
    import main
    from unittest.mock import patch
    from nonceverify import target
    monkeypatch.setattr(target, "TARGET", target.TARGET__CLASSIC)
    with patch("nonceverify.app_classic.main") as classic_main, patch("nonceverify.app.main") as max_main:
        main.main([])
    classic_main.assert_called_once_with()
    max_main.assert_not_called()
    assert target.TARGET__MAX == "max"


def test_donation_details_are_the_signed_ones():
    """ donate.py says what docs/DONATE.txt.asc, signed by the author, says """
    from nonceverify import donate
    signed = open(os.path.join(REPO, "docs", "DONATE.txt.asc"), encoding="utf-8").read()
    body = signed.split("-----BEGIN PGP SIGNATURE-----")[0]
    assert donate.BOLT12_OFFER in body.split()
    assert donate.SILENT_PAYMENT in body.split()
    assert donate.AUTHOR_KEY in body
    assert donate.PAGE_URL.startswith("https://github.com/perseo-lab/anti-klepto-check#")
    for _title, _kind, payload, _sub in donate.pages():
        assert app.checked_qr(payload, ac.DonateScreen.QR_BOX, low_ecc=True) is not None, "every donation QR reads back"
        assert app.checked_qr(payload, app.DonateScreen.QR_BOX, low_ecc=True) is not None


def test_checks_name_what_was_verified():
    from test_nonceverify_v79 import green_report
    import test_nonceverify_v79 as v79
    report = green_report()
    rows = {c: (label, level) for c, label, level, _s in flow.checks(report, True)}
    assert rows[flow.CHECK__NONCE][1] == rows[flow.CHECK__SIGHASH][1] == rows[flow.CHECK__TXID][1] == flow.LEVEL__GREEN
    assert rows[flow.CHECK__CHANGE] == ("Change address", flow.LEVEL__GREEN)
    unverified = v79.verify_psbt(v79.parse_psbt(v79._multisig_spend(xpubs=False).serialize()), v79.master(),
                                 grinding="embit")
    assert dict((c, lv) for c, _l, lv, _s in flow.checks(unverified, True))[flow.CHECK__CHANGE] == flow.LEVEL__YELLOW
    assert dict((c, lv) for c, _l, lv, _s in flow.checks(unusual_change_report(), True))[flow.CHECK__CHANGE] == \
        flow.LEVEL__YELLOW
    # the summary scrolls from the checks down to the fee
    screen = ac.ResultScreen(report, "seedsigner", True)
    top = screen.render()
    assert screen.max_offset() > 0
    screen.on_event(Event(Event.DOWN))
    assert screen.offset > 0 and screen.render().tobytes() != top.tobytes()
