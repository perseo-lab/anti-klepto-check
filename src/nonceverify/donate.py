"""
v7.14: the invitation to donate at the end of a session, as on the Seed Max (Donate).

The payment details are those of docs/DONATE.txt.asc, signed with the author's key
(PGP 513B 3583 0E4F 869E FC6D 9534 F1A0 5CB1 6C89 8D92); a test checks that this file and
the signed one say the same. A fork can change both, but not the signature: the page
says where to verify it. Nothing here is sent anywhere: the device only shows QR codes.
"""
AUTHOR_KEY = "513B 3583 0E4F 869E FC6D 9534 F1A0 5CB1 6C89 8D92"

# The page with the signed details and how to verify them
PAGE_URL = "https://github.com/perseo-lab/anti-skippy-check#support-the-project"

# Lightning, BOLT12 offer (no checksum: never typed by hand, always from here or the signed file)
BOLT12_OFFER = ("lno1zrxq8pjw7qjlm68mtp7e3yvxee4y5xrgjhhyf2fxhlphpckrvevh50u0qfxc0n6m228mgt5rlpmq"
                "p63upgwf7zysppmpear64gjp6taxvp6e2qsr026hacegmnfhu9zd40k9qkplmy3kqee6vfu99esl7nvj"
                "35l86wqqqve5llhdydajwyz64hmauj7qk93xjkaca4pa96tttzr9tfts2tmpu9mlwv39m494t6j9qht5"
                "dpqggel0rxvgqfguxstts7ff65m9xhm60x3ea2kae8xjqy84qzes7tum7w780vh36qqsnus40074hc0y"
                "64ksea2xvfwsgq")

# On-chain, Silent Payments address (BIP 352): every payment lands on a fresh Taproot output
SILENT_PAYMENT = "sp1qqt75n5wr03rpt33xutl40cnf8z9ahg2gmcl3nn5trxq5ff5jjcvf7qlg94hvwzx527zy5tl654vsv5k3dxa7rz97me3ku9w249zsev5ujycl3kaf"


def pages():
    """ [(title, what the QR holds, QR payload, the text under it)], in the order shown """
    return [
        ("Support the project", "page", PAGE_URL, "github.com/perseo-lab/anti-skippy-check"),
        ("Lightning (BOLT12)", "bolt12", BOLT12_OFFER.upper(), "Phoenix, Zeus or another BOLT12 wallet"),
        ("On-chain, Silent Payments", "sp", SILENT_PAYMENT.upper(), "a wallet with Silent Payments (BIP 352)"),
    ]
