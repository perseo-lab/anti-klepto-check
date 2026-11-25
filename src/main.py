#!/usr/bin/env python
"""
Anti-Klepto Check: the verifier SD.

This image does not run SeedSigner: it starts the nonce verifier (src/nonceverify),
which checks the signatures made by another signer (or by the signing SD) and never
signs anything itself.
"""
import sys


def main(sys_argv=None):
    # v7.12: the front end of the hardware this image is built for (nonceverify/target.py)
    from nonceverify.target import TARGET, TARGET__CLASSIC
    if TARGET == TARGET__CLASSIC:
        from nonceverify.app_classic import main as verifier_main
    else:
        from nonceverify.app import main as verifier_main
    verifier_main()


if __name__ == "__main__":
    main(sys.argv[1:])
