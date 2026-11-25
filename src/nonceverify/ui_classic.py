"""
v7.12: the Anti-Klepto Check look on the classic SeedSigner: 240x240, joystick and three
keys. The same identity as on the Seed Max hardware (dark slate, teal accent, the shield
and k emblem, monospace labels, the Tron splash), never SeedSigner's: palette, fonts,
icons and the translated drawing come from ui.py; sizes and input are this screen's.

Input. The joystick moves the selection, pushing it in chooses. The three keys beside the
screen, top to bottom: KEY1 the "?" page of the screen, KEY2 a second action where a
screen has one (Delete, Zoom), KEY3 Back. A small tab on the right edge, next to each key,
says what it does on that screen; no tab, no action.

Every screen is a loop: render -> wait for a key -> return what was chosen.
"""
import time

from PIL import Image

from nonceverify import ui
from nonceverify.hw import Event
from nonceverify.hw_classic import HEIGHT, WIDTH
from nonceverify.i18n import Translated, t

# The palette and the drawing helpers are the Seed Max ones
BACKGROUND, PANEL, PANEL_HI, LINE = ui.BACKGROUND, ui.PANEL, ui.PANEL_HI, ui.LINE
TEXT, DIM, ACCENT, ACCENT_DARK = ui.TEXT, ui.DIM, ui.ACCENT, ui.ACCENT_DARK
GREEN, RED, YELLOW = ui.GREEN, ui.RED, ui.YELLOW
font, fit_font, wrap, text_width, icon, emblem, spaced = (ui.font, ui.fit_font, ui.wrap, ui.text_width, ui.icon,
                                                          ui.emblem, ui.spaced)
draw_on = ui.draw_on

PAD = 6
HEADER_H = 22
TOP = HEADER_H + 4
TAB_W = 14                            # the key tabs on the right edge
RIGHT = WIDTH - TAB_W - 2             # content stops here, the tabs live beyond
ITEM_H = 30

# Where the three keys sit beside the panel (y of their centers), as on the HAT
KEY_Y = {Event.KEY1: 52, Event.KEY2: 120, Event.KEY3: 188}
STEPS = ui.STEPS


def new_canvas():
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    return image, ui.Draw(image)


def header(d, step: int = None, label: str = None):
    """ Top bar: the emblem, then the steps (SEED PSBT RESULT) or a label """
    d.rectangle((0, 0, WIDTH, HEADER_H), fill=PANEL)
    d.line((0, HEADER_H, WIDTH, HEADER_H), fill=LINE, width=1)
    icon(d, "shield", (12, HEADER_H / 2), 14, ACCENT)
    d.text((12, HEADER_H / 2 + 1), "k", fill=PANEL, font=font(10, bold=True, mono=True), anchor="mm")
    left, right = 26, WIDTH - PAD
    if step is not None:
        size = 11
        while size > 8 and sum(text_width(n, font(size, bold=True, mono=True)) + 10 for n in STEPS) - 3 > right - left:
            size -= 1
        f = font(size, bold=True, mono=True)
        x = right
        for i in range(len(STEPS) - 1, -1, -1):
            name = STEPS[i]
            w = text_width(name, f) + 8
            if i == step:
                d.rounded_rectangle((x - w, 4, x, HEADER_H - 4), radius=3, fill=ACCENT)
            d.text((x - w / 2, HEADER_H / 2), name, fill=BACKGROUND if i == step else (ACCENT if i < step else DIM),
                   font=f, anchor="mm")
            x -= w + 3
    elif label:
        d.text((right, HEADER_H / 2), label, fill=DIM, font=fit_font(label, 11, right - left, bold=True, mono=True,
                                                                       smallest=8), anchor="rm")
    else:
        spaced(d, (left, HEADER_H / 2), ui.APP_NAME, font(10, bold=True, mono=True), ACCENT, 1, anchor="lm")


def key_tab(d, key: str, glyph: str, color=ACCENT, is_icon: bool = True):
    """ A tab on the right edge, next to the physical key, with what the key does here """
    cy = KEY_Y[key]
    d.rounded_rectangle((WIDTH - TAB_W, cy - 15, WIDTH + 6, cy + 15), radius=5, fill=PANEL, outline=LINE)
    if is_icon:
        icon(d, glyph, (WIDTH - TAB_W / 2 + 1, cy), 10, color)
    else:
        d.text((WIDTH - TAB_W / 2 + 1, cy), glyph, fill=color, font=font(13, bold=True), anchor="mm")


def paragraph(d, text: str, y: int, size: int = 14, color=TEXT, x: int = PAD, width: int = None,
              max_lines: int = 12, line_gap: int = 3, bold: bool = False) -> int:
    width = width or (RIGHT - x)
    f = font(size, bold=bold)
    lines = wrap(text, f, width)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [Translated(lines[max_lines - 1][:-1] + "…")]
    for line in lines:
        d.text((x, y), line, fill=color, font=f)
        y += size + line_gap
    return y


def title(d, text: str, y: int = TOP + 9, color=TEXT, size: int = 17):
    d.text((PAD, y), text, fill=color, font=fit_font(text, size, RIGHT - PAD, bold=True, smallest=11), anchor="lm")


def panel(d, rect, color=PANEL, outline=LINE, width: int = 1):
    d.rounded_rectangle(rect, radius=5, fill=color, outline=outline, width=width)


def check_mark(d, x: float, y: float, r: float, color=ACCENT):
    d.ellipse((x - r, y - r, x + r, y + r), outline=color, width=2)
    d.line(((x - r * .45, y), (x - r * .1, y + r * .4), (x + r * .5, y - r * .4)), fill=color, width=2)


class Item:
    """
    A choice on the screen. Selected: filled teal. Otherwise outlined; `primary` (what
    the screen expects) has a teal outline, `color` fills it (red: a destructive choice).
    Disabled: drawn dim, never chosen.
    """
    def __init__(self, rect, label: str, value=None, primary: bool = False, color=None, size: int = 15,
                 icon_name: str = None, enabled: bool = True, align: str = "center"):
        self.rect = tuple(int(v) for v in rect)
        self.label = label
        self.value = label if value is None else value
        self.primary, self.color, self.size, self.icon_name = primary, color, size, icon_name
        self.enabled, self.align = enabled, align

    def draw(self, d, selected: bool = False):
        x1, y1, x2, y2 = self.rect
        if selected and self.enabled:
            fill, fg, outline = (self.color or ACCENT), BACKGROUND, None
        elif not self.enabled:
            fill, fg, outline = BACKGROUND, (60, 70, 84), (28, 36, 46)
        else:
            fill, fg = PANEL, TEXT
            outline = self.color or (ACCENT if self.primary else LINE)
        d.rounded_rectangle(self.rect, radius=5, fill=fill, outline=outline, width=2 if outline in (ACCENT, self.color)
                            and outline is not None and not selected else 1)
        label = Translated(t(self.label))         # translated once, measured and drawn as it is
        room = x2 - x1 - 10 - ((self.size + 6) if self.icon_name else 0)
        f = fit_font(label, self.size, room, bold=True, smallest=9)
        cy = (y1 + y2) / 2
        w = (self.size + 6 if self.icon_name else 0) + ui._raw_width(label, f)
        x = x1 + 8 if self.align == "left" else (x1 + x2) / 2 - w / 2
        if self.icon_name:
            icon(d, self.icon_name, (x + self.size / 2, cy), self.size - 2, fg)
            x += self.size + 6
        d.text((x, cy), Translated(label), fill=fg, font=f, anchor="lm")


def column(labels, top: int, values=None, icons=None, height: int = ITEM_H, gap: int = 5, primary_index=None,
           x1: int = PAD, x2: int = RIGHT, size: int = 15, align: str = "center"):
    """ Choices one under the other """
    out = []
    for i, label in enumerate(labels):
        y = top + i * (height + gap)
        out.append(Item((x1, y, x2, y + height), label, value=None if values is None else values[i],
                        primary=(i == primary_index), icon_name=None if icons is None else icons[i], size=size,
                        align=align))
    return out


def row(labels, y: int, values=None, icons=None, height: int = ITEM_H, gap: int = 5, primary_index=None,
        x1: int = PAD, x2: int = RIGHT, size: int = 14):
    """ Choices side by side, equal widths """
    n = len(labels)
    width = (x2 - x1 - gap * (n - 1)) / n
    out = []
    for i, label in enumerate(labels):
        x = x1 + i * (width + gap)
        out.append(Item((x, y, x + width, y + height), label, value=None if values is None else values[i],
                        primary=(i == primary_index), icon_name=None if icons is None else icons[i], size=size))
    return out


def bottom_row(labels, **kw):
    return row(labels, HEIGHT - ITEM_H - 4, **kw)


# v7.5: periodic checks every screen loop runs (the microSD guard): the Seed Max list
housekeeping = ui.housekeeping


def open_help(hw, topic: str):
    from nonceverify import guide_classic
    guide_classic.show(hw, topic)


class Screen:
    """
    Draw, then wait for a key. The joystick moves the selection through `self.items`
    (UP/LEFT back, DOWN/RIGHT forward, disabled items skipped); PRESS returns the
    selected item's value. KEY1 opens the help page (`help_topic`), KEY3 returns
    `back_value` when the screen has one. `selected` None: nothing chosen until the
    joystick moves (where a careless push must not answer for the user).
    """
    step = None
    header_label = None
    help_topic = None
    back_value = None
    key2_glyph = None                 # (glyph, is_icon) of KEY2's tab, when the screen uses it

    def __init__(self):
        self.items = []
        self.selected = 0

    def draw(self, d, image):
        raise NotImplementedError

    def render(self):
        image, d = new_canvas()
        header(d, self.step, self.header_label)
        self.draw(d, image)
        for i, item in enumerate(self.items):
            item.draw(d, selected=(i == self.selected))
        self.draw_tabs(d)
        return image

    def draw_tabs(self, d):
        if self.help_topic:
            key_tab(d, Event.KEY1, "?", is_icon=False)
        if self.key2_glyph:
            key_tab(d, Event.KEY2, *self.key2_glyph)
        if self.back_value is not None:
            key_tab(d, Event.KEY3, "back", TEXT)

    def move(self, step: int):
        enabled = [i for i, item in enumerate(self.items) if item.enabled]
        if not enabled:
            return
        if self.selected is None or self.selected not in enabled:
            self.selected = enabled[0] if step > 0 else enabled[-1]
            return
        pos = enabled.index(self.selected)
        self.selected = enabled[max(0, min(len(enabled) - 1, pos + step))]

    def on_key2(self):
        return None

    def on_event(self, event):
        """ A value to leave the screen, "__redraw__", or None """
        if event.kind in (Event.UP, Event.LEFT):
            self.move(-1)
            return "__redraw__"
        if event.kind in (Event.DOWN, Event.RIGHT):
            self.move(1)
            return "__redraw__"
        if event.kind == Event.PRESS and self.selected is not None and self.items:
            item = self.items[self.selected]
            return item.value if item.enabled else None
        if event.kind == Event.KEY2:
            return self.on_key2()
        if event.kind == Event.KEY3 and self.back_value is not None:
            return self.back_value
        return None

    def run(self, hw, timeout: float = None):
        hw.show(self.render())
        started = time.monotonic()
        while True:
            housekeeping(hw)
            for event in hw.poll():
                if event.kind == Event.KEY1 and self.help_topic:
                    open_help(hw, self.help_topic)          # then the same screen again
                    hw.show(self.render())
                    continue
                result = self.on_event(event)
                if result == "__redraw__":
                    hw.show(self.render())
                elif result is not None:
                    return result
            if timeout is not None and time.monotonic() - started > timeout:
                return None
            hw.wait()


class MessageScreen(Screen):
    def __init__(self, heading: str, body: str, buttons=("OK",), heading_color=TEXT, primary_index=0, values=None,
                 icon_name: str = None, step=None):
        super().__init__()
        self.heading, self.body, self.heading_color, self.icon_name = heading, body, heading_color, icon_name
        self.step = step
        self.list = None
        labels = list(buttons)
        if len(labels) > 2 or any(text_width(b, font(14, bold=True)) > 100 for b in labels):
            self.items = column(labels, HEIGHT - len(labels) * (ITEM_H + 4) - 2, values=values,
                                primary_index=primary_index)
        else:
            self.items = bottom_row(labels, values=values, primary_index=primary_index)
        self.selected = primary_index if primary_index is not None else 0
        top = TOP + 24
        bottom = self.items[0].rect[1] - 4
        lines = []
        f = font(13)
        for line in wrap(body, f, RIGHT - PAD - 4):
            lines.append((line, TEXT, 13, False))
        self.list = ScrollList(lines, top, bottom)

    def draw(self, d, image):
        x = PAD
        if self.icon_name:
            icon(d, self.icon_name, (PAD + 9, TOP + 9), 16, self.heading_color)
            x = PAD + 22
        d.text((x, TOP + 9), self.heading, fill=self.heading_color,
               font=fit_font(self.heading, 16, RIGHT - x, bold=True, smallest=10), anchor="lm")
        self.list.draw(d)

    def on_event(self, event):
        # a long text scrolls with UP/DOWN; LEFT/RIGHT choose
        if event.kind in (Event.UP, Event.DOWN) and self.list.max_offset() > 0 and len(self.items) <= 2 \
                and self.items[0].rect[1] == self.items[-1].rect[1]:
            self.list.scroll(-40 if event.kind == Event.UP else 40)
            return "__redraw__"
        return super().on_event(event)


class ScrollList:
    """ Lines of (text, color, size, mono), scrolled with the joystick """
    def __init__(self, lines, top: int, bottom: int, x: int = PAD, right: int = RIGHT):
        self.lines = lines
        self.top, self.bottom = top, bottom
        self.x, self.right = x, right
        self.offset = 0

    def total_height(self):
        return sum(line[2] + 4 for line in self.lines)

    def max_offset(self):
        return max(0, self.total_height() - (self.bottom - self.top))

    def scroll(self, pixels: int):
        self.offset = min(self.max_offset(), max(0, self.offset + pixels))

    def draw(self, d):
        y = self.top - self.offset
        for text, color, size, mono in self.lines:
            if y >= self.top and y + size + 1 <= self.bottom:
                d.text((self.x, y), text, fill=color, font=font(size, mono=mono))
            y += size + 4
        total, view = self.total_height(), self.bottom - self.top
        if total > view:
            bar_h = max(14, int(view * view / total))
            bar_y = self.top + int((view - bar_h) * self.offset / max(1, self.max_offset()))
            d.rounded_rectangle((self.right - 3, self.top, self.right, self.bottom), radius=1, fill=PANEL)
            d.rounded_rectangle((self.right - 3, bar_y, self.right, bar_y + bar_h), radius=1, fill=ACCENT)


class Grid:
    """
    Joystick navigation over rows of cells (keyboards): LEFT/RIGHT along a row, UP/DOWN to
    the cell of the next row nearest in x. Each row is a list of rects; `cursor` = (row, col).
    """
    def __init__(self, rows):
        self.rows = [r for r in rows if r]
        self.cursor = (0, 0)

    def rect(self):
        r, c = self.cursor
        return self.rows[r][c]

    def move(self, kind) -> bool:
        """ True if the cursor moved """
        r, c = self.cursor
        if kind in (Event.LEFT, Event.RIGHT):
            c2 = max(0, min(len(self.rows[r]) - 1, c + (1 if kind == Event.RIGHT else -1)))
            moved = c2 != c
            self.cursor = (r, c2)
            return moved
        r2 = r + (1 if kind == Event.DOWN else -1)
        if not 0 <= r2 < len(self.rows):
            return False
        x1, _y1, x2, _y2 = self.rows[r][c]
        cx = (x1 + x2) / 2
        c2 = min(range(len(self.rows[r2])), key=lambda i: abs((self.rows[r2][i][0] + self.rows[r2][i][2]) / 2 - cx))
        self.cursor = (r2, c2)
        return True


def key_cell(d, rect, label: str, selected: bool, enabled: bool = True, size: int = 14, mono: bool = False):
    """ One key of a keyboard """
    if selected:
        d.rounded_rectangle(rect, radius=3, fill=ACCENT if enabled else LINE)
        fg = BACKGROUND
    elif enabled:
        d.rounded_rectangle(rect, radius=3, fill=PANEL, outline=LINE)
        fg = TEXT
    else:
        d.rounded_rectangle(rect, radius=3, fill=BACKGROUND, outline=(24, 32, 42))
        fg = (52, 62, 74)
    room = rect[2] - rect[0] - 4
    f = fit_font(label, size, room, bold=True, mono=mono, smallest=8)
    d.text(((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2), label, fill=fg, font=f, anchor="mm")
