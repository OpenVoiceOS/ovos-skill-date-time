import datetime
import unittest
import warnings
from unittest.mock import patch

import pytz
from ovos_bus_client.session import SessionManager
from ovos_utils.fakebus import FakeBus

from ovos_skill_date_time import TimeSkill

# Fixed points in the day so the a.m./p.m. assertions hold no matter what
# time it is when the suite runs.
MORNING = datetime.datetime(2024, 1, 1, 9, 0, tzinfo=pytz.UTC)
AFTERNOON = datetime.datetime(2024, 1, 1, 15, 0, tzinfo=pytz.UTC)

# 06:00 UTC is 15:00 (3 p.m.) in Tokyo (UTC+9), so the location cases below
# exercise get_timezone_in_location for real: passed anchor_date only fixes
# the instant, not the timezone conversion.
TOKYO_ANCHOR = datetime.datetime(2024, 1, 1, 6, 0, tzinfo=pytz.UTC)


class TestAmpmSetting(unittest.TestCase):
    """AM/PM follows the session 12/24h setting, never the presence of a location."""

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore")
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")

    def test_12h_local_time_says_am_in_the_morning(self):
        SessionManager.get().time_format = "half"
        self.assertFalse(self.skill.use_24hour)
        with patch.object(self.skill, "get_datetime", return_value=MORNING):
            self.assertIn("a.m.", self.skill.get_spoken_time())
            self.assertIn("AM", self.skill.get_display_time())

    def test_12h_local_time_says_pm_in_the_afternoon(self):
        SessionManager.get().time_format = "half"
        self.assertFalse(self.skill.use_24hour)
        with patch.object(self.skill, "get_datetime", return_value=AFTERNOON):
            self.assertIn("p.m.", self.skill.get_spoken_time())
            self.assertIn("PM", self.skill.get_display_time())

    def test_24h_local_time_says_no_ampm(self):
        SessionManager.get().time_format = "full"
        self.assertTrue(self.skill.use_24hour)
        with patch.object(self.skill, "get_datetime", return_value=MORNING):
            self.assertNotIn("a.m.", self.skill.get_spoken_time())
            self.assertNotIn("p.m.", self.skill.get_spoken_time())
            self.assertNotIn("AM", self.skill.get_display_time())
            self.assertNotIn("PM", self.skill.get_display_time())

    def test_24h_location_time_says_no_ampm(self):
        # anchor_date only fixes the instant; get_datetime still calls
        # get_timezone_in_location("tokyo") to convert it, so a broken
        # timezone lookup shows up here rather than being mocked away.
        SessionManager.get().time_format = "full"
        self.assertNotIn("p.m.", self.skill.get_spoken_time("tokyo", anchor_date=TOKYO_ANCHOR))
        self.assertNotIn("PM", self.skill.get_display_time("tokyo", anchor_date=TOKYO_ANCHOR))

    def test_12h_location_time_says_ampm(self):
        SessionManager.get().time_format = "half"
        self.assertIn("p.m.", self.skill.get_spoken_time("tokyo", anchor_date=TOKYO_ANCHOR))
        self.assertIn("PM", self.skill.get_display_time("tokyo", anchor_date=TOKYO_ANCHOR))
