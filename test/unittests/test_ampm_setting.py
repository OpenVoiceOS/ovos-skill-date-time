import unittest
import warnings

from ovos_bus_client.session import SessionManager
from ovos_utils.fakebus import FakeBus

from ovos_skill_date_time import TimeSkill


class TestAmpmSetting(unittest.TestCase):
    """AM/PM follows the session 12/24h setting, never the presence of a location."""

    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore")
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), "ovos-skill-date-time.openvoiceos")

    def test_12h_local_time_says_ampm(self):
        SessionManager.get().time_format = "half"
        self.assertFalse(self.skill.use_24hour)
        self.assertIn("a.m.", self.skill.get_spoken_time())
        self.assertIn("AM", self.skill.get_display_time())

    def test_24h_local_time_says_no_ampm(self):
        SessionManager.get().time_format = "full"
        self.assertTrue(self.skill.use_24hour)
        self.assertNotIn("a.m.", self.skill.get_spoken_time())
        self.assertNotIn("p.m.", self.skill.get_spoken_time())
        self.assertNotIn("AM", self.skill.get_display_time())
        self.assertNotIn("PM", self.skill.get_display_time())

    def test_24h_location_time_says_no_ampm(self):
        SessionManager.get().time_format = "full"
        self.assertNotIn("p.m.", self.skill.get_spoken_time("tokyo"))
        self.assertNotIn("PM", self.skill.get_display_time("tokyo"))

    def test_12h_location_time_says_ampm(self):
        SessionManager.get().time_format = "half"
        self.assertIn("p.m.", self.skill.get_spoken_time("tokyo"))
        self.assertIn("PM", self.skill.get_display_time("tokyo"))
