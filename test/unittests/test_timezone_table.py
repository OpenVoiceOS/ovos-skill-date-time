"""Every row of the en-US timezone table resolves, and a row that does not
resolve makes the skill speak time_tz_not_found instead of raising.

Before this test, `Pacific time` mapped to `US/Pacific-New`, a zone pytz
removed, and `_get_timezone_from_table` called `pytz.timezone` with no
try. `what time is it in Pacific time` raised UnknownTimeZoneError out of
the handler. `China` mapped to `Etc/GMT+8`, which is UTC-8 (POSIX sign),
so the skill spoke the time of the wrong hemisphere.
"""
import datetime
import re
import unittest
import warnings
import zoneinfo
from pathlib import Path
from unittest.mock import patch

import pytz
from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from ovos_skill_date_time import TimeSkill

ROOT = Path(__file__).resolve().parents[2]


class TestTimezoneTable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore")
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")

    def test_every_en_us_row_resolves(self):
        rows = self.skill._load_timezone_table()
        self.assertGreater(len(rows), 5)
        for name, tz in rows.items():
            with self.subTest(name=name):
                pytz.timezone(tz)

    def test_china_is_utc_plus_eight(self):
        tz = self.skill._get_timezone_from_table("China")
        when = datetime.datetime(2026, 1, 1, tzinfo=pytz.utc).astimezone(tz)
        self.assertEqual(when.utcoffset(), datetime.timedelta(hours=8))

    def test_pacific_time_resolves_to_los_angeles(self):
        tz = self.skill._get_timezone_from_table("Pacific time")
        self.assertIsNotNone(tz)
        self.assertEqual(str(tz), "America/Los_Angeles")

    def test_unknown_zone_in_table_gives_none(self):
        with patch.object(self.skill, "_load_timezone_table",
                          return_value={"Nowhere": "US/Pacific-New"}):
            self.assertIsNone(self.skill._get_timezone_from_table("Nowhere"))

    def test_unknown_zone_speaks_tz_not_found(self):
        spoken = []
        with patch.object(self.skill, "_load_timezone_table",
                          return_value={"Nowhere land": "US/Pacific-New"}), \
             patch.object(self.skill, "_get_timezone_from_builtins", return_value=None), \
             patch.object(self.skill, "_get_timezone_from_fuzzymatch", return_value=None), \
             patch.object(self.skill, "speak_dialog", side_effect=lambda k, *a, **kw: spoken.append(k)):
            self.skill.handle_query_time(Message("test", {"utterance": "what time is it in Nowhere land",
                                                          "location": "Nowhere land"}))
        self.assertEqual(spoken, ["time_tz_not_found"])


class TestEveryLocaleTimezoneTable(unittest.TestCase):
    """Every locale's table resolves, and every id is one en-US uses, or a
    listed extra with the offset its name promises.

    Before this test 20 languages mapped their word for China to Etc/GMT+8
    (UTC-8, the POSIX sign), 21 kept the removed US/Pacific-New, fr-FR held
    translated ids (Etats-Unis/Centre), cs-CZ translated "Etc" into "atd",
    and fa-IR carried no id at all. A translated locale names the same
    places as en-US, so its ids come from the en-US set; a locale that adds
    a place lists it in EXTRA with the offset the name promises.
    """

    UTC_JAN = datetime.datetime(2026, 1, 1, tzinfo=pytz.utc)
    UTC_JUL = datetime.datetime(2026, 7, 1, tzinfo=pytz.utc)
    HOUR = datetime.timedelta(hours=1)
    # {lang: {id: (january offset, july offset)}}
    EXTRA = {
        "cs-CZ": {"CET": (HOUR, 2 * HOUR),
                  "Europe/Prague": (HOUR, 2 * HOUR),
                  "Europe/Bratislava": (HOUR, 2 * HOUR)},
        "pl-PL": {"Etc/GMT-1": (HOUR, HOUR), "Etc/GMT-2": (2 * HOUR, 2 * HOUR)},
    }

    @staticmethod
    def _rows(lang_dir):
        """(place, zone) pairs read from the `timezone_*.voc` files of a locale."""
        zones = {"timezone_" + re.sub(r"[/-]", "_", zone.lower()): zone
                 for zone in zoneinfo.available_timezones()}
        rows = []
        for path in sorted(lang_dir.glob("timezone_*.voc")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    rows.append((line, zones[path.stem]))
        return rows

    def _offsets(self, tz_name):
        tz = pytz.timezone(tz_name)
        return (self.UTC_JAN.astimezone(tz).utcoffset(), self.UTC_JUL.astimezone(tz).utcoffset())

    def test_every_row_of_every_locale_resolves_to_an_en_us_id_or_a_listed_extra(self):
        locale = ROOT / "locale"
        en_ids = {tz for _, tz in self._rows(locale / "en-US")}
        for lang_dir in sorted(p.parent for p in locale.glob("*/timezone_*.voc")):
            lang = lang_dir.name
            rows = self._rows(lang_dir)
            with self.subTest(lang=lang):
                self.assertGreater(len(rows), 5, f"{lang} table is empty or short")
                for name, tz in rows:
                    with self.subTest(lang=lang, name=name):
                        self.assertTrue(tz, f"{lang}: {name!r} carries no timezone id")
                        got = self._offsets(tz)  # UnknownTimeZoneError on a bad id
                        if tz in en_ids:
                            continue
                        self.assertIn(tz, self.EXTRA.get(lang, {}),
                                      f"{lang}: {name!r} -> {tz!r} is not an en-US id and not a listed extra")
                        self.assertEqual(got, self.EXTRA[lang][tz],
                                         f"{lang}: {name!r} -> {tz} does not carry the offset its name promises")


class TestTimezoneVocFiles(unittest.TestCase):
    """The place names of each zone live in one `timezone_<zone>.voc` file."""

    LOCALE = ROOT / "locale"

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore")
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")

    def test_no_value_file_ships(self):
        self.assertEqual(sorted(self.LOCALE.rglob("*.value")), [])

    def test_every_voc_base_name_is_compliant(self):
        for path in sorted(self.LOCALE.glob("*/timezone_*.voc")):
            with self.subTest(path=str(path.relative_to(self.LOCALE))):
                self.assertRegex(path.stem, r"^[a-z0-9_]+$")

    def test_every_voc_maps_to_an_available_zone(self):
        zones = {"timezone_" + zone.lower().replace("/", "_").replace("-", "_")
                 for zone in zoneinfo.available_timezones()}
        paths = sorted(self.LOCALE.glob("*/timezone_*.voc"))
        self.assertGreater(len(paths), 24)
        for path in paths:
            with self.subTest(path=str(path.relative_to(self.LOCALE))):
                self.assertIn(path.stem, zones)

    def test_zone_name_transform_is_injective(self):
        names = [TimeSkill._timezone_voc_name(zone)
                 for zone in zoneinfo.available_timezones()]
        self.assertEqual(len(names), len(set(names)))

    def test_en_us_table_equals_the_voc_files(self):
        zones = {"timezone_" + zone.lower().replace("/", "_").replace("-", "_"): zone
                 for zone in zoneinfo.available_timezones()}
        expected = {}
        for path in sorted((self.LOCALE / "en-US").glob("timezone_*.voc")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    expected[line.strip()] = zones[path.stem]
        self.assertEqual(len(expected), 10)
        self.assertEqual(self.skill._load_timezone_table(), expected)
        self.assertEqual(expected["Kansas City"], "US/Central")
        self.assertEqual(expected["East coast"], "US/Eastern")

    def test_voc_for_an_unknown_zone_is_logged_and_skipped(self):
        with patch.object(self.skill.resources, "static", {}), \
             patch("ovos_skill_date_time.zoneinfo.available_timezones",
                   return_value={"US/Central"}), \
             patch("ovos_skill_date_time.LOG") as log:
            table = self.skill._load_timezone_table()
        self.assertEqual(set(table.values()), {"US/Central"})
        self.assertTrue(log.error.called)

    def test_non_injective_zone_names_fail_loudly(self):
        with patch.object(self.skill.resources, "static", {}), \
             patch("ovos_skill_date_time.zoneinfo.available_timezones",
                   return_value={"Etc/GMT-1", "Etc/GMT_1"}):
            with self.assertRaises(RuntimeError):
                self.skill._load_timezone_table()
