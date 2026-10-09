"""what_day_is_it answers a day request and a date request with the full date.

"what day is it" and "what date is it" route to one intent. The handler speaks
the ``date`` dialog with the weekday, the day, the month and the year of today,
whatever date words the request holds. A language without a date format gets
the day through the ``day_current`` dialog. The handler is called directly, so these tests check the answer, not intent
routing (the golden utterances cover routing). "Now" is pinned so the answer
is fixed.
"""
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import pytz
from ovos_bus_client.message import Message

SKILL_ID = "ovos-skill-date-time.openvoiceos"
NOW = pytz.timezone("Europe/Copenhagen").localize(datetime(2026, 9, 27, 12, 0))


class TestCurrentDay(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-day-")
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

    def _ask(self, utterance, lang="en-US"):
        """Run the handler and return (dialog key, dialog data)."""
        message = Message("what_day_is_it", {"utterance": utterance})
        with mock.patch.object(self.skill, "get_datetime", return_value=NOW), \
                mock.patch.object(type(self.skill), "lang",
                                  new_callable=mock.PropertyMock,
                                  return_value=lang), \
                mock.patch.object(self.skill, "show_date"), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_current_day(message)
        speak.assert_called_once()
        return speak.call_args.args[0], speak.call_args.args[1]

    def test_day_and_date_requests_get_the_weekday_and_the_date(self):
        # 2026-09-27 is a Sunday
        for utterance in ("what day is it", "what date is it"):
            key, data = self._ask(utterance)
            self.assertEqual(key, "date", utterance)
            self.assertEqual(data["date"],
                             "sunday, september twenty-seventh, twenty twenty six",
                             utterance)

    def test_a_day_word_in_the_request_is_not_an_offset(self):
        # the date parser reads "ein Tag" as one day from now; the answer
        # must still be Sunday the 27th, not Monday the 28th
        key, data = self._ask("was ist heute für ein Tag", lang="de-DE")
        self.assertEqual(key, "date")
        self.assertTrue(data["date"].startswith("Sonntag"), data)
        self.assertIn("September", data["date"])

    def test_a_language_without_a_date_format_gets_the_day(self):
        # ovos-date-parser formats no tr date; the day_current answer stays
        key, data = self._ask("bugün günlerden ne", lang="tr-TR")
        self.assertEqual(key, "day_current")
        self.assertEqual(data["day"], "27 September")


if __name__ == "__main__":
    unittest.main()
