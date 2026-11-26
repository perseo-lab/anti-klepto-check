"""
Anti-Skippy Check (verifier SD): `src/main.py` starts the nonce verifier, never the
SeedSigner Controller. Replaces upstream's test_main.py, which drove the Controller (on
this image main() starts the verifier, and that test would hang).
"""
import os
import subprocess
import sys
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))


def test_main_starts_the_verifier():
    """ v7.12: the front end of the target this tree builds (target.py): Seed Max or classic """
    import main
    from nonceverify.target import TARGET, TARGET__CLASSIC
    with patch("nonceverify.app.main") as max_main, patch("nonceverify.app_classic.main") as classic_main:
        main.main([])
    started, other = (classic_main, max_main) if TARGET == TARGET__CLASSIC else (max_main, classic_main)
    started.assert_called_once_with()
    other.assert_not_called()


def test_main_does_not_load_the_signer():
    """
    The verifier's modules, as main() loads them at boot, pull in no SeedSigner
    controller, view or seed code, no embit and no urtypes
    """
    code = (
        "import sys; sys.path.insert(0, 'src'); import main, nonceverify.app, nonceverify.hw; "
        "bad = [m for m in sys.modules if m.startswith(('seedsigner.controller', 'seedsigner.views', "
        "'seedsigner.models.seed', 'embit', 'urtypes'))]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True,
                            timeout=60, cwd=REPO)
    assert result.returncode == 0, result.stdout + result.stderr
