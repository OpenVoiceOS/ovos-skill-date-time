"""Holiday names in date questions ("when is christmas", "hvornår er det jul",
"how many days until easter") and the two holiday intents.

ovos-date-parser does not know holiday names, so these questions used to
fall back to "now" and were answered with today's date. The handlers are
called directly with "now" pinned; the golden utterances cover routing.
"""
import os
import tempfile
import unittest
from datetime import date, datetime
from unittest import mock

import pytz
from ovos_bus_client.message import Message

SKILL_ID = "ovos-skill-date-time.openvoiceos"
NOW = pytz.timezone("Europe/Copenhagen").localize(datetime(2026, 10, 1, 9, 0))


class TestHolidayLookup(unittest.TestCase):

    def setUp(self):
        from ovos_skill_date_time.holidays_lookup import find_holiday
        self.find = find_holiday

    def test_spoken_names(self):
        today = date(2026, 10, 1)
        self.assertEqual(self.find("when is christmas", "en-US", today, "US"),
                         ("Christmas Day", date(2026, 12, 25)))
        self.assertEqual(self.find("how many days until easter", "en-US", today, "US")[1],
                         date(2027, 3, 28))
        self.assertEqual(self.find("hvornår er det jul", "da-DK", today, "DK"),
                         ("Juledag", date(2026, 12, 25)))
        self.assertEqual(self.find("wann ist weihnachten", "de-DE", today, "DE")[1], date(2026, 12, 25))

    def test_the_librarys_own_name(self):
        """not in holidays.json, said by its official name"""
        self.assertEqual(self.find("hvornår er grundlovsdag", "da-DK", date(2026, 10, 1), "DK"),
                         ("Grundlovsdag", date(2027, 6, 5)))

    def test_language_region_when_the_location_country_lacks_it(self):
        """a Danish device in the US still knows "jul"; an English one in Denmark "christmas" """
        self.assertEqual(self.find("hvornår er det jul", "da-DK", date(2026, 10, 1), "US")[1],
                         date(2026, 12, 25))
        self.assertEqual(self.find("when is christmas", "en-US", date(2026, 10, 1), "DK")[1],
                         date(2026, 12, 25))

    def test_accents_do_not_matter(self):
        """the intent parser hands over "noel" / "paske" as the {date} slot"""
        self.assertEqual(self.find("noel", "fr-FR", date(2026, 10, 1), "FR")[1], date(2026, 12, 25))
        self.assertEqual(self.find("paske", "da-DK", date(2026, 10, 1), "DK")[1], date(2027, 3, 28))

    def test_not_a_holiday(self):
        for text in ("when is my birthday", "when is friday", "what time is it", "how many days until june 3rd"):
            self.assertIsNone(self.find(text, "en-US", date(2026, 10, 1), "US"), text)


class TestHolidayHandlers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-holidays-")
        cls._saved = {}
        for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME",
                    "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            cls._saved[var] = os.environ.get(var)
            os.environ[var] = os.path.join(cls._xdg.name, var.lower())

        from ovos_skill_date_time import TimeSkill
        from ovos_utils.messagebus import FakeBus

        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), SKILL_ID)

    @classmethod
    def tearDownClass(cls):
        cls.skill.shutdown()
        for var, value in cls._saved.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        cls._xdg.cleanup()

    def _run(self, handler, data, now=NOW, country="DK", lang="en-US"):
        spoken = []
        with mock.patch.object(type(self.skill), "lang", new_callable=mock.PropertyMock,
                               return_value=lang), \
                mock.patch.object(self.skill, "get_datetime", return_value=now), \
                mock.patch.object(self.skill, "_holiday_country", return_value=country), \
                mock.patch.object(self.skill, "speak_dialog",
                                  side_effect=lambda key, data=None, **kw: spoken.append((key, data))), \
                mock.patch.object(self.skill, "show_date"):
            handler(Message("test", data))
        return spoken

    def test_when_is_christmas_is_christmas_not_today(self):
        [(key, data)] = self._run(self.skill.handle_time_until, {"utterance": "when is christmas"})
        self.assertEqual(key, "date_relative_future")
        self.assertIn("december", data["date"].lower())
        self.assertIn("days", data["num_days"])

    def test_weekday_of_a_holiday(self):
        [(key, data)] = self._run(self.skill.handle_weekday,
                                  {"utterance": "what day of the week is christmas", "date": "christmas"})
        self.assertEqual(key, "weekday_at_date_future")
        self.assertEqual(data["weekday"].lower(), "friday")

    def test_days_between_holidays(self):
        [(key, data)] = self._run(self.skill.handle_days_between,
                                  {"start": "christmas", "end": "new year"})
        self.assertEqual(key, "days_between")
        self.assertTrue(data["num_days"].startswith("seven days") or "7" in data["num_days"],
                        data["num_days"])

    def test_is_holiday_today(self):
        christmas = NOW.replace(month=12, day=25)
        self.assertEqual(self._run(self.skill.handle_is_holiday_today, {}, now=christmas, lang="da-DK"),
                         [("holiday_today", {"holiday": "Juledag"})])
        self.assertEqual(self._run(self.skill.handle_is_holiday_today, {}, lang="da-DK"),
                         [("holiday_not_today", None)])

    def test_next_holiday(self):
        [(key, data)] = self._run(self.skill.handle_next_holiday, {}, lang="da-DK")
        self.assertEqual(key, "next_holiday")
        self.assertEqual(data["holiday"], "Juleaftensdag")


if __name__ == "__main__":
    unittest.main()
