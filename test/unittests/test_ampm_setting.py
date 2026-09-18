import datetime
import unittest
import warnings
from unittest import mock

import pytz
from ovos_bus_client.session import SessionManager
from ovos_utils.fakebus import FakeBus

from ovos_skill_date_time import TimeSkill

# A fixed UTC instant, morning in UTC (and therefore in the "local" test's
# pinned UTC timezone) and evening in Asia/Tokyo (UTC+9) -- deterministic
# AM/PM regardless of the real wall-clock time the suite runs at.
_ANCHOR_UTC = datetime.datetime(2024, 6, 15, 9, 0, tzinfo=pytz.utc)


class TestAmpmSetting(unittest.TestCase):
    """AM/PM follows the session 12/24h setting, never the presence of a location."""

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore")
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")
        # Pin the "local" timezone so get_spoken_time()/get_display_time()
        # (no location) are as deterministic as the "tokyo" location calls,
        # instead of depending on this environment's real default timezone.
        cls._tz_patch = mock.patch.object(
            type(cls.skill), "location_timezone",
            new_callable=mock.PropertyMock, return_value="UTC",
        )
        cls._tz_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._tz_patch.stop()

    def test_12h_local_time_says_ampm(self):
        SessionManager.get().time_format = "half"
        self.assertFalse(self.skill.use_24hour)
        self.assertIn("a.m.", self.skill.get_spoken_time(anchor_date=_ANCHOR_UTC))
        self.assertIn("AM", self.skill.get_display_time(anchor_date=_ANCHOR_UTC))

    def test_24h_local_time_says_no_ampm(self):
        SessionManager.get().time_format = "full"
        self.assertTrue(self.skill.use_24hour)
        self.assertNotIn("a.m.", self.skill.get_spoken_time(anchor_date=_ANCHOR_UTC))
        self.assertNotIn("p.m.", self.skill.get_spoken_time(anchor_date=_ANCHOR_UTC))
        self.assertNotIn("AM", self.skill.get_display_time(anchor_date=_ANCHOR_UTC))
        self.assertNotIn("PM", self.skill.get_display_time(anchor_date=_ANCHOR_UTC))

    def test_24h_location_time_says_no_ampm(self):
        SessionManager.get().time_format = "full"
        self.assertNotIn("p.m.", self.skill.get_spoken_time("tokyo", anchor_date=_ANCHOR_UTC))
        self.assertNotIn("PM", self.skill.get_display_time("tokyo", anchor_date=_ANCHOR_UTC))

    def test_12h_location_time_says_ampm(self):
        SessionManager.get().time_format = "half"
        self.assertIn("p.m.", self.skill.get_spoken_time("tokyo", anchor_date=_ANCHOR_UTC))
        self.assertIn("PM", self.skill.get_display_time("tokyo", anchor_date=_ANCHOR_UTC))
