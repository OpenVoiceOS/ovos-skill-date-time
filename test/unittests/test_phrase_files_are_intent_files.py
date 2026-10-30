"""Phrase stores ship as unregistered `.intent` files, never as `.list` files.

OVOS-INTENT-2 §1 defines seven resource roles and `.list` is not one of them.
"""
import unittest
from pathlib import Path

from ovos_utils.messagebus import FakeBus

from ovos_skill_date_time import TimeSkill

ROOT = Path(__file__).parents[2]
LOCALE = ROOT / "locale"
SKILL_ID = "ovos-skill-date-time.openvoiceos"


class TestPhraseFilesAreIntentFiles(unittest.TestCase):

    def test_no_list_file_ships(self):
        found = sorted(str(p.relative_to(ROOT)) for p in LOCALE.rglob("*.list"))
        self.assertEqual([], found)

    def test_the_skill_loads_the_lines_of_the_intent_file(self):
        skill = TimeSkill()
        skill._startup(FakeBus(), SKILL_ID)
        skill.config_core["lang"] = "en-US"
        skill._lang = "en-US"
        skill._resources = None
        skill.resources.static.clear()
        path = LOCALE / "en-US" / "ambiguous_locations.intent"
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertGreater(len(lines), 0)
        self.assertEqual({line.casefold() for line in lines},
                         skill._load_locale_phrase_set("ambiguous_locations"))

    def test_a_regional_session_finds_the_locale_directory(self):
        skill = TimeSkill()
        skill._startup(FakeBus(), SKILL_ID)
        skill.config_core["lang"] = "en"
        skill._lang = "en"
        skill._resources = None
        skill.resources.static.clear()
        self.assertGreater(len(skill._load_locale_phrase_set("ambiguous_locations")), 0)


if __name__ == "__main__":
    unittest.main()
