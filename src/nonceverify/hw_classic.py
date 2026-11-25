"""
v7.12: hardware of the classic SeedSigner: Raspberry Pi Zero, Waveshare 1.3" LCD HAT
(ST7789, 240x240, joystick and three keys), Pi camera. No touch, no battery gauge.

Drivers of the SeedSigner OS image, used as plain hardware code: the original ST7789
driver that SeedSigner itself uses for 240x240 (the "mpy" one draws that panel skewed),
RPi.GPIO for the keys, the camera stream shared with the Seed Max target (hw.Camera).
Nothing here touches a key or the microSD.

Pins in physical header numbering (GPIO.BOARD), as SeedSigner's hardware/buttons.py on a
40-pin Pi: the keys pull the pin to ground when pressed.
"""
import time

from nonceverify.hw import Camera, Event

WIDTH = 240
HEIGHT = 240

PINS = {
    Event.UP: 31, Event.DOWN: 35, Event.LEFT: 29, Event.RIGHT: 37, Event.PRESS: 33,
    Event.KEY1: 40, Event.KEY2: 38, Event.KEY3: 36,
}


class Profile:
    """ The camera as SeedSigner mounts it on the classic hardware """
    CAMERA_RESOLUTION = 320           # square frames for the decoder; the preview is scaled to 240
    CAMERA_ROTATION = 180             # stock SeedSigner default for this hardware


class NoBattery:
    """ The classic hardware has no gauge: no icon, nothing to read """
    def start(self) -> bool:
        return False

    def tick(self) -> bool:
        return False

    def display(self):
        return None


class Keys:
    """
    Key presses from the pin levels, read at every poll. A press is reported once when the
    key goes down (after DEBOUNCE_MS steady); the joystick directions repeat while held
    (after REPEAT_AFTER_MS, every REPEAT_EVERY_MS), the center and the three keys never do.
    """
    DEBOUNCE_MS = 25
    REPEAT_AFTER_MS = 450
    REPEAT_EVERY_MS = 140
    REPEATING = (Event.UP, Event.DOWN, Event.LEFT, Event.RIGHT)

    def __init__(self, read, clock=time.monotonic):
        self.read = read                          # kind -> True while pressed
        self.clock = clock
        self.state = {k: (False, 0.0) for k in PINS}  # kind -> (down, since ms)
        self.reported = {k: False for k in PINS}
        self.next_repeat = {k: 0.0 for k in PINS}

    def poll(self) -> list:
        now = self.clock() * 1000
        events = []
        for kind in PINS:
            down = bool(self.read(kind))
            was, since = self.state[kind]
            if down != was:
                self.state[kind] = (down, now)
                if not down:
                    self.reported[kind] = False
                continue
            if not down or now - since < self.DEBOUNCE_MS:
                continue
            if not self.reported[kind]:
                self.reported[kind] = True
                self.next_repeat[kind] = now + self.REPEAT_AFTER_MS
                events.append(Event(kind))
            elif kind in self.REPEATING and now >= self.next_repeat[kind]:
                self.next_repeat[kind] = now + self.REPEAT_EVERY_MS
                events.append(Event(kind))
        return events


class Hardware(Camera):
    """ The real classic SeedSigner """
    def __init__(self):
        import RPi.GPIO as GPIO
        from seedsigner.hardware.displays.ST7789 import ST7789

        self.hw_profile = Profile
        self.stream = None
        self.zoom = 1
        self.battery = NoBattery()
        self.display = ST7789(_width=WIDTH, _height=HEIGHT)      # sets GPIO.BOARD itself
        GPIO.setmode(GPIO.BOARD)
        for pin in PINS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.keys = Keys(lambda kind: GPIO.input(PINS[kind]) == GPIO.LOW)

    def show(self, image):
        self.display.show_image(image.convert("RGB"), 0, 0)

    def poll(self) -> list:
        return self.keys.poll()

    def wait(self, seconds: float = 0.005):
        time.sleep(seconds)

    def battery_tick(self) -> bool:
        return False
