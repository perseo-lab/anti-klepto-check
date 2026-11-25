"""
v7.11: flow.py, the flow's rules apart from any screen. Every front end (the Seed Max
480x320 touch today, the classic SeedSigner 240x240 next) draws these decisions; none
takes its own. Here: flow.py imports no screen code, and the rules hold on their own.
"""
import ast
import os

import pytest

from nonceverify import flow
from nonceverify.verify import Report, VERDICT__FAIL, VERDICT__OK, VERDICT__PARTIAL

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "nonceverify")

# The verifier's core: no screen, no hardware. Front ends sit on top of these files.
CORE = ("crypto.py", "psbt.py", "verify.py", "address.py", "transport.py", "seedqr.py", "flow.py")
NOT_IN_CORE = ("PIL", "nonceverify.ui", "nonceverify.hw", "nonceverify.app", "nonceverify.wordentry",
               "nonceverify.guide", "nonceverify.i18n", "seedsigner", "embit", "RPi", "spidev")


def _imports(name):
    tree = ast.parse(open(os.path.join(SRC, name), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            yield base
            if base == "nonceverify":
                for alias in node.names:
                    yield f"nonceverify.{alias.name}"


def test_core_imports_no_screen_and_no_hardware():
    for name in CORE:
        for imported in _imports(name):
            for banned in NOT_IN_CORE:
                assert imported != banned and not imported.startswith(banned + "."), f"{name} imports {imported}"


def _report(**kw):
    kw.setdefault("fingerprint", "73c5da0a")
    kw.setdefault("txid", "ab" * 32)
    kw.setdefault("seed_matches", True)
    return Report(**kw)


def test_signer_is_fixed_by_the_first_scan_and_only_with_a_signer():
    s = flow.Session()
    assert not s.lock_signer(), "no scan without a device named"
    s.choose_signer(flow.SIGNER__TREZOR)
    assert s.lock_signer() and s.signer_locked
    s.choose_signer(flow.SIGNER__COLDCARD_Q)
    assert s.signer == flow.SIGNER__TREZOR, "fixed for the seed session"
    s.wipe()
    s.choose_signer(flow.SIGNER__COLDCARD_Q)
    assert s.signer == flow.SIGNER__COLDCARD_Q, "a new seed session chooses again"


def test_txid_answer():
    s = flow.Session()
    ok = _report(verdict=VERDICT__OK)
    assert flow.needs_txid(ok) and flow.confirm_txid(s, ok, same=True) and ok.verdict == VERDICT__OK
    bad = _report(verdict=VERDICT__OK)
    assert not flow.confirm_txid(s, bad, same=False)
    assert bad.verdict == VERDICT__FAIL and "Do not broadcast" in bad.tx_problem
    assert not flow.needs_txid(_report(verdict=VERDICT__FAIL)), "a red is red without asking"


def test_no_green_and_no_broadcast_before_the_txid():
    rep = _report(verdict=VERDICT__OK, broadcast_tx=b"\x02")
    assert flow.result_banner(rep, flow.SIGNER__TREZOR, txid_confirmed=False)[0] != flow.LEVEL__GREEN
    assert not flow.can_export(rep, txid_confirmed=False)
    assert flow.result_banner(rep, flow.SIGNER__TREZOR, txid_confirmed=True)[0] == flow.LEVEL__GREEN
    assert flow.can_export(rep, txid_confirmed=True)
    assert not flow.shows_summary(rep, txid_confirmed=False)


def test_broadcast_only_on_green_with_proven_change():
    for kw in ({"verdict": VERDICT__PARTIAL}, {"verdict": VERDICT__FAIL},
               {"verdict": VERDICT__OK, "change_unverified": True}, {"verdict": VERDICT__OK, "broadcast_tx": None}):
        kw.setdefault("broadcast_tx", b"\x02")
        rep = _report(**kw)
        actions, _ = flow.result_actions(rep, True, flow.shows_summary(rep, True), False)
        assert flow.ACTION__BROADCAST not in [a[1] for a in actions], kw


def test_red_stays_red_under_another_signer():
    s = flow.Session()
    s.signer = flow.SIGNER__COLDCARD_Q
    flow.lock_after_red(s, _report(txid="cd" * 32, verdict=VERDICT__FAIL))
    s.wipe()
    s.signer = flow.SIGNER__TREZOR
    later = _report(txid="cd" * 32, verdict=VERDICT__OK)
    flow.lock_after_red(s, later)
    assert later.verdict == VERDICT__FAIL and flow.result_banner(later, s.signer, True)[0] == flow.LEVEL__RED


def test_first_payload_kinds():
    pytest.importorskip("embit")
    from test_nonceverify import p2wpkh_psbt
    psbt = p2wpkh_psbt()
    raw = (psbt[0] if isinstance(psbt, tuple) else psbt).serialize()
    assert flow.first_payload(raw, flow.SIGNER__TREZOR)[0] == flow.FIRST__UNSIGNED
    assert flow.first_payload(raw, flow.SIGNER__COLDCARD_Q)[0] == flow.FIRST__UNSIGNED_COLDCARD
