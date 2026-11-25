"""
v7.12: the hardware this image is built for. One image per target, no detection at boot:
a display can't be detected reliably, and a verifier runs less code when it doesn't try.

    TARGET__MAX      Seed Max hardware: Pi Zero, Waveshare 3.5" (A) 480x320 touch, UPS HAT (C)
    TARGET__CLASSIC  classic SeedSigner: Pi Zero, Waveshare 1.3" 240x240, joystick and three keys

The release tags differ by this one line: vX.Y builds the Seed Max image, vX.Y-classic
the classic one (git diff vX.Y vX.Y-classic shows only TARGET).
"""
TARGET__MAX = "max"
TARGET__CLASSIC = "classic"

TARGET = TARGET__CLASSIC
