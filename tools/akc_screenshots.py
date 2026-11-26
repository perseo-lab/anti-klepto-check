#!/usr/bin/env python3
"""
Anti-Klepto Check: render the README screenshots straight from the device code.

The screens are drawn by the same code and on the same PIL canvas as on the device
(480x320 for the Raspy Max, 240x240 for the classic SeedSigner), with the test data of
tests/ (the public "abandon ... about" test seed).
Usage, from the repository root, with the test dependencies installed (see README):
    python3 tools/akc_screenshots.py docs/screenshots
"""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(root, "src"), os.path.join(root, "tests")]

from nonceverify import i18n                    # noqa: E402
import test_nonceverify_v710 as T               # noqa: E402  (its screens() is the list of screens)

SHOTS = [   # (file name, screen name in screens(), language)
    ("01-splash", "splash", "en"),
    ("02-home", "home", "en"),
    ("03-seed-words", "words", "en"),
    ("04-txid", "txid", "en"),
    ("05-result", "result", "en"),
    ("06-details", "details", "en"),
    ("07-broadcast", "broadcast", "en"),
    ("08-help", "help result", "en"),
    ("09-result-italian", "result", "it"),
]

# v7.14: the classic SeedSigner (240x240), saved at twice the size (each pixel a 2x2 block)
CLASSIC_SHOTS = [
    ("classic-01-splash", "splash", "en"),
    ("classic-02-seed-words", "entry", "en"),
    ("classic-03-txid", "txid", "en"),
    ("classic-04-result-checks", "result green top", "en"),
    ("classic-05-result-address", "result green address", "en"),
    ("classic-06-broadcast", "broadcast", "en"),
    ("classic-07-donate", "donate 0", "en"),
    ("classic-08-result-italian", "result green top", "it"),
]


def main(out):
    os.makedirs(out, exist_ok=True)
    for fname, screen, lang in SHOTS:
        i18n.reset()
        i18n.set_language(lang)
        render = dict(T.screens())[screen]
        path = os.path.join(out, fname + ".png")
        render().save(path)
        print(path)
    import test_nonceverify_classic as C
    from PIL import Image
    for fname, screen, lang in CLASSIC_SHOTS:
        i18n.reset()
        i18n.set_language(lang)
        image = dict(C.screens())[screen]()
        path = os.path.join(out, fname + ".png")
        image.resize((image.width * 2, image.height * 2), Image.NEAREST).save(path)
        print(path)
    i18n.reset()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
