"""The regex location path stays gone.

ovos-workshop deprecates regex intents: they are adapt-engine only and go away
in 10.0.0. This skill read a `location.rx` per locale through its own
`_extract_location`, beside the `{location}` slot the intent files carry. The
file could not work in every locale it shipped: the hu-HU and eu-ES patterns let
the alternation bind the whole pattern, so a match carried no `Location` group
and the handler raised on `None`.

The third case is the one that carries weight. The first two only say the files
and the method are absent, which a tree that never had them would satisfy; the
third says the path that replaced them is actually there, in every locale.
"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCALE = REPO / "locale"
LOCATED_INTENTS = ("current_date", "what_day_is_it",
                   "what_time_is_it", "what_time_will_it_be")


class TestNoRegexResources(unittest.TestCase):
    def test_no_regex_resource_files(self):
        found = sorted(str(p.relative_to(REPO)) for p in REPO.rglob("*.rx")
                       if ".venv" not in p.parts and "build" not in p.parts)
        self.assertEqual([], found, f"regex resources are deprecated, found: {found}")

    def test_no_regex_extractor(self):
        source = (REPO / "__init__.py").read_text(encoding="utf-8")
        for symbol in ("_extract_location", "'regex'", '"regex"'):
            self.assertNotIn(symbol, source,
                             f"{symbol} is the regex location path and was removed")

    def test_every_locale_carries_the_location_slot(self):
        locales = sorted(p.name for p in LOCALE.iterdir() if p.is_dir())
        self.assertTrue(locales, "no locales found")
        missing = []
        for lang in locales:
            for name in LOCATED_INTENTS:
                path = LOCALE / lang / "intents" / f"{name}.intent"
                if not path.exists():
                    missing.append(f"{lang}/{name}.intent is absent")
                elif "{location}" not in path.read_text(encoding="utf-8"):
                    missing.append(f"{lang}/{name}.intent carries no {{location}}")
        self.assertEqual([], missing,
                         "the slot is the only location path now: " + "; ".join(missing))


if __name__ == "__main__":
    unittest.main()
