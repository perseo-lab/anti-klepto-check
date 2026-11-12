"""
v7.9 (Ollen, 12 Nov 2026): the result opens on a fixed summary page, nothing to scroll:
where the money goes (amount and the whole destination address), the change and whether
it is proven yours, the fee, in large type. Txid, XFP, inputs and outputs are on the
Details page, with Finish. Amounts in BTC. A red keeps the scrolling list, reason first.
The Broadcast screen says that Sparrow opens the loaded transaction in a new tab.
"""
import pytest

from nonceverify import address as A, app, ui
from nonceverify.hw import HEIGHT, WIDTH
from nonceverify.psbt import parse_psbt
from nonceverify.verify import (OWNER__EXTERNAL, OWNER__OURS, OWNER__UNVERIFIED, VERDICT__FAIL, VERDICT__OK,
    VERDICT__PARTIAL, verify_psbt)

pytest.importorskip("embit")
from embit import bip32, script                                                     # noqa: E402
from embit.psbt import DerivationPath                                               # noqa: E402
from test_nonceverify import embit_root, libsecp_sign_psbt, master, p2wpkh_psbt     # noqa: E402
from test_nonceverify_ui import (DETAILS, FINISH, FULL, LEFT, RIGHT, SAME_TXID, SEEDSIGNER, FakeHardware,  # noqa: E402
    Stop, load_seed_script, text_mode_zbar, ur_parts)                               # noqa: F401
from test_nonceverify_v76 import _multisig_spend, with_output_script                # noqa: E402

BUTTONS_TOP = HEIGHT - ui.BUTTON_H - ui.PAD


def green_report(n=2):
    psbt, keys, amounts = p2wpkh_psbt(n)
    libsecp_sign_psbt(psbt, keys, amounts)
    return verify_psbt(parse_psbt(psbt.serialize()), master(), grinding="libsecp")


def labels(screen):
    return [b.label for b in screen.buttons]


def run(script_, session=None):
    hw = FakeHardware(script_ + [("stop",)])
    with pytest.raises(Stop):
        app.run(hw, session)
    return hw


def test_green_opens_on_the_summary():
    report = green_report()
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=True)
    assert s.summary and labels(s) == ["Details", "Broadcast", "Next PSBT"]
    assert [b.value for b in s.buttons] == ["details", "txqr", "again"]
    assert s.buttons[1].primary, "Broadcast is the primary action on green"
    color, _icon, headline, sub = s.summary_banner()
    assert color == ui.GREEN and headline == "NONCE OK" and "txid OK" in sub
    image = s.render()
    assert image.getpixel((240, 34)) == ui.GREEN
    sends, change = s.card_texts()
    pay = next(o for o in report.outputs if o.owner == OWNER__EXTERNAL)
    ours = next(o for o in report.outputs if o.owner == OWNER__OURS)
    assert " ".join(t for t, _c, _m in sends[3]) == A.grouped(pay.address), "the whole destination address"
    assert sends[2] == pay.amount and change[2] == ours.amount
    assert change[0] == "CHANGE" and change[1] == ui.GREEN
    assert change[3][0][0] == f"{ours.label} · {ours.path}" and "proven" in change[3][1][0]
    assert app.btc_amount(ours.amount) == f"{ours.amount / 1e8:.8f}", "BTC, 8 decimals"


def test_summary_regions_do_not_overlap():
    R = app.ResultScreen
    assert ui.HEADER_H + R.SUMMARY_BANNER_H < R.SENDS_CARD[1] < R.SENDS_CARD[3] < R.CHANGE_CARD[1] < R.CHANGE_CARD[3]
    assert R.CHANGE_CARD[3] < R.FEE_Y - 8 and R.FEE_Y + 8 < R.NOTE_Y - 7 and R.NOTE_Y + 8 < BUTTONS_TOP
    for card in (R.SENDS_CARD, R.CHANGE_CARD):
        assert card[1] + 30 + 2 * 20 <= card[3] + 2, "two text lines fit in the card"


@pytest.mark.parametrize("address_text", [
    "bc1qk2m4r8w0x6d3fy5n7c9t2v4l8a0e3j6h5zqp7u",                               # P2WPKH, 42
    "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3",           # P2WSH, 62
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"])
def test_every_address_type_fits_in_two_lines(address_text):
    width = app.ResultScreen.SENDS_CARD[2] - app.ResultScreen.SENDS_CARD[0] - 20
    lines = app.address_lines(address_text, width)
    assert len(lines) <= 2 and " ".join(lines) == A.grouped(address_text)
    assert all(ui.text_width(ln, ui.font(17, mono=True)) <= width for ln in lines), "17 px, no shrinking"
    if len(lines) == 2:
        assert abs(len(lines[0].split()) - len(lines[1].split())) <= 1, "balanced: never a lone group"


def test_details_has_finish_and_back_and_the_full_list():
    report = green_report()
    d = app.ResultScreen(report, "coldcard_q", txid_confirmed=True, details=True)
    assert not d.summary and labels(d) == ["Finish", "Back"] and [b.value for b in d.buttons] == ["done", "back"]
    text = " ".join(line[0] for line in d.list.lines)
    assert "txid" in text and "XFP" in text and "OUTPUTS" in text and "input #0" in text
    assert "Broadcast THIS" not in text, "the instruction lives on the Broadcast screen"


def test_flow_details_back_broadcast_then_finish_asks():
    psbt, keys, amounts = p2wpkh_psbt(2)
    psbt.sign_with(embit_root())
    session = app.Session()
    script_ = load_seed_script(shots=False) + SEEDSIGNER + [RIGHT, ("blank",)] + ur_parts(psbt.serialize())
    script_ += [SAME_TXID, ("shot", "120_summary"), DETAILS, ("shot", "121_details"), RIGHT, ("shot", "122_back"),
                FULL, ("shot", "123_tx_qr"), FULL, ("shot", "124_summary_again"), DETAILS, FINISH,
                ("shot", "125_wipe_question"), RIGHT, ("shot", "126_kept")]
    hw = run(script_, session)
    for name in ("120_summary", "122_back", "124_summary_again"):
        assert hw.shots[name].getpixel((240, 34)) == ui.GREEN, name
    assert hw.shots["121_details"].tobytes() != hw.shots["120_summary"].tobytes()
    assert hw.shots["122_back"].tobytes() == hw.shots["120_summary"].tobytes(), "Back: the same summary"
    from test_nonceverify_v75 import _tx_qr_part
    assert _tx_qr_part(hw.shots["123_tx_qr"]).startswith("B$2T")
    shot = hw.shots["125_wipe_question"]
    assert any(shot.getpixel((x, y)) == ui.YELLOW for x in range(10, 60) for y in range(40, 64)), "Finish asks"
    assert session.master is not None, "Keep: the seed stays"


def test_unusual_change_is_yellow_with_the_reason_in_the_card():
    psbt, keys, amounts = p2wpkh_psbt(1)
    root = embit_root()
    path = "m/84h/0h/5h/1/3"
    pub = root.derive(path).key.get_public_key()
    psbt = with_output_script(psbt, 1, script.p2wpkh(pub))
    psbt.outputs[1].bip32_derivations = {pub: DerivationPath(root.my_fingerprint, bip32.parse_path(path))}
    libsecp_sign_psbt(psbt, keys, amounts)
    report = verify_psbt(parse_psbt(psbt.serialize()), master(), grinding="libsecp")
    assert report.change_warning
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=True)
    assert s.summary and s.summary_banner()[0] == ui.YELLOW and s.summary_banner()[2] == "CHANGE?"
    assert labels(s) == ["Details", "Broadcast", "Next PSBT"] and s.buttons[2].primary, "Next PSBT primary"
    _sends, change = s.card_texts()
    text = " ".join(t for t, _c, _m in change[3])
    assert change[4] == ui.YELLOW and all(c == ui.YELLOW for _t, c, _m in change[3])
    assert text.startswith("change #3:") and "another account" in text and "Sparrow sees it" in text, text
    image = s.render()
    x1, y1, x2, y2 = app.ResultScreen.CHANGE_CARD
    assert image.getpixel((x1 + 1, (y1 + y2) // 2)) == ui.YELLOW or image.getpixel((x1, (y1 + y2) // 2)) == ui.YELLOW


def test_unverified_multisig_change_has_no_broadcast():
    report = verify_psbt(parse_psbt(_multisig_spend(xpubs=False).serialize()), master(), grinding="embit")
    assert report.change_unverified
    s = app.ResultScreen(report, "seedsigner", txid_confirmed=True)
    assert s.summary and "txqr" not in [b.value for b in s.buttons]
    _sends, change = s.card_texts()
    assert change[0] == "CHANGE NOT VERIFIED" and change[4] == ui.YELLOW


def test_partial_has_no_broadcast_and_says_why():
    from test_nonceverify_v75 import _multisig
    from test_nonceverify import EVIL_K, sign_with_k
    psbt = _multisig(lambda B, z: sign_with_k(int.from_bytes(B.key.secret, "big"), z, EVIL_K))
    report = verify_psbt(parse_psbt(psbt.serialize()), master(), grinding="embit")
    assert report.verdict == VERDICT__PARTIAL
    s = app.ResultScreen(report, "seedsigner", txid_confirmed=True)
    assert s.summary and labels(s) == ["Details", "Next PSBT"]
    assert s.summary_banner()[0] == ui.YELLOW and "cosigner" in s.summary_banner()[3]
    assert "Do not broadcast" in s.summary_note()[0]
    s.render()


def test_red_keeps_the_list_reason_first():
    psbt, keys, amounts = p2wpkh_psbt(2)
    thief = embit_root("letter advice cage absurd amount doctor acoustic avoid letter advice cage above", "") \
        .derive("m/84h/0h/0h/1/0").key.get_public_key()
    psbt = with_output_script(psbt, 1, script.p2wpkh(thief))
    psbt.outputs[1].bip32_derivations = {thief: DerivationPath(embit_root().my_fingerprint,
                                                               bip32.parse_path("m/84h/0h/0h/1/0"))}
    libsecp_sign_psbt(psbt, keys, amounts)
    report = verify_psbt(parse_psbt(psbt.serialize()), master(), grinding="libsecp")
    assert report.verdict == VERDICT__FAIL
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=False)
    assert not s.summary and labels(s) == ["Finish", "Next PSBT"]
    assert "NOT YOUR CHANGE" in s.list.lines[0][0]


def test_several_destinations_and_no_change():
    report = green_report()
    from dataclasses import replace
    pay = next(o for o in report.outputs if o.owner == OWNER__EXTERNAL)
    report.outputs = [pay, replace(pay, index=1, amount=1000)]
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=True)
    sends, change = s.card_texts()
    assert sends[2] == pay.amount + 1000 and "2 addresses" in sends[3][0][0]
    assert change[2] is None and "no change" in change[3][0][0]
    s.render()


def test_extra_fields_note_on_the_summary():
    report = green_report()
    report.extra_fields = 2
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=True)
    assert "2 extra PSBT field" in s.summary_note()[0]


def test_summary_texts_fit():
    report = green_report()
    s = app.ResultScreen(report, "coldcard_q", txid_confirmed=True)
    width = WIDTH - 2 * ui.PAD - 20
    for card in s.card_texts():
        for text, _c, mono in card[3]:
            f = ui.font(17, mono=True) if mono else ui.fit_font(text, 16, width)
            assert ui.text_width(text, f) <= width or mono, text
        label_w = ui.text_width(card[0], ui.font(15, bold=True)) + 16 + 11 + ui.text_width("YOURS", ui.font(15, bold=True))
        amount_w = ui.text_width("21.00000000", ui.font(24, bold=True, mono=True)) + 16 + ui.text_width("BTC", ui.font(13, bold=True))
        assert label_w + amount_w < width, card[0]


def test_broadcast_screen_mentions_the_new_tab():
    import inspect
    src = inspect.getsource(app.BroadcastScreen.draw)
    assert "NEW tab" in src and "close the old one" in src
    report = green_report()
    app.BroadcastScreen(report).render()


# ---------------------------------------------------------------------------------------
# v7.9: "?" help pages, what to do and why (Ollen chose the "?" over a fixed "Why" line)
# ---------------------------------------------------------------------------------------
from nonceverify import guide, wordentry                                          # noqa: E402
from nonceverify.hw import Event                                                  # noqa: E402

HELP_TAP = ("tap", 229, 15)
SCAN_HELP_TAP = ("tap", 40, 160)
HELP_BACK = FULL


def _screen_classes():
    import inspect
    out = []
    for mod in (app, wordentry, guide):
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, ui.Screen) and cls.__module__ == mod.__name__:
                out.append(cls)
    return out


def test_every_step_screen_has_a_help_page():
    without = {"SplashScreen", "HelpScreen"}           # the splash has START only; help has no help
    for cls in _screen_classes():
        if cls.__name__ in without:
            assert cls.help_topic is None, cls.__name__
            continue
        if cls.step is not None or cls.header_label is not None:
            assert cls.help_topic in guide.TOPICS, cls.__name__
    for topic in {c.help_topic for c in _screen_classes() if c.help_topic}:
        assert topic in guide.TOPICS


@pytest.mark.parametrize("topic", sorted(guide.TOPICS))
def test_help_pages_render_and_scroll_to_the_end(topic):
    s = guide.HelpScreen(topic)
    width = WIDTH - 3 * ui.PAD
    for text, _c, size, mono in s.list.lines:
        assert ui.text_width(text, ui.font(size, mono=mono)) <= width + 2, (topic, text)
    first = s.render().tobytes()
    for _ in range(40):
        s.on_event(Event(Event.TAP, 240, s.list.bottom - 10))
    assert s.list.offset == s.list.max_offset(), "the last line can be reached"
    s.render()
    names = [t for t, c, _s, _m in s.list.lines if c == ui.ACCENT]
    assert names and all(n == n.upper() for n in names), "sections: DO / WHY / ..."
    assert first


def test_help_icon_is_drawn_only_where_there_is_help():
    cx, cy = ui.HELP_CENTER
    ready = app.SeedReadyScreen("73c5da0a", 12, False, "seedsigner").render()
    assert ready.getpixel((cx, cy - 11)) == ui.ACCENT or ready.getpixel((cx, cy - 10)) == ui.ACCENT
    plain = ui.MessageScreen("x", "y").render()
    assert plain.getpixel((cx, cy - 10)) != ui.ACCENT and plain.getpixel((cx, cy - 11)) != ui.ACCENT
    # the tap area stays inside the header and clear of the steps on the right
    assert ui.HELP_RECT[3] <= ui.HEADER_H + 2
    assert ui.text_width(ui.APP_NAME, ui.font(14, bold=True, mono=True)) + 32 + 20 < ui.HELP_RECT[0]


def test_help_from_the_seed_screen_and_back_to_the_same_screen():
    session = app.Session()
    script_ = load_seed_script(shots=False) + SEEDSIGNER + [("shot", "130_ready"), HELP_TAP, ("shot", "131_help"),
                                                            ("swipe_up",), HELP_BACK, ("shot", "132_ready_again")]
    hw = run(script_, session)
    assert hw.shots["131_help"].tobytes() != hw.shots["130_ready"].tobytes()
    assert hw.shots["132_ready_again"].tobytes() == hw.shots["130_ready"].tobytes(), "nothing changed meanwhile"
    assert session.master is not None and session.signer is None, "the signer is taken only on Scan PSBT"


def test_help_on_the_result_and_on_broadcast_then_it_still_broadcasts():
    psbt, keys, amounts = p2wpkh_psbt(2)
    psbt.sign_with(embit_root())
    script_ = load_seed_script(shots=False) + SEEDSIGNER + [RIGHT, ("blank",)] + ur_parts(psbt.serialize())
    script_ += [SAME_TXID, ("shot", "133_summary"), HELP_TAP, ("shot", "134_result_help"), HELP_BACK,
                ("shot", "135_summary_again"), FULL, HELP_TAP, ("shot", "136_broadcast_help"), HELP_BACK,
                ("shot", "137_tx_qr")]
    hw = run(script_)
    assert hw.shots["135_summary_again"].tobytes() == hw.shots["133_summary"].tobytes()
    from test_nonceverify_v75 import _tx_qr_part
    assert _tx_qr_part(hw.shots["137_tx_qr"]).startswith("B$2T")
    for name in ("134_result_help", "136_broadcast_help"):
        assert _tx_qr_part(hw.shots[name]) is None


def test_help_while_scanning_the_psbt():
    psbt, keys, amounts = p2wpkh_psbt(1)
    psbt.sign_with(embit_root())
    script_ = load_seed_script(shots=False) + SEEDSIGNER + [RIGHT, ("blank",), SCAN_HELP_TAP, ("shot", "138_scan_help"),
                                                            HELP_BACK, ("blank",)] + ur_parts(psbt.serialize())
    script_ += [SAME_TXID, ("shot", "139_green")]
    hw = run(script_)
    assert hw.shots["139_green"].getpixel((240, 34)) == ui.GREEN, "the scan went on after the help page"
    shot = hw.shots["138_scan_help"]
    assert shot.getpixel((240, 34)) != ui.GREEN


def test_scan_heading_never_splits_a_word():
    s = app.ScanScreen("PSBT · SeedSigner", lambda p: (False, 0, ""), help_topic="scan_psbt")
    s.compose(None)
    longest = "SeedSigner"
    f = ui.fit_font(longest, 15, s.LEFT - 8, bold=True)
    assert ui.text_width(longest, f) <= s.LEFT - 8
    assert "SeedSigner" in ui.wrap("PSBT · SeedSigner", f, s.LEFT - 8)[-1]
