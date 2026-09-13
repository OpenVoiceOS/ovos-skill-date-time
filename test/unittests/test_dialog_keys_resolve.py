"""Every dialog key a handler speaks must resolve to a real dialog file.

A dialog key with no file does not raise. ``speak_dialog`` renders the raw
key, so the device speaks "time_current" (or "time current" for a dotted
key) and the intent tests still pass, because they only check routing.

This test reads the dialog keys from the skill code with ``ast``:

- the literal first argument of ``speak_dialog``, ``speak_time`` and
  ``get_response``;
- every string literal assigned to a variable that one of those calls
  receives as its first argument (``dialog = "a" if x else "b"``).

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
SPEAK_CALLS = {"speak_dialog", "speak_time", "get_response"}

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


def _string_constants(node):
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def spoken_dialog_keys(code):
    """Return (keys, unresolved) for the skill code.

    ``unresolved`` names each call whose first argument is not a literal
    and not a local variable with string literal assignments.
    """
    keys, unresolved = set(), []
    tree = ast.parse(code)
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in func.args.args + func.args.kwonlyargs}
        assigned = {}
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, set()).update(
                            _string_constants(node.value))
        for node in ast.walk(func):
            if not (isinstance(node, ast.Call)
                    and _call_name(node) in SPEAK_CALLS and node.args):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
            elif isinstance(first, ast.Name) and assigned.get(first.id):
                keys.update(assigned[first.id])
            elif isinstance(first, ast.Name) and first.id in params \
                    and func.name in SPEAK_CALLS:
                # a speak helper that forwards its own parameter; the
                # callers supply the literal
                continue
            else:
                unresolved.append(f"{func.name}:{node.lineno}")
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

        from ovos_utils.messagebus import FakeBus
        from ovos_skill_date_time import TimeSkill

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
