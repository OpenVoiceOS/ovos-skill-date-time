"""Regression tests for the locale template resources.

Every non-comment line in the ``.intent``, ``.voc`` and ``.entity`` files must
expand into valid samples, and intent slot names must come from the canonical
inventory the skill handlers read from ``message.data``.
"""
import re
from os.path import dirname, join
from pathlib import Path
from unittest import TestCase

from ovos_spec_tools.expansion import expand

LOCALE_DIR = Path(join(dirname(dirname(dirname(__file__))), "locale"))
TEMPLATE_SUFFIXES = (".intent", ".voc", ".entity")
# slot names the intent handlers read from message.data
CANONICAL_SLOTS = {"location", "offset", "date", "weekday", "month"}


def iter_template_lines():
    for path in sorted(LOCALE_DIR.rglob("*")):
        if path.suffix not in TEMPLATE_SUFFIXES:
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            yield path, lineno, stripped


class TestLocaleTemplates(TestCase):

    def test_locale_dir_exists(self):
        self.assertTrue(LOCALE_DIR.is_dir())
        self.assertTrue(any(iter_template_lines()))

    def test_every_template_line_expands(self):
        failures = []
        for path, lineno, line in iter_template_lines():
            try:
                expand(line)
            except Exception as e:
                rel = path.relative_to(LOCALE_DIR)
                failures.append(f"{rel}:{lineno}: {line!r} -> {e}")
        self.assertEqual(failures, [],
                         "malformed template lines:\n" + "\n".join(failures))

    def test_intent_slot_names_are_canonical(self):
        failures = []
        for path, lineno, line in iter_template_lines():
            if path.suffix != ".intent":
                continue
            for slot in re.findall(r"\{([^{}]+)\}", line):
                if slot.strip() not in CANONICAL_SLOTS:
                    rel = path.relative_to(LOCALE_DIR)
                    failures.append(f"{rel}:{lineno}: {{{slot}}}")
        self.assertEqual(failures, [],
                         "non-canonical intent slot names:\n" + "\n".join(failures))
