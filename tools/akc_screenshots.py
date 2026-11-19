#!/usr/bin/env python3
"""
Anti-Klepto Check: render the README screenshots straight from the device code.

The screens are drawn by the same code and on the same 480x320 PIL canvas as on the
device, with the test data of tests/ (the public "abandon ... about" test seed).
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

def main(out):
    os.makedirs(out, exist_ok=True)
    for fname, screen, lang in SHOTS:
        i18n.reset()
        i18n.set_language(lang)
        render = dict(T.screens())[screen]
        path = os.path.join(out, fname + ".png")
        render().save(path)
        print(path)
    i18n.reset()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
