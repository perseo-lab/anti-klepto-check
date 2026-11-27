"""
v7.16 (27 Nov 2026, after the tests of v7.15 on both devices):
- Raspy Max: the host is a question of its own after START, nothing preselected; the
  splash has Donate top left instead; the keys of the keyboards light up when pressed;
  no explorer; no donation at the end of a session.
- Classic SeedSigner (test_nonceverify_classic): the heart on the splash, only the
  possible letters in the word entry.
"""
import pytest

from nonceverify import app, flow, guide, i18n, ui, wordentry
from nonceverify.hw import Event
from test_nonceverify_ui import (HOST_NUNCHUK, HOST_SPARROW, SPLASH_START, TYPE_SEED, WORDS_12, FakeHardware,
                                 Stop, type_word)

DONATE_CHIP = ("tap", 54, 20)
DONATE_BACK = ("tap", 420, 288)            # DonateScreen: Back, rightmost of the bottom row
HOST_BACK = ("tap", 240, 288)


def center(rect):
    return int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)


@pytest.fixture(autouse=True)
def english_sparrow():
    i18n.reset()
    yield
    i18n.reset()


@pytest.fixture
def zbar(monkeypatch):
    monkeypatch.setattr(app, "decode_qr", lambda im: __import__("pyzbar.pyzbar", fromlist=["x"])
                        .decode(im.convert("L"))[0].data)


def run(script):
    hw = FakeHardware(script + [("stop",)])
    with pytest.raises(Stop):
        app.run(hw, app.Session())
    return hw


def test_host_is_asked_after_start_and_back_returns_to_the_splash():
    hw = run([("shot", "splash"), SPLASH_START, ("shot", "host"), HOST_BACK, ("shot", "splash_again"),
              SPLASH_START, HOST_NUNCHUK, ("shot", "home")])
    assert hw.shots["splash_again"].tobytes() == hw.shots["splash"].tobytes()
    assert i18n.host() == "nunchuk"
    assert hw.shots["home"].tobytes() != hw.shots["host"].tobytes()


def test_host_has_no_answer_preselected_and_a_tap_elsewhere_answers_nothing():
    hw = run([SPLASH_START, ("shot", "host"), ("tap", 240, 100), ("tap", 240, 140), ("shot", "host_still"),
              HOST_SPARROW, ("shot", "home")])
    assert hw.shots["host_still"].tobytes() == hw.shots["host"].tobytes()
    image = hw.shots["host"]
    for code, _name in i18n.HOSTS:
        rect = next(b.rect for b in app.HostScreen().buttons if b.value == code)
        assert image.getpixel((rect[0] + 6, center(rect)[1])) == ui.PANEL, f"{code}: not filled, not chosen"
    assert i18n.host() == "sparrow"


def test_donate_from_the_splash_and_back(zbar):
    hw = run([("shot", "splash"), DONATE_CHIP, ("shot", "donate"), DONATE_BACK, ("shot", "splash_again"),
              SPLASH_START, HOST_SPARROW, ("shot", "home")])
    assert app.decode_qr(hw.shots["donate"]) is not None, "the donation QR reads"
    assert hw.shots["splash_again"].tobytes() == hw.shots["splash"].tobytes()


def test_no_donation_at_the_end_of_a_session():
    """ flow.run never asks the front end for it any more """
    import inspect
    assert "donate" not in inspect.getsource(flow.run)
    assert not hasattr(app.MaxFrontEnd, "donate")


def test_address_check_has_no_explorer():
    values = [b.value for b in app.AddressModeScreen().buttons]
    assert values == ["single", "descriptor", "back"]
    assert "explorer" not in guide.TOPICS
    for name in ("ExplorerWalletScreen", "ExplorerListScreen", "explorer_flow", "address_qr"):
        assert not hasattr(app, name), name
    assert not hasattr(ui, "NumberPadScreen")


def lit_at(image, rect):
    """ The key filled teal, its label dark """
    x1, y1, x2, y2 = rect
    return image.getpixel((x1 + 4, (y1 + y2) // 2)) == ui.ACCENT


def test_a_letter_lights_up_then_goes_dark_again():
    rect = wordentry.WordEntryScreen.key_rect("a")
    hw = run([SPLASH_START, HOST_SPARROW, TYPE_SEED, WORDS_12, ("tap",) + center(rect), ("shot", "after")])
    entry = wordentry.WordEntryScreen(0, 12).render().tobytes()
    start = next(i for i, im in enumerate(hw.shown) if im.tobytes() == entry)
    lit = [im for im in hw.shown[start:] if lit_at(im, rect)]
    assert len(lit) == 1, "one frame with the key lit"
    i = start + hw.shown[start:].index(lit[0])
    assert not lit_at(hw.shown[i + 1], rect), "then the same screen with the key dark"
    # only the key's rows were sent again: everything else is the same frame
    y1, y2 = ui.lit_rows(ui.Button(rect, "a"))
    before, after = lit[0], hw.shown[i + 1]
    assert before.crop((0, 0, 480, y1)).tobytes() == after.crop((0, 0, 480, y1)).tobytes()
    assert before.crop((0, y2 + 1, 480, 320)).tobytes() == after.crop((0, y2 + 1, 480, 320)).tobytes()
    assert not lit_at(hw.shots["after"], rect)


def test_a_dimmed_letter_does_not_light_up():
    s = wordentry.WordEntryScreen(0, 12, "ab")
    rect = s.key_rect("q")                                   # no BIP39 word starts with "abq"
    assert s.on_event(Event(Event.TAP, *center(rect))) is None
    assert s.lit is None


def test_candidates_and_controls_light_up():
    s = wordentry.WordEntryScreen(0, 12, "abando")
    rect = s.candidate_rect(0)
    assert s.on_event(Event(Event.TAP, *center(rect))) == ("word", "abandon")
    assert s.lit is not None and s.lit.rect == rect
    s = wordentry.WordEntryScreen(0, 12, "ab")
    s.lit = None
    assert s.on_event(Event(Event.TAP, *center(s.control_rects()["erase"]))) == "__redraw__"
    assert s.lit.icon_name == "erase"


def test_passphrase_keys_light_up_the_page_key_with_its_new_label():
    kb = ui.KeyboardScreen("")
    key = next(b for b in kb.keys() if b.value == ("char", "q"))
    assert kb.on_event(Event(Event.TAP, *center(key.rect))) == "__redraw__"
    assert kb.lit.rect == key.rect and kb.lit.label == "q" and kb.text == "q"
    numbers = next(b for b in kb.keys() if b.value == ("page", "123"))
    kb.on_event(Event(Event.TAP, *center(numbers.rect)))
    assert kb.page == "123"
    assert kb.lit.rect == numbers.rect and kb.lit.label == "#+=", "123 -> #+=: the key shows where it leads now"


def test_typed_seed_still_reaches_the_review_with_the_flash():
    words = "abandon " * 11 + "about"
    script = [SPLASH_START, HOST_SPARROW, TYPE_SEED, WORDS_12]
    for w in words.split():
        script += type_word(w)
    script += [("shot", "review")]
    hw = run(script)
    assert "review" in hw.shots


def test_lit_frame_never_reaches_a_real_display_without_show_rows():
    """ a hardware without show_rows gets whole frames: ui.show_rows falls back to show """
    shown = []

    class Plain:
        def show(self, image):
            shown.append(image)
    image = ui.new_canvas()[0]
    ui.show_rows(Plain(), image, 10, 20)
    assert shown == [image]


def test_version():
    assert app.VERSION == "7.16"
