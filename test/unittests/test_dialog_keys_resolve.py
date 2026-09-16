"""Every dialog key a handler speaks must resolve to a real dialog file.

A dialog key with no file does not raise. ``speak_dialog`` renders the raw
key, so the device speaks "time_current" (or "time current" for a dotted
key) and the intent tests still pass, because they only check routing.

This test reads the dialog keys from the skill code with ``ast``:

- the literal dialog argument of every call in ``SPEAK_CALLS``, given
  by position or by keyword (``speak_dialog(key="month_current")``);
- every string literal assigned to a variable that one of those calls
  receives as that argument (``dialog = "a" if x else "b"``).

A name that any assignment builds at run time (an f-string, a ``+``
concatenation, a ``+=``) is never read as a key. The call is listed in
``unresolved`` instead, so the failure says "built at run time" and not
"no dialog file".

It then checks each key in every shipped locale, in two ways: the file
``<key>.dialog`` exists, and the skill's own dialog renderer does not give
back the key.

A locale that does not yet translate some dialogs is listed in
``KNOWN_GAPS``. The list can only shrink: a new missing key fails, and a
listed key that is now present also fails, so the list stays true.
"""
import ast
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCALE_DIR = ROOT / "locale"
SKILL_CODE = ROOT / "__init__.py"
SKILL_ID = "ovos-skill-date-time.openvoiceos"
# Call name -> (index of the positional dialog argument, keyword names
# that carry the same argument). ``ask_selection`` takes the options first
# and the dialog second.
SPEAK_CALLS = {
    "speak_dialog": (0, ("key",)),
    "speak_time": (0, ("key",)),
    "get_response": (0, ("dialog",)),
    "ask_yesno": (0, ("prompt",)),
    "ask_selection": (1, ("dialog",)),
}

# Dialog keys that a locale does not ship yet. A handler in these locales
# speaks the raw key. Remove a key here when its translation lands.
KNOWN_GAPS = {
    "cs-CZ": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
    "fa-IR": (
        "day_current",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
    ),
    "hu-HU": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
    "kab": (
        "date_future_weekend",
        "date_last_weekend",
        "did_you_mean_timezone",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "next_leap_year",
        "time_current",
        "time_future",
        "time_tz_not_found",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
    ),
    "pl-PL": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
    "ru-RU": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
    "sv-FI": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
    "tr-TR": (
        "day_current",
        "extract_date_error",
        "leap_year_current_no",
        "leap_year_current_yes",
        "leap_year_either_no",
        "leap_year_either_yes",
        "leap_year_next_no",
        "leap_year_next_yes",
        "month_current",
        "weekday_at_date_future",
        "weekday_at_date_past",
        "weekday_current",
        "weekday_matches_date_future_no",
        "weekday_matches_date_future_yes",
        "weekday_matches_date_past_no",
        "weekday_matches_date_past_yes",
        "weekday_matches_date_today_no",
        "weekday_matches_date_today_yes",
        "year_current",
    ),
}


def _call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _literal_values(node):
    """Return the string constants ``node`` can give, or ``None``.

    ``None`` means the value is built at run time. Only a string constant
    and a conditional expression of string constants are literal.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        body = _literal_values(node.body)
        orelse = _literal_values(node.orelse)
        if body is None or orelse is None:
            return None
        return body | orelse
    return None


def _dialog_argument(node, name):
    """Return the dialog argument node of a call, or ``None``."""
    index, keywords = SPEAK_CALLS[name]
    if len(node.args) > index:
        return node.args[index]
    for keyword in node.keywords:
        if keyword.arg in keywords:
            return keyword.value
    return None


def spoken_dialog_keys(code):
    """Return (keys, unresolved) for the skill code.

    ``unresolved`` names each call whose dialog argument is absent, is
    not a literal, and is not a local variable that only string literals
    assign.
    """
    keys, unresolved = set(), []
    tree = ast.parse(code)
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in func.args.args + func.args.kwonlyargs}
        assigned, runtime = {}, set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            elif isinstance(node, ast.AugAssign):
                # "name += ..." always builds the value at run time
                targets, value = [node.target], None
            else:
                continue
            values = None if value is None else _literal_values(value)
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if values is None:
                    runtime.add(target.id)
                else:
                    assigned.setdefault(target.id, set()).update(values)
        for node in ast.walk(func):
            name = _call_name(node) if isinstance(node, ast.Call) else None
            if name not in SPEAK_CALLS:
                continue
            where = f"{func.name}:{node.lineno}"
            argument = _dialog_argument(node, name)
            literal = None if argument is None else _literal_values(argument)
            if literal is not None:
                keys.update(literal)
            elif isinstance(argument, ast.Name) and argument.id not in runtime \
                    and assigned.get(argument.id):
                keys.update(assigned[argument.id])
            elif isinstance(argument, ast.Name) and argument.id in params \
                    and func.name in SPEAK_CALLS:
                # a speak helper that forwards its own parameter; the
                # callers supply the literal
                continue
            else:
                unresolved.append(where)
    return keys, unresolved


def shipped_locales():
    return sorted(p.name for p in LOCALE_DIR.iterdir() if p.is_dir())


def raw_key_forms(key):
    return {key, key.replace(".", " "), key.replace("_", " ")}


class TestSpokenDialogKeysStatic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.keys, cls.unresolved = spoken_dialog_keys(
            SKILL_CODE.read_text(encoding="utf-8"))

    def test_extractor_finds_known_keys(self):
        # positive control: a helper that finds nothing proves nothing
        for key in ("time_current", "time_future", "date",
                    "weekday_matches_date_past_no", "leap_year_current_no"):
            self.assertIn(key, self.keys)
        self.assertGreaterEqual(len(self.keys), 25)

    def test_extractor_sees_a_stale_key(self):
        # positive control: the extractor reads a renamed key back
        code = SKILL_CODE.read_text(encoding="utf-8").replace(
            'speak_time("time_current"', 'speak_time("time.current"')
        keys, _ = spoken_dialog_keys(code)
        self.assertIn("time.current", keys)

    def test_every_dialog_argument_is_resolvable(self):
        self.assertEqual(self.unresolved, [],
                         "dialog names built at run time; list them by hand")

    def test_a_run_time_name_is_unresolved_not_a_fragment(self):
        # positive control first: the same shape with constants resolves
        literal = """
def handle_month(self, message):
    dialog = "month_current" if message else "month_next"
    self.speak_dialog(dialog)
"""
        keys, unresolved = spoken_dialog_keys(literal)
        self.assertEqual(keys, {"month_current", "month_next"})
        self.assertEqual(unresolved, [])
        # an f-string, a "+" and a "+=" each give no key and one entry
        for value in ('f"month_{when}"',
                      '"month_" + when',
                      '"month_"\n    dialog += when'):
            code = f"""
def handle_month(self, when):
    dialog = {value}
    self.speak_dialog(dialog)
"""
            keys, unresolved = spoken_dialog_keys(code)
            self.assertEqual(keys, set(), value)
            self.assertEqual(len(unresolved), 1, value)
            self.assertTrue(unresolved[0].startswith("handle_month:"), value)

    def test_a_keyword_dialog_argument_is_read(self):
        code = """
def handle_month(self, message):
    self.speak_dialog(key="month_current")
    self.get_response(dialog="did_you_mean_timezone")
    self.ask_yesno(prompt="leap_year_current_no")
    self.ask_selection(options, dialog="next_leap_year")
"""
        keys, unresolved = spoken_dialog_keys(code)
        self.assertEqual(keys, {"month_current", "did_you_mean_timezone",
                                "leap_year_current_no", "next_leap_year"})
        self.assertEqual(unresolved, [])

    def test_a_call_with_no_dialog_argument_is_unresolved(self):
        # negative control: the call is listed, never skipped in silence
        code = """
def handle_month(self, **kwargs):
    self.speak_dialog(**kwargs)
"""
        keys, unresolved = spoken_dialog_keys(code)
        self.assertEqual(keys, set())
        self.assertEqual(unresolved, ["handle_month:3"])

    def test_known_gaps_name_real_locales_and_keys(self):
        locales = set(shipped_locales())
        for lang, missing in KNOWN_GAPS.items():
            self.assertIn(lang, locales)
            self.assertLessEqual(set(missing), self.keys, lang)

    def test_every_spoken_key_has_a_dialog_file(self):
        new_gaps, stale_gaps = [], []
        for lang in shipped_locales():
            present = {p.stem for p in (LOCALE_DIR / lang).rglob("*.dialog")}
            missing = self.keys - present
            allowed = set(KNOWN_GAPS.get(lang, ()))
            new_gaps += [f"{lang}/{k}.dialog" for k in sorted(missing - allowed)]
            stale_gaps += [f"{lang}/{k}" for k in sorted(allowed - missing)]
        self.assertEqual(new_gaps, [],
                         "spoken dialog keys with no dialog file")
        self.assertEqual(stale_gaps, [],
                         "KNOWN_GAPS lists keys that now exist; remove them")


class TestSpokenDialogKeysRender(unittest.TestCase):
    """The skill's own renderer must not give back the key as speech."""

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-dialog-")
        cls._saved = {}
        for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME",
                    "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            cls._saved[var] = os.environ.get(var)
            os.environ[var] = os.path.join(cls._xdg.name, var.lower())

        from ovos_skill_date_time import TimeSkill
        from ovos_utils.messagebus import FakeBus

        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), SKILL_ID)
        cls.keys, _ = spoken_dialog_keys(SKILL_CODE.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.skill.shutdown()
        for var, value in cls._saved.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        cls._xdg.cleanup()

    def _render(self, lang, key):
        # supply a value for every {slot} the locale's dialog file names
        slots = set()
        for path in (LOCALE_DIR / lang).rglob(f"{key}.dialog"):
            slots.update(re.findall(r"\{([^{}]+)\}",
                                    path.read_text(encoding="utf-8")))
        renderer = self.skill.load_lang(lang=lang).dialog_renderer
        return renderer.render(key, {slot: "slot" for slot in slots})

    def test_renderer_gives_back_a_missing_key(self):
        # positive control: the check below detects the raw-key fallback
        self.assertIn(self._render("en-US", "time.current"),
                      raw_key_forms("time.current"))

    def test_spoken_text_is_never_the_dialog_key(self):
        failures = []
        for lang in shipped_locales():
            allowed = set(KNOWN_GAPS.get(lang, ()))
            for key in sorted(self.keys - allowed):
                spoken = self._render(lang, key)
                if spoken.strip() in raw_key_forms(key):
                    failures.append(f"{lang}: {key!r} -> {spoken!r}")
        self.assertEqual(failures, [], "dialog keys spoken as raw text")


if __name__ == "__main__":
    unittest.main()
