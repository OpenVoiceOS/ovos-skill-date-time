"""Every row of the en-US timezone table resolves, and a row that does not
resolve makes the skill speak time_tz_not_found instead of raising.

Before this test, `Pacific time` mapped to `US/Pacific-New`, a zone pytz
removed, and `_get_timezone_from_table` called `pytz.timezone` with no
try. `what time is it in Pacific time` raised UnknownTimeZoneError out of
the handler. `China` mapped to `Etc/GMT+8`, which is UTC-8 (POSIX sign),
so the skill spoke the time of the wrong hemisphere.
"""
import datetime
import unittest
import warnings
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
        rows = self.skill.resources.load_named_value_file("timezone.value", ",")
        self.assertGreater(len(rows), 5)
        for name, tz in rows.items():
            with self.subTest(name=name):
                pytz.timezone(tz.strip())

    def test_china_is_utc_plus_eight(self):
        tz = self.skill._get_timezone_from_table("China")
        when = datetime.datetime(2026, 1, 1, tzinfo=pytz.utc).astimezone(tz)
        self.assertEqual(when.utcoffset(), datetime.timedelta(hours=8))

    def test_pacific_time_resolves_to_los_angeles(self):
        tz = self.skill._get_timezone_from_table("Pacific time")
        self.assertIsNotNone(tz)
        self.assertEqual(str(tz), "America/Los_Angeles")

    def test_unknown_zone_in_table_gives_none(self):
        with patch.object(self.skill.resources, "load_named_value_file",
                          return_value={"Nowhere": "US/Pacific-New"}):
            self.assertIsNone(self.skill._get_timezone_from_table("Nowhere"))

    def test_unknown_zone_speaks_tz_not_found(self):
        spoken = []
        with patch.object(self.skill.resources, "load_named_value_file",
                          return_value={"Nowhere land": "US/Pacific-New"}), \
             patch.object(self.skill, "_get_timezone_from_builtins", return_value=None), \
             patch.object(self.skill, "_get_timezone_from_fuzzymatch", return_value=None), \
             patch.object(self.skill, "speak_dialog", side_effect=lambda k, *a, **kw: spoken.append(k)):
            self.skill.handle_query_time(Message("test", {"utterance": "what time is it in Nowhere land",
                                                          "location": "Nowhere land"}))
        self.assertEqual(spoken, ["time_tz_not_found"])
