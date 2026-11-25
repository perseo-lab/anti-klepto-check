"""
v7.12: the seed typed word by word, and the passphrase, on the classic SeedSigner
(240x240, joystick). Same rules as wordentry.py on the Seed Max hardware, the same flow
(wordentry.enter_mnemonic with these screens): only the BIP39 letters that can still lead
to a word are active, the matching words are offered once four or fewer remain, all the
words are reviewed at the end with the checksum, hidden until Show.

The letters are in alphabetical order: with a joystick, a known order is faster to reach
than QWERTY. KEY2 deletes a letter, KEY3 goes back (to the previous word, or the review).
"""
from nonceverify import seedqr, ui_classic as u
from nonceverify.hw import Event
from nonceverify.i18n import Translated
from nonceverify.wordentry import matches, next_letters


class WordCountScreen(u.Screen):
    step = 0
    help_topic = "seed"
    back_value = "back"

    def __init__(self):
        super().__init__()
        self.items = u.column(["12 words", "24 words"], 112, values=[12, 24], height=34)

    def draw(self, d, image):
        u.title(d, "Type the seed word by word")
        u.paragraph(d, "How many words does your seed have?", u.TOP + 24, size=14, color=u.DIM)
        u.paragraph(d, "They stay in RAM only; at the end you review them all, with the checksum.", 192,
                    size=12, color=u.DIM, max_lines=3)


class WordEntryScreen(u.Screen):
    """ Typing word `index` (0-based) of `count`. Returns ("word", w) or ("prev",) """
    step = 0
    help_topic = "seed"
    ROWS = ("abcdefg", "hijklmn", "opqrstu", "vwxyz")
    COLS = 7
    KEYS_TOP = 76
    KEY_H = 25
    KEY_GAP = 3
    CAND_TOP = 190
    CAND_SLOTS = 4
    LABEL_CY = u.TOP + 9
    FIELD = (u.PAD, u.TOP + 22, u.RIGHT, u.TOP + 44)
    key2_glyph = ("erase", True)

    def __init__(self, index: int, count: int, text: str = "", back_label: str = "Back"):
        super().__init__()
        self.index, self.count = index, count
        self.text = text
        self.back_label = back_label
        self.back_value = ("prev",)
        self.cursor = None
        self.layout()

    @classmethod
    def key_rect(cls, letter: str):
        width = (u.RIGHT - u.PAD - (cls.COLS - 1) * cls.KEY_GAP) / cls.COLS
        for row, chars in enumerate(cls.ROWS):
            if letter in chars:
                col = chars.index(letter)
                x = u.PAD + col * (width + cls.KEY_GAP)
                y = cls.KEYS_TOP + row * (cls.KEY_H + cls.KEY_GAP)
                return (int(x), int(y), int(x + width), int(y + cls.KEY_H))
        raise KeyError(letter)

    @classmethod
    def candidate_rect(cls, slot: int):
        width = (u.RIGHT - u.PAD - 4) / 2
        col, row = slot % 2, slot // 2
        x = u.PAD + col * (width + 4)
        y = cls.CAND_TOP + row * 24
        return (int(x), y, int(x + width), y + 21)

    def candidates(self) -> list:
        found = matches(self.text)
        return found if self.text and len(found) <= self.CAND_SLOTS else []

    def layout(self):
        """ The grid: the letter rows, then the candidate words (two per row) """
        rows = [[self.key_rect(c) for c in chars] for chars in self.ROWS]
        cands = self.candidates()
        rows.append([self.candidate_rect(i) for i in range(min(2, len(cands)))])
        rows.append([self.candidate_rect(i) for i in range(2, len(cands))])
        old = self.cursor
        self.grid = u.Grid(rows)
        self.cells = {}
        for r, chars in enumerate(self.ROWS):
            for c, letter in enumerate(chars):
                self.cells[(r, c)] = ("letter", letter)
        for slot, word in enumerate(cands):
            r = len(self.ROWS) + slot // 2
            self.cells[(r, slot % 2)] = ("word", word)
        if len(cands) == 1:
            self.grid.cursor = (len(self.ROWS), 0)          # one word left: it is selected
        elif old is not None and old in self.cells and old[0] < len(self.ROWS):
            self.grid.cursor = old
        else:
            allowed = next_letters(self.text)
            first = next((rc for rc, (kind, v) in self.cells.items() if kind == "letter" and v in allowed), (0, 0))
            self.grid.cursor = first if old is None or old not in self.cells else old
        self.cursor = self.grid.cursor

    def draw(self, d, image):
        self.draw_position(d)
        found = matches(self.text)
        d.rounded_rectangle(self.FIELD, radius=4, fill=u.PANEL, outline=u.ACCENT, width=1)
        cy = (self.FIELD[1] + self.FIELD[3]) / 2
        d.text((u.PAD + 6, cy), Translated(self.text + "_"), fill=u.TEXT, font=u.font(16, bold=True, mono=True),
               anchor="lm")
        if self.text and len(found) > self.CAND_SLOTS:
            d.text((self.FIELD[2] - 5, cy), f"{len(found)} words", fill=u.DIM, font=u.font(11, mono=True),
                   anchor="rm")
        allowed = next_letters(self.text)
        for (r, c), (kind, value) in self.cells.items():
            if kind != "letter":
                continue
            u.key_cell(d, self.key_rect(value), value, (r, c) == self.cursor, value in allowed, size=15)
        cands = self.candidates()
        for slot, word in enumerate(cands):
            r = len(self.ROWS) + slot // 2
            u.Item(self.candidate_rect(slot), Translated(word), primary=len(cands) == 1, size=13).draw(
                d, selected=(r, slot % 2) == self.cursor)
        if not self.text:
            d.text(((u.PAD + u.RIGHT) / 2, self.CAND_TOP + 20), "type the first letters", fill=u.DIM,
                   font=u.font(12), anchor="mm")
        elif not cands:
            d.text(((u.PAD + u.RIGHT) / 2, self.CAND_TOP + 20), "the words appear at four or fewer", fill=u.DIM,
                   font=u.fit_font("the words appear at four or fewer", 12, u.RIGHT - u.PAD, smallest=9), anchor="mm")

    def bar_segments(self):
        x1, x2 = 132, u.RIGHT
        gap = 2 if self.count <= 12 else 1
        width = (x2 - x1 - gap * (self.count - 1)) / self.count
        y = self.LABEL_CY - 3
        return [(int(round(x1 + i * (width + gap))), y, max(int(round(x1 + i * (width + gap))),
                 int(round(x1 + i * (width + gap) + width)) - 1), y + 6) for i in range(self.count)]

    def draw_position(self, d):
        """ "WORD 5 of 12", the number large, and one bar segment per word """
        x, cy = u.PAD, self.LABEL_CY
        f_label, f_num, f_of = u.font(10, bold=True, mono=True), u.font(17, bold=True), u.font(12, bold=True)
        u.spaced(d, (x, cy + 1), "WORD", f_label, u.DIM, 1, anchor="lm")
        x += sum(u.text_width(Translated(c), f_label) for c in u.t("WORD")) + 3 + 5
        number = str(self.index + 1)
        d.text((x, cy), number, fill=u.ACCENT, font=f_num, anchor="lm")
        x += u.text_width(number, f_num) + 4
        d.text((x, cy + 1), f"of {self.count}", fill=u.TEXT, font=f_of, anchor="lm")
        for i, rect in enumerate(self.bar_segments()):
            color = u.ACCENT if i < self.index else (u.TEXT if i == self.index else u.LINE)
            d.rectangle(rect, fill=color)

    def on_key2(self):
        if self.text:
            self.text = self.text[:-1]
            self.layout()
            return "__redraw__"
        return None

    def on_event(self, event):
        if event.kind in (Event.UP, Event.DOWN, Event.LEFT, Event.RIGHT):
            self.grid.move(event.kind)
            self.cursor = self.grid.cursor
            return "__redraw__"
        if event.kind == Event.PRESS:
            kind, value = self.cells.get(self.cursor, (None, None))
            if kind == "word":
                return ("word", value)
            if kind == "letter" and value in next_letters(self.text):
                self.text += value
                self.layout()
                return "__redraw__"
            return None                          # a dimmed letter: no BIP39 word goes that way
        return super().on_event(event)


class SeedReviewScreen(u.Screen):
    """
    All the words, numbered, with the checksum. Returns "ok" (valid checksum only),
    ("edit", index) or "cancel". Twelve words per page; 24 words: the page follows the
    selected word.
    """
    step = 0
    help_topic = "seed"
    back_value = "cancel"
    GRID_TOP = u.TOP + 32
    ROW_H = 22
    PER_PAGE = 12

    def __init__(self, words: list):
        super().__init__()
        self.words = words
        self.valid = seedqr.mnemonic_is_valid(" ".join(words))
        self.revealed = not self.valid            # wrong checksum: shown, the wrong word must be found
        self.page = 0
        self.make_items()

    def make_items(self):
        labels = ["Cancel", "Hide" if self.revealed else "Show", "Confirm" if self.valid else "Wrong"]
        self.buttons = u.bottom_row(labels, values=["cancel", "reveal", "ok"], primary_index=2 if self.valid else None,
                                    size=13)
        self.buttons[2].enabled = self.valid
        if not self.valid:
            self.buttons[2].color = u.RED
        # the words are choices only when shown (to re-type the wrong one)
        self.word_items = [u.Item(self.cell(i), "", value=("edit", i)) for i in range(len(self.words))] \
            if self.revealed else []
        self.items = self.word_items + self.buttons
        self.selected = len(self.word_items) + (2 if self.valid else 0)

    def cell(self, i: int):
        j = i % self.PER_PAGE
        col, row = j // 6, j % 6                  # numbered down each column, as on paper
        width = (u.RIGHT - u.PAD - 4) / 2
        x = u.PAD + col * (width + 4)
        y = self.GRID_TOP + row * self.ROW_H
        return (int(x), y, int(x + width), y + self.ROW_H - 3)

    def render(self):
        if self.selected is not None and self.selected < len(self.word_items):
            self.page = self.selected // self.PER_PAGE
        image, d = u.new_canvas()
        u.header(d, self.step, self.header_label)
        self.draw(d, image)
        for i, item in enumerate(self.buttons):
            item.draw(d, selected=(len(self.word_items) + i == self.selected))
        self.draw_tabs(d)
        return image

    def draw(self, d, image):
        if self.valid:
            u.icon(d, "ok_circle", (u.PAD + 7, u.TOP + 7), 13, u.GREEN)
            text, color = ("Checksum OK: compare the words with your backup" if self.revealed else
                           "Checksum OK · words hidden: Show to compare"), u.TEXT
        else:
            u.icon(d, "x_circle", (u.PAD + 7, u.TOP + 7), 13, u.RED)
            text, color = "Checksum wrong: choose the wrong word", u.RED      # v7.12: no "tap" here
        u.paragraph(d, text, u.TOP, size=12, color=color, x=u.PAD + 18, max_lines=2, line_gap=1, bold=True)
        f_num, f_word = u.font(11, mono=True), u.font(14, bold=True)
        start = self.page * self.PER_PAGE
        for i in range(start, min(len(self.words), start + self.PER_PAGE)):
            rect = self.cell(i)
            selected = i == self.selected
            d.rounded_rectangle(rect, radius=3, fill=u.ACCENT if selected else u.PANEL,
                                outline=None if selected else u.LINE)
            cy = (rect[1] + rect[3]) / 2
            fg = u.BACKGROUND if selected else u.TEXT
            d.text((rect[0] + 20, cy), f"{i + 1}", fill=u.BACKGROUND if selected else u.DIM, font=f_num, anchor="rm")
            word = Translated(self.words[i]) if self.revealed else "•" * 4       # BIP39 words, never translated
            d.text((rect[0] + 25, cy), word, fill=fg if self.revealed else u.DIM, font=f_word, anchor="lm")
        if len(self.words) > self.PER_PAGE:
            d.text((u.RIGHT, self.GRID_TOP + 6 * self.ROW_H + 1), f"{self.page + 1}/{len(self.words) // 12}",
                   fill=u.DIM, font=u.font(10, mono=True), anchor="rt")

    def on_event(self, event):
        if event.kind == Event.PRESS and self.selected is not None and self.items[self.selected].value == "reveal":
            self.revealed = not self.revealed
            self.make_items()
            self.selected = len(self.word_items) + 1
            return "__redraw__"
        if event.kind in (Event.UP, Event.DOWN) and not self.word_items and len(self.words) > self.PER_PAGE:
            pages = len(self.words) // self.PER_PAGE
            self.page = (self.page + (1 if event.kind == Event.DOWN else -1)) % pages
            return "__redraw__"
        return super().on_event(event)


def confirm_discard(hw, typed: int) -> bool:
    """ Leaving the word entry throws the typed words away: ask first """
    if typed == 0:
        return True
    choice = u.MessageScreen("Cancel the seed entry?",
                             f"The {typed} words typed so far will be erased and you will start again.",
                             buttons=("Erase all", "Keep typing"), primary_index=1, values=["drop", "keep"],
                             heading_color=u.YELLOW, icon_name="warning").run(hw)
    return choice == "drop"


def enter_mnemonic(hw):
    import sys
    from nonceverify import wordentry
    return wordentry.enter_mnemonic(hw, screens=sys.modules[__name__])


class KeyboardScreen(u.Screen):
    """ Passphrase entry: printable ASCII, four pages of keys (as on the Seed Max) """
    PAGES = {
        "abc": ["qwertyuiop", "asdfghjkl", "zxcvbnm"],
        "ABC": ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"],
        "123": ["1234567890", "!@#$%^&*()", "-_=+[]{};:"],
        "#+=": ["'\",.<>/?\\|", "`~"],
    }
    KEYS_TOP = 84
    KEY_H = 26
    GAP = 2
    FIELD_FONT = 14
    step = 0
    help_topic = "seed"
    key2_glyph = ("erase", True)

    def __init__(self, text: str = ""):
        super().__init__()
        self.text = text
        self.page = "abc"
        self.back_value = ("done", None)          # KEY3: done, as the Done key
        self.build()

    def build(self, keep=None):
        rows, self.cells = [], {}
        width = (u.RIGHT - u.PAD - 9 * self.GAP) / 10
        for r, chars in enumerate(self.PAGES[self.page]):
            total = len(chars) * width + (len(chars) - 1) * self.GAP
            x = u.PAD + (u.RIGHT - u.PAD - total) / 2
            y = self.KEYS_TOP + r * (self.KEY_H + self.GAP)
            rects = []
            for c, ch in enumerate(chars):
                rect = (int(x), y, int(x + width), y + self.KEY_H)
                rects.append(rect)
                self.cells[(r, c)] = (("char", ch), ch)
                x += width + self.GAP
            rows.append(rects)
        shift = "abc" if self.page == "ABC" else ("ABC" if self.page == "abc" else "abc")
        numbers = "#+=" if self.page == "123" else "123"
        controls = [(38, "aA" if self.page in ("abc", "ABC") else "abc", ("page", shift)),
                    (38, numbers, ("page", numbers)),
                    (74, "space", ("char", " ")),
                    (0, "Done", ("done", None))]
        y = self.KEYS_TOP + 4 * (self.KEY_H + self.GAP) + 4
        x, rects, r = u.PAD, [], len(rows)
        for c, (w, label, value) in enumerate(controls):
            w = w or (u.RIGHT - x)
            rects.append((x, y, x + w, y + self.KEY_H + 2))
            self.cells[(r, c)] = (value, label)
            x += w + 3
        rows.append(rects)
        self.rows = rows
        self.grid = u.Grid(rows)
        if keep is not None and keep in self.cells:
            self.grid.cursor = keep

    def per_line(self) -> int:
        f = u.font(self.FIELD_FONT, mono=True)
        widest = max(f.getlength(c) for c in "MW@·_…")
        return max(8, int((u.RIGHT - 3 * u.PAD) // widest))

    def field_lines(self) -> list:
        n = self.per_line()
        shown = Translated(self.text.replace(" ", "·") + "_")      # typed text, never translated
        if len(shown) > 2 * n:
            shown = "…" + shown[-(2 * n - 1):]
        lines = [shown[:n], shown[n:]] if len(shown) > n else [shown]
        return [Translated(line) for line in lines]

    def draw(self, d, image):
        u.spaced(d, (u.PAD, u.TOP + 1), "PASSPHRASE", u.font(10, bold=True, mono=True), u.DIM, 1, anchor="lt")
        d.text((u.RIGHT, u.TOP + 1), f"{len(self.text)} characters · space = ·", fill=u.DIM,
               font=u.fit_font(f"{len(self.text)} characters · space = ·", 10, 120, mono=True, smallest=8), anchor="rt")
        d.rounded_rectangle((u.PAD, u.TOP + 15, u.RIGHT, self.KEYS_TOP - 6), radius=4, fill=u.PANEL, outline=u.ACCENT)
        for i, line in enumerate(self.field_lines()):
            d.text((u.PAD + 6, u.TOP + 27 + i * 18), line, fill=u.TEXT, font=u.font(self.FIELD_FONT, mono=True),
                   anchor="lm")
        for (r, c), (value, label) in self.cells.items():
            rect = self.rows[r][c]
            selected = (r, c) == self.grid.cursor
            if value[0] == "done":
                u.Item(rect, label, primary=True, size=13).draw(d, selected=selected)
            else:
                u.key_cell(d, rect, Translated(label) if value[0] == "char" else label, selected,
                           size=14 if value[0] == "char" else 11, mono=value[0] == "char")

    def on_key2(self):
        self.text = self.text[:-1]
        return "__redraw__"

    def on_event(self, event):
        if event.kind in (Event.UP, Event.DOWN, Event.LEFT, Event.RIGHT):
            self.grid.move(event.kind)
            return "__redraw__"
        if event.kind == Event.PRESS:
            (kind, arg), _label = self.cells[self.grid.cursor]
            if kind == "char":
                self.text += arg
                if self.page == "ABC":
                    self.page = "abc"
                    self.build(self.grid.cursor)
            elif kind == "page":
                self.page = arg
                self.build(self.grid.cursor)
            elif kind == "done":
                return ("done", self.text)
            return "__redraw__"
        if event.kind == Event.KEY3:
            return ("done", self.text)
        return super().on_event(event)

    def draw_tabs(self, d):
        u.key_tab(d, Event.KEY1, "?", is_icon=False)
        u.key_tab(d, Event.KEY2, "erase")
        u.key_tab(d, Event.KEY3, "check", u.GREEN)
