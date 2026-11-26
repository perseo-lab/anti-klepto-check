"""
v7.9: "what to do and why", one page per step, opened with the
"?" in the header (in the scan screens: the "?" on the left, above Back). The pages are
plain text, written here once; the screens only name their topic.

Standard library and PIL only, as the rest of the verifier.
"""
from nonceverify import ui
from nonceverify.hw import HEIGHT, WIDTH, Event

# topic -> (title, [(section, text), ...]). Text: English, as the rest of the interface.
TOPICS = {
    "home": ("What this SD does", [
        ("WHAT IT IS", "A second SD for the same device. It never signs: it checks, offline, the signatures "
                       "your signer made, before you broadcast them."),
        ("WHY", "A signer with malicious firmware can hide your seed inside normal-looking signatures, in "
                "the nonce (Dark Skippy). The coins move as you wanted; the attacker reads your seed from "
                "the blockchain and takes the rest."),
        ("HOW", "Load the same seed here. For every signature of this seed, the nonce the signer was "
                "obliged to use (RFC 6979, deterministic) is recomputed and compared. Any other nonce: red."),
        ("STEPS", "1. Load the seed: SeedQR or words, then the passphrase.\n"
                  "2. Choose the device that signed; scan the signed PSBT from Sparrow.\n"
                  "3. Compare the txid, read the result, tap Broadcast and load that QR in Sparrow."),
        ("SAFETY", "The seed lives only in RAM. The microSD is remounted read-only: nothing is written. "
                   "When you are done, switch off with the switch: the RAM is lost."),
    ]),
    "seed": ("Loading the seed", [
        ("DO", "Load exactly the seed and the passphrase of the wallet that signed: the SeedQR, or the "
               "words typed one by one, then the passphrase if you use one."),
        ("WHY", "Your keys are recomputed here from the seed. Another seed, or one character of "
                "passphrase different, gives other keys: nothing to check, or \"seed does not match\"."),
        ("WORDS", "Only the letters that can still lead to a BIP39 word are active. When four or fewer words are left they are offered: pick yours. At the end every word is checked with the checksum."),
        ("SEEDQR", "Standard and compact SeedQR, 12 or 24 words. If it doesn't read: the QR full screen, zoom 1x, 20-30 cm away, no reflections."),
        ("PRIVACY", "Words and passphrase stay hidden until Show: an audience or a camera can't read them. "
                    "With a wrong checksum the words are shown, so you can find the wrong one."),
        ("SAFETY", "RAM only, never written to the microSD. Change seed and Finish wipe it; switching off "
                   "clears the RAM completely."),
    ]),
    "signer": ("Seed ready: who signed?", [
        ("XFP", "The fingerprint of the seed and passphrase just loaded. It must be the XFP on your backup "
                "and in Sparrow's wallet. Different: wrong seed or wrong passphrase."),
        ("WHICH DEVICE", "Each firmware has its own \"low R\" rule (retrying until the signature is one "
                         "byte shorter): Coldcard Q follows libsecp256k1, SeedSigner embit, Trezor none. The "
                         "nonce is recomputed with that exact rule: choose the device that really signed, "
                         "or a clean signature looks red."),
        ("WHY IT IS FIXED", "Once you scan, the device can't change until Change seed. After a red, "
                            "trying the other names until one turns green would hide a real leak."),
        ("NEXT", "Scan PSBT: the signed transaction, from Sparrow. Address: check an address of this "
                 "wallet, or list your addresses (Explorer)."),
    ]),
    "scan_psbt": ("Scan the signed PSBT", [
        ("DO", "In Sparrow, load what the signer returned, then show the signed PSBT as QR (File > Show "
               "PSBT as QR), before broadcasting anything."),
        ("COLDCARD Q", "It returns the final transaction (.txn): load it in Sparrow and show it as QR, then "
                       "scan the UNSIGNED PSBT of the same transaction too. Any order."),
        ("WHY", "The PSBT carries the signatures and what is needed to recompute their nonces: amounts, "
                "scripts, derivation paths. A final transaction alone has no amounts: the unsigned PSBT "
                "supplies them, and wrong amounts make the signatures invalid, i.e. red."),
        ("TIP", "Zoom (right) if the QR is small. Keep the screen still: an animated QR is collected part "
                "by part, the ring shows how much."),
    ]),
    "txid": ("Compare the txid", [
        ("DO", "In Sparrow, the transaction tab shows the Transaction ID. Compare all four rows with this "
               "screen. Same: tap Same txid. Different: tap Different."),
        ("WHY", "The nonce check says THIS PSBT is clean. The txid ties it to the transaction Sparrow "
                "holds: if they differ, Sparrow would broadcast something that was not checked."),
        ("NOTE", "A segwit txid does not cover the signatures. That is why, at the end, you broadcast the "
                 "transaction made here (Broadcast), not Sparrow's own."),
    ]),
    "result": ("Reading the result", [
        ("GREEN", "Every signature of this seed uses the nonce it had to use, sighash ALL, low S, and the "
                  "txid is Sparrow's. Tap Broadcast."),
        ("CHECKS", "Four checks, each named on the result: Nonce, Sighash ALL, Txid, Change address. All four green: broadcast. Each one is explained below."),
        ("NONCE", "Recomputed here with RFC 6979 from your key and the transaction, and compared with the nonce inside every signature of this seed. Any other nonce can carry your seed out (Dark Skippy): red."),
        ("SIGHASH ALL", "Every signature, cosigners' included, must commit to all the inputs and all the outputs (SIGHASH_ALL), in strict DER with low S. NONE, SINGLE or ANYONECANPAY would let someone change the transaction after you signed: red."),
        ("CHANGE ADDRESS", "Certified: the change address is derived here from your seed (multisig: from the descriptor you confirmed, or the same quorum as the coins spent) and is exactly the output's. Proven, not read from the PSBT's labels. Not certified: yellow, and no Broadcast."),
        ("SENDS TO", "The amount and the WHOLE address that receives it. Compare it with the address you "
                     "meant to pay (from the invoice, from the person): malware on a computer swaps "
                     "addresses."),
        ("YELLOW", "Not red, not ready: change where a wallet won't look, change that can't be proven, "
                   "cosigners still to check, not fully signed. Read the card and Details; broadcast only "
                   "when you understand why."),
        ("RED", "Do not broadcast. A wrong nonce means this signer can't be trusted with this seed: keep "
                "the PSBT, stop using the signer, move the coins with another device."),
        ("DETAILS", "Txid, XFP, every input and output, locktime. Finish is there: it wipes the seed."),
    ]),
    "broadcast": ("Broadcast THIS", [
        ("DO", "In Sparrow: File > Load Transaction > From QR, and show this animated QR to the webcam. "
               "Sparrow opens it in a NEW tab: check the txid is the same, tap Broadcast in that tab, close "
               "the old tab without broadcasting."),
        ("WHY", "A segwit txid does not cover the signatures: the same transaction can exist with other "
                "signatures. A signer could show clean ones and write leaking ones to its file. This QR is "
                "rebuilt here only from the signatures just checked: the one copy proven clean."),
        ("PRIVACY", "Broadcast from Sparrow connected to your own node: a public explorer learns your IP "
                    "with your transaction."),
        ("LIMIT", "A compromised Sparrow already holds the PSBT's signatures. This protects from an honest "
                  "Sparrow broadcasting other witnesses, not from a compromised computer."),
    ]),
    "address": ("Check an address", [
        ("CHECK", "Scan an address (or a bitcoin: QR) that Sparrow shows or that you will give to a payer. "
                  "It is searched among this wallet's addresses, derived here from the seed. Green: yours."),
        ("WHY", "Malware can show you an attacker's address to receive into. Checking it on an offline "
                "device, with your seed, proves where the coins will land."),
        ("MULTISIG", "Needs the wallet descriptor, scanned from your paper backup and checked key by key."),
        ("EXPLORER", "Lists your addresses, derived here, with their QR: take a receive address from here "
                     "instead of from the computer."),
        ("RED QR", "A bitcoin: QR with lightning=, pj= or other instructions is red: a payer's wallet could "
                   "follow those instead of paying the address."),
    ]),
    "descriptor": ("Descriptor check", [
        ("DO", "Scan the descriptor QR from your PAPER backup (Sparrow's PDF). Your key is checked by "
               "derivation. For each other key, find on the paper the groups highlighted here; then "
               "confirm M of N."),
        ("WHY", "A forged descriptor can carry look-alike keys: same start, same end, even the same "
                "checksum. It can't match groups picked at random here from the part of the xpub that "
                "depends on the key. A changed threshold (1 of 4) is caught by the last question."),
        ("KEPT", "The descriptor stays in RAM until you switch off, never on the microSD: public data, "
                 "but it reveals your wallet."),
    ]),
    "explorer": ("Explorer", [
        ("WHAT", "Your addresses, derived on this device from the seed (single-sig) or from the confirmed "
                 "descriptor (multisig). Recv / Chg, account - / +, Go to #."),
        ("DO", "Tap an address: its QR and the address in groups of four. The QR is read back by the "
               "camera's decoder before it is shown: if it doesn't read exactly the address, no QR."),
        ("WHY", "A receive address taken from here doesn't depend on the computer."),
    ]),
    # v7.14: the passphrase, the start, the donation
    "passphrase": ("The passphrase", [
        ("DO", "Type the passphrase exactly as in the wallet that signed: capitals, spaces and symbols count. The XFP shown at the end must be the one in Sparrow's wallet."),
        ("WHY", "The same words with another passphrase are another wallet: other keys, another XFP. A typo gives no error, it gives a different, empty wallet: the XFP is the check."),
        ("SPACES", "Spaces are shown as ·: a space at the start or at the end is easy to miss and changes the wallet."),
        ("SAFETY", "RAM only, hidden until Show, never written to the microSD."),
    ]),
    "start": ("Before you start", [
        ("LANGUAGE", "Language and host are chosen here, before START. RAM only: at every power-on the device starts again in English, with Sparrow."),
        ("HOST", "Sparrow loads back the transaction from this device's QR: the strongest check. Nunchuk can't load a second copy: you compare the whole txid instead."),
        ("MICROSD", "The microSD is remounted read-only at start and checked every second. Nothing is ever written: no seed, no settings, no logs."),
        ("NEXT", "START, then load the seed. Every step has its help page, like this one."),
    ]),
    "donate": ("Support the project", [
        ("WHAT", "Anti-Skippy Check is free and open source. If it helped you, a donation keeps it going: Lightning (BOLT12) or on-chain with Silent Payments."),
        ("VERIFY", "These details are signed with the author's key (PGP 513B 3583 0E4F 869E FC6D 9534 F1A0 5CB1 6C89 8D92) in docs/DONATE.txt.asc. A fork could change this screen, not the signature: check it on the project page."),
        ("PRIVACY", "Silent Payments: every payment lands on a new Taproot output, never linkable from outside. BOLT12: a reusable offer, no invoice to ask for."),
        ("NOTHING SENT", "This device only shows QR codes: scan them with your phone. Nothing leaves the device."),
    ]),
}


class HelpScreen(ui.Screen):
    """ One topic: title, then sections (heading in teal, text), scrolled by tap or swipe """
    header_label = "HELP"

    def __init__(self, topic: str):
        super().__init__()
        self.title_text, sections = TOPICS[topic]
        lines = []
        width = WIDTH - 3 * ui.PAD
        for name, text in sections:
            lines.append((name, ui.ACCENT, 14, True))
            for line in ui.wrap(text, ui.font(17), width):
                lines.append((line, ui.TEXT, 17, False))
            lines.append(("", ui.TEXT, 2, False))
        self.list = ui.ScrollList(lines, ui.TOP + 32, HEIGHT - ui.BUTTON_H - 2 * ui.PAD)
        self.buttons = ui.bottom_row(["Back"], values=["back"], icons=["back"])

    def draw(self, d, image):
        ui.title(d, self.title_text, color=ui.ACCENT)
        self.list.draw(d)

    def on_event(self, event):
        if event.kind == Event.SWIPE_UP:
            self.list.scroll(46)
            return "__redraw__"
        if event.kind == Event.SWIPE_DOWN:
            self.list.scroll(-46)
            return "__redraw__"
        if event.kind == Event.TAP and self.list.top <= event.y < self.list.bottom:
            middle = (self.list.top + self.list.bottom) / 2
            self.list.scroll(-120 if event.y < middle else 120)
            return "__redraw__"
        return super().on_event(event)


def show(hw, topic: str):
    HelpScreen(topic).run(hw)
