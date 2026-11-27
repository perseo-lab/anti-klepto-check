"""
v7.10: what changes with Nunchuk (on the phone) as the host instead of Sparrow.

NUNCHUK: English Sparrow text -> English Nunchuk text, for the texts whose steps differ.
Everywhere else "Sparrow" simply becomes "Nunchuk" (i18n.t). The catalogs translate both.

Nunchuk's own menu names stay in English (Sign, Import signature, Export transaction,
Broadcast transaction), as Sparrow's do (File > Load Transaction > From QR).

Nunchuk can't load a second copy of a transaction as Sparrow does (Load Transaction): it
broadcasts the transaction it holds, the one exported to this verifier. So with Nunchuk
there is no Tx QR: the Broadcast screen shows the whole txid to find in Nunchuk, and the
help page says plainly that the witnesses are as safe as Nunchuk is honest.
"""
NUNCHUK = {
    # v7.16: the power-on state names Sparrow as such, whatever host is chosen now
    "Language and host are chosen here, before START. RAM only: at every power-on the device starts again in "
    "English, with Sparrow.":
        "Language and host are chosen here, before START. RAM only: at every power-on the device starts again in "
        "English, with Sparrow.",
    # title of the broadcast help page: there is no Tx QR to broadcast
    "Broadcast THIS": "Broadcast from Nunchuk",
    # home page of the help
    "1. Load the seed: SeedQR or words, then the passphrase.\n2. Choose the device that signed; scan the signed "
    "PSBT from Sparrow.\n3. Compare the txid, read the result, tap Broadcast and load that QR in Sparrow.":
        "1. Load the seed: SeedQR or words, then the passphrase.\n2. Choose the device that signed; scan the signed "
        "transaction that Nunchuk exports.\n3. Compare the txid, read the result, then broadcast from Nunchuk.",
    # scanning
    "In Sparrow, load what the signer returned, then show the signed PSBT as QR (File > Show PSBT as QR), before "
    "broadcasting anything.":
        "In Nunchuk, import what the signer returned (Sign > Import signature), then show the transaction as QR "
        "(Export transaction: BBQr, or a UR format such as Jade). Don't broadcast yet.",
    "It returns the final transaction (.txn): load it in Sparrow and show it as QR, then scan the UNSIGNED PSBT of "
    "the same transaction too. Any order.":
        "Import the Q's signed QR into Nunchuk (Sign > Import signature), then scan the transaction Nunchuk exports: "
        "usually one QR is enough. If the verifier asks for a second one, it is the UNSIGNED PSBT of the same "
        "transaction.",
    "Coldcard Q: two QR codes": "Coldcard Q with Nunchuk",
    "Both from Sparrow, in any order:\n1. the signed transaction: load the Q's .txn in Sparrow, then show it as QR;\n"
    "2. the UNSIGNED PSBT of the same transaction.\nAt the end, broadcast the Tx QR shown here.":
        "First import the Q's signature into Nunchuk (Sign > Import signature), then scan the transaction Nunchuk "
        "exports.\nIf Nunchuk hands over the final transaction, the UNSIGNED PSBT of the same transaction is asked "
        "too.\nAt the end, broadcast from Nunchuk.",
    "Now the signed transaction, from Sparrow (the Q's .txn loaded there).":
        "Now the signed transaction, from Nunchuk (the Q's signature imported there).",
    "This is the unsigned PSBT. Scan the SIGNED one from Sparrow (after loading what the signer returned).":
        "This is the unsigned PSBT. Scan the SIGNED one from Nunchuk (after Sign > Import signature).",
    # txid
    "Sparrow, transaction tab: is it the same, all of it?":
        "Nunchuk, transaction details: is it the same, all of it?",
    "In Sparrow, the transaction tab shows the Transaction ID. Compare all four rows with this screen. Same: tap "
    "Same txid. Different: tap Different.":
        "In Nunchuk, the transaction details show the transaction ID. Compare all four rows with this screen. Same: "
        "tap Same txid. Different: tap Different.",
    "A segwit txid does not cover the signatures. That is why, at the end, you broadcast the transaction made here "
    "(Broadcast), not Sparrow's own.":
        "A segwit txid does not cover the signatures. Nunchuk broadcasts its own copy, the one it exported here: "
        "look at its txid once more before Broadcast transaction.",
    # result
    "Every signature of this seed uses the nonce it had to use, sighash ALL, low S, and the txid is Sparrow's. Tap "
    "Broadcast.":
        "Every signature of this seed uses the nonce it had to use, sighash ALL, low S, and the txid is Nunchuk's. "
        "Then broadcast from Nunchuk.",
    "The PSBT carries {0} field(s) the check doesn't need: data that could leave with the PSBT file. Broadcast with "
    "the Tx QR, don't pass the PSBT on.":
        "The PSBT carries {0} field(s) the check doesn't need: data that could leave with the PSBT file. Don't pass "
        "the PSBT on.",
    "Not complete: some input is not signed yet. When the transaction is fully signed, scan it again here: only "
    "then broadcast, with the Tx QR.":
        "Not complete: some input is not signed yet. When the transaction is fully signed, scan it again here: only "
        "then broadcast.",
    "{0} extra PSBT field(s): broadcast only with Broadcast": "{0} extra PSBT field(s): don't pass the PSBT on",
    # broadcast (help page)
    "In Sparrow: File > Load Transaction > From QR, and show this animated QR to the webcam. Sparrow opens it in a "
    "NEW tab: check the txid is the same, tap Broadcast in that tab, close the old tab without broadcasting.":
        "In Nunchuk, open the same transaction: check that its transaction ID is the one on this screen, all of it, "
        "then tap Broadcast transaction.",
    "A segwit txid does not cover the signatures: the same transaction can exist with other signatures. A signer "
    "could show clean ones and write leaking ones to its file. This QR is rebuilt here only from the signatures "
    "just checked: the one copy proven clean.":
        "Nunchuk can't load a second copy as Sparrow does: it broadcasts the transaction you exported to this "
        "verifier, with the signatures checked here. A segwit txid does not cover the signatures, so this relies "
        "on Nunchuk sending exactly what it showed you.",
    "Broadcast from Sparrow connected to your own node: a public explorer learns your IP with your transaction.":
        "In Nunchuk's settings, use your own Electrum server (your node): otherwise its server learns your IP with "
        "your transaction.",
    "A compromised Sparrow already holds the PSBT's signatures. This protects from an honest Sparrow broadcasting "
    "other witnesses, not from a compromised computer.":
        "A compromised phone or Nunchuk could broadcast other signatures with the same txid. For the strongest "
        "check, broadcast with Sparrow (Load Transaction), the one copy rebuilt here.",
}

# Texts only the Nunchuk version of the Broadcast screen draws (English; translated in the catalogs)
NUNCHUK_BROADCAST_TITLE = "Broadcast from Nunchuk"
NUNCHUK_BROADCAST_TEXT = ("In Nunchuk: open the same transaction, check that its transaction ID is this one, "
                          "then tap Broadcast transaction.")

TEMPLATE_KEYS = ()
