"""
v7.10 (Ollen, 12 Nov 2026): the interface in five languages and two hosts.

- Language: English (default), Italiano, Français, Español, Deutsch.
- Host (the coordinator the PSBT comes from and the transaction goes back to): Sparrow
  (default) or Nunchuk on the phone.
Both are chosen on the splash, before START, and live ONLY in this process's memory:
never written to the microSD (which is read-only anyway, storage.py), back to English and
Sparrow at every power-on.

How the translation works. The code keeps writing English; the text is translated where
it is measured and drawn (ui.text_width, ui.wrap, ui.spaced, Button, ui.Draw.text). The
English text is the key; text built with values ("Sends 0.0015 BTC to 1 other
address(es)") matches a template key ("Sends {0} to {1} other address(es)") and the
values are translated in turn ("change #3" -> "resto #3"). A text with no translation is
shown in English: nothing can break, at worst a sentence stays in English. With English
and Sparrow nothing is looked up at all: the screens are byte for byte the ones of v7.9
(the splash only gains the host and language chips).

With Nunchuk, the texts whose steps differ from Sparrow's (menus, where the txid is, how
to broadcast) are replaced by their Nunchuk version (NUNCHUK below, translated like any
other text); in every other text "Sparrow" becomes "Nunchuk".

Standard library only.
"""
import importlib
import re

LANGUAGES = (("en", "EN"), ("it", "IT"), ("fr", "FR"), ("es", "ES"), ("de", "DE"))
HOSTS = (("sparrow", "Sparrow"), ("nunchuk", "Nunchuk"))

_state = {"lang": "en", "host": "sparrow"}
_catalogs = {}
_templates = {}
_cache = {}


def language() -> str:
    return _state["lang"]


def host() -> str:
    return _state["host"]


def host_name() -> str:
    return dict(HOSTS)[_state["host"]]


def set_language(code: str):
    if code not in dict(LANGUAGES):
        raise ValueError("unknown language")
    _state["lang"] = code
    _cache.clear()


def set_host(code: str):
    if code not in dict(HOSTS):
        raise ValueError("unknown host")
    _state["host"] = code
    _cache.clear()


def reset():
    """ English and Sparrow (power-on state; tests) """
    _state.update(lang="en", host="sparrow")
    _cache.clear()


def catalog(lang: str) -> dict:
    """
    English text -> translation. The English texts are in i18n_keys.py (KEYS, id -> text),
    the translations in i18n_<lang>.py (BY_ID, id -> text): a translation never depends on
    copying an English sentence exactly.
    """
    if lang == "en":
        return {}
    if lang not in _catalogs:
        from nonceverify.i18n_keys import KEYS
        by_id = importlib.import_module(f"nonceverify.i18n_{lang}").BY_ID
        _catalogs[lang] = {KEYS[k]: v for k, v in by_id.items() if k in KEYS}
    return _catalogs[lang]


_PLACEHOLDER = re.compile(r"\{(\d+)\}")


def _compile(key: str):
    """ A template key -> (regex, literal prefix) """
    parts, pos = [], 0
    for m in _PLACEHOLDER.finditer(key):
        parts.append(re.escape(key[pos:m.start()]))
        parts.append(f"(?P<g{m.group(1)}>.+?)")
        pos = m.end()
    parts.append(re.escape(key[pos:]))
    prefix = key[:key.find("{")]
    return re.compile("^" + "".join(parts) + "$", re.S), prefix


def templates(lang: str) -> list:
    """ The template keys of `lang` (and of the Nunchuk texts), longest literal first """
    key = (lang, _state["host"])
    if key not in _templates:
        keys = set(k for k in catalog(lang) if _PLACEHOLDER.search(k))
        if _state["host"] == "nunchuk":
            keys |= set(k for k in NUNCHUK if _PLACEHOLDER.search(k))
        keys |= set(k for k in TEMPLATE_KEYS)
        compiled = []
        for k in keys:
            regex, prefix = _compile(k)
            compiled.append((len(_PLACEHOLDER.sub("", k)), k, regex, prefix))
        compiled.sort(key=lambda c: -c[0])
        _templates[key] = [(k, regex, prefix) for _n, k, regex, prefix in compiled]
    return _templates[key]


def _swap_host(text: str) -> str:
    """ Nunchuk: "Sparrow" -> "Nunchuk" in a text that has no Nunchuk version of its own """
    return text.replace("Sparrow", "Nunchuk") if _state["host"] == "nunchuk" else text


def _translate(text: str, depth: int = 0) -> str:
    lang, nunchuk = _state["lang"], _state["host"] == "nunchuk"
    cat = catalog(lang)
    if nunchuk and text in NUNCHUK:
        source = NUNCHUK[text]               # its own Nunchuk version: names kept as written
        return cat.get(source, source)
    if text in cat:
        return _swap_host(cat[text])
    if depth < 3:
        for key, regex, prefix in templates(lang):
            if lang == "en" and key not in NUNCHUK:
                continue                    # English: only the Nunchuk templates change anything
            if prefix and not text.startswith(prefix):
                continue
            m = regex.match(text)
            if not m:
                continue
            values = {name: _translate(value, depth + 1) for name, value in m.groupdict().items()}
            if nunchuk and key in NUNCHUK:
                pattern = cat.get(NUNCHUK[key], NUNCHUK[key])
            else:
                pattern = _swap_host(cat.get(key, key))
            try:
                return _PLACEHOLDER.sub(lambda p: values["g" + p.group(1)], pattern)
            except KeyError:
                return text
        if "; " in text:
            return "; ".join(_translate(part, depth + 1) for part in text.split("; "))
    return _swap_host(text)


class Translated(str):
    """ Text already translated (the lines ui.wrap returns): t() leaves it as it is """


def t(text):
    """ `text` in the language and for the host chosen (English and Sparrow: unchanged) """
    if not isinstance(text, str) or not text or isinstance(text, Translated):
        return text
    if _state["lang"] == "en" and _state["host"] == "sparrow":
        return text
    key = (_state["lang"], _state["host"], text)
    out = _cache.get(key)
    if out is None:
        out = _translate(text)
        if len(_cache) > 4000:
            _cache.clear()
        _cache[key] = out
    return out


# Template keys used by the code (values in {0}, {1}... order), translated per language in
# the catalogs. Listed here so that a template is recognised even before a catalog has it.
TEMPLATE_KEYS = ()

# English Sparrow text -> English Nunchuk text, where the steps differ. Translated like
# any other English text (the catalogs have both versions).
NUNCHUK = {}

from nonceverify.i18n_host import NUNCHUK as _NUNCHUK, TEMPLATE_KEYS as _TEMPLATE_KEYS  # noqa: E402
NUNCHUK.update(_NUNCHUK)
TEMPLATE_KEYS = tuple(_TEMPLATE_KEYS)
