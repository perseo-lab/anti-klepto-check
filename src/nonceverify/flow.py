"""
v7.11: the rules of the verifier's flow, apart from any screen.

What makes a result green, yellow or red for the user, what may be broadcast, what stays
red, which signer rule applies and when it is fixed: decided here, once, and only drawn
by a front end (app.py for the Seed Max hardware, 480x320 touch; others to come). A
front end may choose how a decision looks; it never takes one. Moved out of app.py
unchanged: the same code, the same texts (English, translated where they are drawn).

No PIL, no ui, no hw: standard library and the verifier's own modules only, so the same
file runs, and is reviewed, for every target.
"""
import base64
import random

from nonceverify import address, crypto, transport
from nonceverify.psbt import combine_final_tx, has_signatures, parse_psbt, parse_tx
from nonceverify.verify import (OWNER__EXTERNAL, OWNER__OURS, OWNER__UNVERIFIED,
    GRIND__EMBIT, GRIND__LIBSECP, GRIND__NONE, STATUS__FAIL,
    VERDICT__FAIL, VERDICT__OK, VERDICT__PARTIAL, verify_psbt)

# The signer under test, chosen by name on the "Seed ready" screen. Each one maps to the
# low-R grinding rule its firmware follows (verify.py keeps the three rules); the rule is
# what the nonce check uses, the name is what the user recognizes.
#   Coldcard Q: libsecp256k1, retry until r < 2^255 (low R, as Bitcoin Core);
#   SeedSigner: embit, retry until the DER signature is <= 70 bytes;
#   Trezor: trezor-crypto / secp256k1-zkp, first RFC 6979 nonce, no retry (firmware
#     source: core/src/apps/bitcoin/common.py ecdsa_sign -> secp256k1.sign with no
#     canonical callback -> crypto/ecdsa.c or zkp_ecdsa.c, retry counter 0; confirmed on
#     a real Trezor on 8 Nov 2026).
SIGNER__COLDCARD_Q = "coldcard_q"
SIGNER__SEEDSIGNER = "seedsigner"
SIGNER__TREZOR = "trezor"
SIGNERS = {
    SIGNER__COLDCARD_Q: ("Coldcard Q", GRIND__LIBSECP),
    SIGNER__SEEDSIGNER: ("SeedSigner", GRIND__EMBIT),
    SIGNER__TREZOR: ("Trezor", GRIND__NONE),
}
SIGNER_ORDER = (SIGNER__COLDCARD_Q, SIGNER__SEEDSIGNER, SIGNER__TREZOR)
GRINDING_SHORT = {GRIND__LIBSECP: "libsecp", GRIND__EMBIT: "embit", GRIND__NONE: "none"}

# Levels of a verdict as shown to the user; each front end maps them to its colors
LEVEL__GREEN = "green"
LEVEL__YELLOW = "yellow"
LEVEL__RED = "red"

# v7.5: randomness for the checks that must not be predictable (the xpub groups to find
# on the paper). The OS's CSPRNG; tests swap in a fixed one.
RNG = random.SystemRandom()


def signer_name(signer: str) -> str:
    return SIGNERS[signer][0]


def signer_grinding(signer: str) -> str:
    return SIGNERS[signer][1]


def show_spaces(text: str) -> str:
    """ Spaces made visible (the keyboard can't type a middle dot, so no ambiguity) """
    return text.replace(" ", "·")


def btc(sats) -> str:
    if sats is None:
        return "?"
    return f"{sats / 1e8:.8f} BTC"


def btc_amount(sats) -> str:
    """ v7.9: the amount alone, as Sparrow writes it in BTC (the unit is drawn apart) """
    return "?" if sats is None else f"{sats / 1e8:.8f}"


def txid_rows(txid: str) -> list:
    """ The 64 hex digits in 4 rows of 4 groups of 4, as they are compared by eye """
    groups = [txid[i:i + 4] for i in range(0, len(txid), 4)]
    return [" ".join(groups[i:i + 4]) for i in range(0, len(groups), 4)]


# ---------------------------------------------------------------------------------------
# The session
# ---------------------------------------------------------------------------------------
class Session:
    """ What the app keeps between screens: the BIP32 master node, nothing else secret """
    def __init__(self):
        self.master = None
        self.words = 0
        self.has_passphrase = False
        self.signer = None               # chosen by name after every seed load
        self.signer_locked = False       # True once "Scan PSBT" was pressed in this seed session
        self.failed = {}                 # txid -> signer it was red under; kept until power-off (v7)
        self.descriptor = None           # v7: wallet descriptor for "Check address" (public data)
        # v7.5: (pubkey, signature) pairs whose nonce a seed of this power-on verified,
        # green and txid confirmed. Public data, kept across "Change seed": a multisig's
        # cosigner signatures become checked when their own seed is loaded and the same
        # PSBT scanned again.
        self.clean_sigs = set()
        self.coldcard_intro_shown = False

    def wipe(self):
        if self.master is not None:
            self.master.wipe()
        self.master = None
        self.signer = None
        self.signer_locked = False
        # self.failed is kept: a transaction that came out red stays red until power-off,
        # also after "Change seed" (txids are public data)
        self.words = 0
        self.has_passphrase = False
        # v7.6 review: the descriptor is kept (public data, every key of it verified by
        # derivation or on the paper): the cosigner's seed checks the same multisig change

    def set_seed(self, mnemonic: str, passphrase: str):
        if self.master is not None:
            self.master.wipe()
        self.master = crypto.HDKey.from_seed(crypto.bip39_seed(mnemonic, passphrase))
        self.words = len(mnemonic.split())
        self.has_passphrase = bool(passphrase)

    @staticmethod
    def fingerprint_of(mnemonic: str, passphrase: str) -> str:
        node = crypto.HDKey.from_seed(crypto.bip39_seed(mnemonic, passphrase))
        try:
            return node.fingerprint.hex()
        finally:
            node.wipe()

    def choose_signer(self, signer):
        """ The device named on the seed screen; ignored once the session's signer is fixed """
        if not self.signer_locked:
            self.signer = signer

    def lock_signer(self) -> bool:
        """
        One signer per seed session, fixed as soon as a scan starts (v7; before, after the
        first verdict). Each rule accepts exactly one signature, but the rules differ: a
        Coldcard that skipped its low-R grinding is red as "Coldcard Q" and, about half the
        time, green as "Trezor". If the name could change after a scan, the signer's choice
        of rule would come back through the user. False (no scan) without a signer.
        """
        if self.signer not in SIGNERS:
            return False
        self.signer_locked = True
        return True


# ---------------------------------------------------------------------------------------
# A PSBT: assembling the QR codes, checking, the txid, what stays red
# ---------------------------------------------------------------------------------------
FIRST__FINAL_TX = "final_tx"                  # v7.2 Coldcard Q: the unsigned PSBT comes second
FIRST__SIGNED = "signed"                      # a signed PSBT: checked as it is
FIRST__UNSIGNED_COLDCARD = "unsigned_coldcard"  # Coldcard Q: the final transaction comes second
FIRST__UNSIGNED = "unsigned"                  # not signed, not a Coldcard: scan the signed one


def first_payload(first: bytes, signer: str):
    """
    (kind, psbt or None) for the first QR (or QR series) scanned. A final transaction
    (Coldcard Q) is parsed to reject garbage early; it needs the unsigned PSBT next.
    Raises PSBTError / ValueError on a payload that is neither.
    """
    if transport.looks_like_final_tx(first):
        parse_tx(first)
        return FIRST__FINAL_TX, None
    psbt = parse_psbt(first)
    if has_signatures(psbt):
        return FIRST__SIGNED, psbt
    if signer == SIGNER__COLDCARD_Q:
        return FIRST__UNSIGNED_COLDCARD, psbt
    return FIRST__UNSIGNED, psbt


def combine(kind: str, first, second: bytes):
    """ v7.2: the PSBT to check from a final transaction + unsigned PSBT pair, either order """
    if kind == FIRST__FINAL_TX:
        return combine_final_tx(parse_psbt(second), first)
    return combine_final_tx(first, second)


def second_payload_problem(second: bytes, final: bool):
    """
    The second QR of the pair must be the other half: the final transaction after an
    unsigned PSBT (final=True), the unsigned PSBT after a final transaction. The message
    to show, or None.
    """
    if transport.looks_like_final_tx(second) == final:
        return None
    return transport.NOT_FINAL_TX_MESSAGE if final else "this is the final transaction again: scan the unsigned PSBT"


def check(psbt, session: Session, progress=None, scan_progress=None):
    """ The nonce check of `psbt` with the session's seed, signer rule and descriptor """
    return verify_psbt(psbt, session.master, progress=progress, scan_progress=scan_progress,
                       grinding=signer_grinding(session.signer), clean_elsewhere=session.clean_sigs,
                       descriptor=session.descriptor)


def needs_txid(report) -> bool:
    """ v7: no green before the txid has been compared with the host's """
    return report.verdict in (VERDICT__OK, VERDICT__PARTIAL)


def confirm_txid(session: Session, report, same: bool) -> bool:
    """
    The user's answer to "same txid?". Same: the signatures checked here count as clean
    for the cosigners of this power-on. Different: red, whatever the nonces said. Returns
    whether the txid is confirmed.
    """
    if same:
        for r in report.inputs:
            session.clean_sigs.update(r.checked_sigs)
        return True
    report.verdict = VERDICT__FAIL
    report.tx_problem = ("The txid is NOT the one in Sparrow: the transaction checked here is not "
                         "the one Sparrow would broadcast. Do not broadcast.")
    # v7.5 review: a txid mismatch says nothing about the
    # signer: it is not recorded as red for the other seeds and devices of a multisig
    return False


def lock_after_red(session: Session, report):
    """
    Defence in depth behind Session.signer_locked: a transaction that came out red stays
    red for the rest of this seed session, under whatever signer.
    """
    earlier = session.failed.get(report.txid) if report.txid else None
    if earlier is not None and earlier != session.signer and report.verdict != VERDICT__FAIL:
        report.verdict = VERDICT__FAIL
        message = (f"This transaction already came out NOT valid with «{signer_name(earlier)}». "
                   "Changing the signer doesn't make it clean: do not broadcast.")
        report.tx_problem = message + (" " + report.tx_problem if report.tx_problem else "")
    # "SEED DOES NOT MATCH" (wrong seed or passphrase) says nothing about the signer: not kept
    seed_mismatch = not report.seed_matches and not report.tx_problem and \
        not any(r.status == STATUS__FAIL for r in report.inputs)
    if report.verdict == VERDICT__FAIL and report.txid and report.txid not in session.failed and not seed_mismatch:
        session.failed[report.txid] = session.signer


def can_export(report, txid_confirmed: bool) -> bool:
    """
    v7.5 review: the Tx QR only on green. On "this seed clean" the transaction would carry
    the unchecked cosigner signature, or is not complete; v7.6: not with an unproven change.
    """
    return bool(txid_confirmed and report.broadcast_tx and report.verdict == VERDICT__OK
                and not report.change_unverified)


# ---------------------------------------------------------------------------------------
# The result, as words and levels
# ---------------------------------------------------------------------------------------
def seed_mismatch(report) -> bool:
    """ Red only because no input belongs to this seed: wrong seed or passphrase """
    return not report.seed_matches and report.verdict == VERDICT__FAIL and \
        not any(r.status == STATUS__FAIL for r in report.inputs)


def shows_summary(report, txid_confirmed: bool, details: bool = False) -> bool:
    """
    v7.9: with the txid confirmed and the nonces clean (green, or a yellow that is not a
    red), the result opens on the summary: where the money goes, the change, the fee. A
    red or an incomplete check is a list, reason first.
    """
    return (not details and txid_confirmed and report.verdict in (VERDICT__OK, VERDICT__PARTIAL)
            and not seed_mismatch(report))


def outputs_by_owner(report):
    """ (external, ours, unverified) outputs """
    return ([o for o in report.outputs if o.owner == OWNER__EXTERNAL],
            [o for o in report.outputs if o.owner == OWNER__OURS],
            [o for o in report.outputs if o.owner == OWNER__UNVERIFIED])


def result_banner(report, signer, txid_confirmed: bool):
    """ (level, icon, headline, subline) of the result as a list """
    if seed_mismatch(report):
        return LEVEL__RED, "x_circle", "SEED DOES NOT MATCH", "check seed and passphrase"
    if report.verdict == VERDICT__OK and txid_confirmed and report.change_unverified:
        return LEVEL__YELLOW, "warning", "CHANGE NOT VERIFIED", "do not broadcast yet: see below"
    if report.verdict == VERDICT__OK and txid_confirmed and report.change_warning:
        return LEVEL__YELLOW, "warning", "NONCE OK · CHANGE?", "your change is somewhere unusual: see below"
    if report.verdict == VERDICT__OK and txid_confirmed:
        who = signer_name(signer) if signer in SIGNERS else None
        what = "tap Broadcast" if report.broadcast_tx else "broadcast"
        return LEVEL__GREEN, "ok_circle", "NONCE OK", (f"{who} signatures clean, txid OK: {what}"
                                                       if who else f"no covert channel, txid OK: {what}")
    if report.verdict == VERDICT__PARTIAL and txid_confirmed:
        if report.unchecked_cosigners:
            return LEVEL__YELLOW, "warning", "THIS SEED: CLEAN", \
                f"do not broadcast yet: {report.unchecked_cosigners} cosigner signature(s) to check"
        return LEVEL__YELLOW, "warning", "THIS SEED: CLEAN", "not complete: scan again when fully signed"
    if report.verdict in (VERDICT__OK, VERDICT__PARTIAL):
        # never shown by the app (the txid step comes first), kept for safety
        return LEVEL__YELLOW, "warning", "COMPARE THE TXID", "nonces OK: compare the txid before broadcasting"
    if report.verdict == VERDICT__FAIL:
        return LEVEL__RED, "x_circle", "DO NOT BROADCAST", "a signature or the transaction is not what it must be"
    return LEVEL__YELLOW, "warning", "INCOMPLETE CHECK", "not everything can be verified: not green"


def summary_banner(report, signer):
    """ v7.9: (level, icon, headline, subline), short enough for the summary's banner """
    if report.verdict == VERDICT__OK and report.change_unverified:
        return LEVEL__YELLOW, "warning", "CHANGE NOT VERIFIED", "do not broadcast yet"
    if report.verdict == VERDICT__OK and report.change_warning:
        return LEVEL__YELLOW, "warning", "CHANGE?", "nonce OK · check below"
    if report.verdict == VERDICT__OK:
        who = signer_name(signer) if signer in SIGNERS else None
        return LEVEL__GREEN, "ok_circle", "NONCE OK", f"{who} · txid OK" if who else "txid OK"
    if report.unchecked_cosigners:
        return LEVEL__YELLOW, "warning", "THIS SEED: CLEAN", f"{report.unchecked_cosigners} cosigner sig. to check"
    return LEVEL__YELLOW, "warning", "THIS SEED: CLEAN", "not complete"


def summary_note(report):
    """ v7.9: (text, level) of the one line under the fee when something must be read in Details """
    if report.verdict == VERDICT__PARTIAL and report.unchecked_cosigners:
        return "Do not broadcast yet: cosigners to check, see Details", LEVEL__YELLOW
    if report.verdict == VERDICT__PARTIAL:
        return "Not fully signed yet: scan again when it is", LEVEL__YELLOW
    if report.extra_fields:
        return f"{report.extra_fields} extra PSBT field(s): broadcast only with Broadcast", LEVEL__YELLOW
    return None, None


# Actions on the result: what each button returns to the flow
ACTION__DETAILS = "details"
ACTION__BROADCAST = "txqr"
ACTION__NEXT = "again"
ACTION__FINISH = "done"
ACTION__BACK = "back"


def result_actions(report, txid_confirmed: bool, summary: bool, details: bool):
    """
    ([(label, action, icon)], primary index or None): the buttons of the result. Broadcast
    only when can_export(); on a change in an unusual place "Next PSBT" is the default.
    """
    export = can_export(report, txid_confirmed)
    if summary:
        # v7.9: Finish moves to Details; what to do with the result stays here
        if export:
            return ([("Details", ACTION__DETAILS, None), ("Broadcast", ACTION__BROADCAST, "qr"),
                     ("Next PSBT", ACTION__NEXT, "camera")], 2 if report.change_warning else 1)
        return [("Details", ACTION__DETAILS, None), ("Next PSBT", ACTION__NEXT, "camera")], 1
    if details:
        return [("Finish", ACTION__FINISH, "power"), ("Back", ACTION__BACK, "back")], 1
    if export:
        return ([("Finish", ACTION__FINISH, "power"), ("Broadcast", ACTION__BROADCAST, "qr"),
                 ("Next PSBT", ACTION__NEXT, "camera")], 2 if report.change_warning else 1)
    return [("Finish", ACTION__FINISH, "power"), ("Next PSBT", ACTION__NEXT, "camera")], 1


# ---------------------------------------------------------------------------------------
# Broadcast: the transaction checked here, as BBQr
# ---------------------------------------------------------------------------------------
# v7.5: the verified transaction as BBQr (Coinkite), file type "T", base32: Sparrow reads
# it with File > Load Transaction > From QR (and Coldcard Q too). Parts sized for QR
# version 8 (M): 4-pixel modules in the 230-pixel box, easy for a webcam.
BBQR_PART_CHARS = 192


def bbqr_parts(raw: bytes, file_type: str = "T", part_chars: int = BBQR_PART_CHARS) -> list:
    data = base64.b32encode(raw).decode("ascii").rstrip("=")
    chunks = [data[i:i + part_chars] for i in range(0, len(data), part_chars)] or [""]
    if len(chunks) > 36 * 36 - 1:
        raise ValueError("transaction too large for BBQr")

    def b36(n):
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return digits[n // 36] + digits[n % 36]
    return [f"B$2{file_type}{b36(len(chunks))}{b36(i)}{c}" for i, c in enumerate(chunks)]


# ---------------------------------------------------------------------------------------
# Descriptor: the cosigners' keys checked on the paper
# ---------------------------------------------------------------------------------------
KEY_CHECK_GROUPS = 3


def key_dependent_start(xpub_text: str) -> int:
    """
    v7.5 review: the first character of the xpub that depends on its PUBLIC KEY. Base58
    writes the 78 bytes as one number: the leading ~60 characters are fixed by version,
    depth, parent fingerprint, child number and chain code, all public, so a look-alike
    key with the real chain code matches them for free. Found by changing the key and
    seeing where the text changes (a few variants: the earliest difference wins).
    """
    from nonceverify.psbt import base58check
    raw = address.b58decode_check(xpub_text)
    first = len(xpub_text)
    for n in range(1, 9):
        other = crypto.pubkey_compressed(crypto.point_mul_g(n * 0x1000003 + 7))
        text = base58check(raw[:45] + other)
        first = min(first, next((i for i, (a, b) in enumerate(zip(text, xpub_text)) if a != b), first))
    return first


def pick_groups(xpub_text: str, rng=None, count: int = KEY_CHECK_GROUPS) -> list:
    """
    Group indexes (groups of four) to find on the paper, chosen by the device at random
    among the groups that depend on the public key, the last (short) group excluded.
    Matching one unpredictable group costs a forger ~58^4 = 2^23 tries per key and
    group; matching enough of them to pass three random picks is out of reach.
    """
    rng = rng or RNG
    groups = address.grouped(xpub_text).split(" ")
    lo = (key_dependent_start(xpub_text) + 3) // 4            # first whole group after the change
    hi = len(groups) - 1 if len(groups[-1]) < 4 else len(groups)
    pool = list(range(lo, hi))
    picked = []
    for _ in range(min(count, len(pool))):
        picked.append(pool.pop(rng.randrange(len(pool))))
    return sorted(picked)


# ---------------------------------------------------------------------------------------
# v7.3: address explorer
# ---------------------------------------------------------------------------------------
EXPLORER_PAGE = 4                     # v7.5: 40-pixel rows (were 6 of 26)
EXPLORER_MAX_INDEX = 0x7FFFFFFF - EXPLORER_PAGE
EXPLORER_MAX_ACCOUNT = 99


def indexed(explorer) -> bool:
    """ Addresses numbered by an index (a descriptor without /* has a single address) """
    return getattr(explorer, "wildcard", lambda: True)()


# ---------------------------------------------------------------------------------------
# v7.12: the steps of a session, for any front end
# ---------------------------------------------------------------------------------------
# The order of the steps is part of the check (no result before the txid, the signer fixed
# at the first scan, red kept): it is written here once. A front end draws each step in
# its own way and returns what the user chose. What it must offer (duck typing):
#
#   splash()                                  until the user starts
#   home() -> "scan_seed" | "type_seed"       how to load the seed
#   scan(heading, on_payload, topic, errors=()) -> True | None (back)
#       on_payload(bytes) -> (done, progress 0-1, note), may raise one of `errors`
#   type_mnemonic() -> mnemonic | None
#   passphrase_question(xfp, words) -> "none" | "enter"
#   passphrase_keyboard(text) -> text
#   confirm_passphrase(passphrase, xfp) -> "ok" | "edit"
#   seed_ready(xfp, words, has_passphrase, signer, locked) -> (choice, signer)
#       choice: "scan_psbt" | "change_seed" | "address" | other (back to the same screen)
#   message(heading, body, tone, icon, buttons=("OK",), values=None, primary=0) -> value
#       tone: TONE__ACCENT | TONE__YELLOW | TONE__RED
#   working() -> progress callable (index, total), with .scan(index, total)
#   txid_check(report) -> "same" | other
#   result(report, signer, txid_confirmed, details) -> one of the ACTION__ values
#   broadcast(report)
#   address(session)                          optional: the address checks (v7)
#   error(exception)                          an unexpected error, the seed kept
TONE__ACCENT = "accent"
SWITCH_OFF__UPS_HAT = "Switch off with the UPS HAT switch: that clears the RAM completely."
TONE__YELLOW = "yellow"
TONE__RED = "red"


class QRPayload:
    """ One QR (or one series of QR parts) collected by fe.scan() """
    def __init__(self, collector=None):
        self.collector = collector or transport.PSBTCollector()
        self.result = None

    def __call__(self, payload):
        c = self.collector
        c.restarted = False
        c.add(payload)
        note = "QR of another PSBT: starting over" if c.restarted else ""
        return c.complete, c.progress, note


def load_seed(fe, session: Session, method: str = "scan_seed") -> bool:
    if method == "type_seed":
        mnemonic = fe.type_mnemonic()
        if mnemonic is None:
            return False
    else:
        found = {}

        def on_payload(payload):
            from nonceverify import seedqr
            found["mnemonic"] = seedqr.decode(payload)
            return True, 1.0, ""

        if fe.scan("SeedQR", on_payload, "seed") is None:
            return False
        mnemonic = found.pop("mnemonic")
    words = len(mnemonic.split())
    choice = fe.passphrase_question(Session.fingerprint_of(mnemonic, ""), words)
    passphrase = ""
    if choice == "enter":
        while True:
            passphrase = fe.passphrase_keyboard(passphrase)
            if fe.confirm_passphrase(passphrase, Session.fingerprint_of(mnemonic, passphrase)) == "ok":
                break
    session.set_seed(mnemonic, passphrase)
    del mnemonic, passphrase
    return True


def scan_second(fe, heading: str, final: bool):
    """ The second QR of a final transaction + unsigned PSBT pair (v7.2), raw bytes or None """
    state = {"collector": transport.PSBTCollector(), "result": None}

    def on_payload(payload):
        collector = state["collector"]
        collector.restarted = False
        collector.add(payload)
        if collector.complete:
            state["collector"] = transport.PSBTCollector()         # wrong kind: start clean
            problem = second_payload_problem(collector.result, final)
            if problem:
                raise transport.TransportError(problem)
            state["result"] = collector.result
            return True, 1.0, ""
        return False, collector.progress, "QR of another PSBT: starting over" if collector.restarted else ""

    if fe.scan(heading, on_payload, "scan_psbt") is None:
        return None
    return state["result"]


def check_psbt(fe, session: Session, log=None) -> str:
    """ Scan, check, txid, result. Returns "again" (next PSBT), "back", "done" (Finish) or "keep" """
    from nonceverify.psbt import PSBTError
    payload = QRPayload()
    coldcard = session.signer == SIGNER__COLDCARD_Q
    if coldcard and not session.coldcard_intro_shown:
        session.coldcard_intro_shown = True
        fe.message("Coldcard Q: two QR codes", "Both from Sparrow, in any order:\n"
                   "1. the signed transaction: load the Q's .txn in Sparrow, then show it as QR;\n"
                   "2. the UNSIGNED PSBT of the same transaction.\n"
                   "At the end, broadcast the Tx QR shown here.",
                   TONE__ACCENT, "camera", buttons=("Scan",))
    heading = f"PSBT · {signer_name(session.signer)}"
    if fe.scan(heading, payload, "scan_psbt") is None:
        return "back"
    try:
        first = payload.collector.result
        kind, psbt = first_payload(first, session.signer)
        if kind == FIRST__FINAL_TX:
            # v7.2: a final transaction (Coldcard Q): its unsigned PSBT gives the amounts
            fe.message("1 of 2: final transaction read",
                       "Now the UNSIGNED PSBT of the same transaction, from Sparrow: it carries the "
                       "amounts and paths needed to check the signatures.",
                       TONE__ACCENT, "camera", buttons=("Scan unsigned PSBT",))
            unsigned = scan_second(fe, "2 of 2: unsigned PSBT", final=False)
            if unsigned is None:
                return "back"
            psbt = combine(kind, first, unsigned)
        elif kind == FIRST__UNSIGNED:
            fe.message("PSBT without signatures", "This is the unsigned PSBT. Scan the SIGNED one "
                       "from Sparrow (after loading what the signer returned).", TONE__YELLOW, "warning")
            return "again"
        elif kind == FIRST__UNSIGNED_COLDCARD:
            fe.message("1 of 2: unsigned PSBT read",
                       "Now the signed transaction, from Sparrow (the Q's .txn loaded there).",
                       TONE__ACCENT, "camera", buttons=("Scan final transaction",))
            final = scan_second(fe, "2 of 2: final transaction", final=True)
            if final is None:
                return "back"
            psbt = combine(kind, psbt, final)
        working = fe.working()
        report = check(psbt, session, progress=working, scan_progress=working.scan)
    except (PSBTError, ValueError) as e:
        fe.message("PSBT not readable", str(e)[:160] + ". Scan it again from Sparrow; if it keeps "
                   "failing, export the PSBT again.", TONE__RED, "x_circle")
        return "again"
    except Exception as e:
        if log is not None:
            log.exception("verification error")
        fe.message("Verification error", f"{type(e).__name__}: not checked, so not green. The seed "
                   "stays loaded: try the scan again.", TONE__RED, "warning")
        return "again"
    lock_after_red(session, report)
    confirmed = False
    if needs_txid(report):
        # v7: no green before the txid has been compared with Sparrow's (v7.8: read and
        # confirm, no quiz on the ending)
        confirmed = confirm_txid(session, report, fe.txid_check(report) == "same")
    while True:
        choice = fe.result(report, session.signer, confirmed, False)
        if choice == ACTION__BROADCAST and can_export(report, confirmed):
            fe.broadcast(report)
        elif choice == ACTION__DETAILS:
            # v7.9: txid, XFP, inputs, outputs; Finish is here, Back returns to the summary
            if fe.result(report, session.signer, confirmed, True) == ACTION__FINISH:
                return "done"
        elif choice == ACTION__BROADCAST:
            continue                         # never without can_export(), whatever the screen offered
        else:
            return choice


def confirm_wipe(fe) -> bool:
    """ v7.5: wiping the seed means typing it all again: ask, the destructive choice on the left """
    choice = fe.message("Wipe the seed?", "Seed and passphrase are removed from memory: to check "
                        "anything else you will load them again.", TONE__YELLOW, "lock",
                        buttons=("Wipe", "Keep"), values=["wipe", "keep"], primary=1)
    return choice == "wipe"


def run(fe, session: Session = None, splash: bool = True, log=None):
    """ The whole session: seed, signer, PSBTs, until power-off """
    from nonceverify import seedqr
    session = session or Session()
    if splash:
        fe.splash()                          # v7.4: until START
    while True:
        if session.master is None:
            method = fe.home()
            try:
                if not load_seed(fe, session, method):
                    continue
            except seedqr.SeedQRError as e:
                fe.message("Seed not valid", str(e), TONE__RED, "x_circle")
                continue
        choice, signer = fe.seed_ready(session.master.fingerprint.hex(), session.words, session.has_passphrase,
                                       session.signer, session.signer_locked)
        session.choose_signer(signer)
        if choice == "change_seed":
            if confirm_wipe(fe):
                session.wipe()
            continue
        if choice == "address" and hasattr(fe, "address"):
            fe.address(session)
            continue
        # v7.11: the signer is fixed as soon as a scan starts (Session.lock_signer)
        if choice != "scan_psbt" or not session.lock_signer():
            continue
        while True:
            outcome = check_psbt(fe, session, log)
            if outcome == "again":
                continue
            if outcome == "done" and not confirm_wipe(fe):
                outcome = "keep"             # v7.5: "Finish" asks first; "Keep" goes back to the seed
            break
        if outcome == "done":
            session.wipe()
            # how the power goes off depends on the hardware: the front end says it
            fe.message("Seed wiped", "Seed and passphrase have been removed from the app's memory.\n\n"
                       + getattr(fe, "SWITCH_OFF", SWITCH_OFF__UPS_HAT), TONE__ACCENT, "lock", buttons=("Start again",))
