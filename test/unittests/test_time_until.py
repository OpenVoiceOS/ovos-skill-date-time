"""time_until answers both "how long until X" and "how many days between X and Y".

A request with two dates fills {start} and {end} and gets the calendar days
between them; a request with one date gets that date and its distance from
today. The handler is called directly with the slots already bound, so these
tests check the date arithmetic and the dialog choice, not intent routing
(the golden utterances cover routing). "Now" is pinned so the answers are
fixed.
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


class TestTimeUntil(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-between-")
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

    def _ask(self, from_date, to_date, lang="en-US"):
        """Ask for the days between two dates; return (dialog key, dialog data)."""
        return self._handle(Message("time_until", {"start": from_date,
                                                   "end": to_date}), lang)

    def _handle(self, message, lang="en-US"):
        """Run the handler and return (dialog key, dialog data)."""
        with mock.patch.object(self.skill, "get_datetime", return_value=NOW), \
                mock.patch.object(type(self.skill), "lang",
                                  new_callable=mock.PropertyMock,
                                  return_value=lang), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_time_until(message)
        speak.assert_called_once()
        key = speak.call_args.args[0]
        data = speak.call_args.args[1] if len(speak.call_args.args) > 1 else {}
        return key, data

    def test_days_between_two_dates(self):
        key, data = self._ask("march 1 2027", "june 5 2027")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["num_days"], "ninety six days")

    def test_order_does_not_matter(self):
        key, data = self._ask("june 5 2027", "march 1 2027")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["num_days"], "ninety six days")

    def test_reversed_pair_fills_the_earlier_date_first(self):
        # a directional template ("Fra {from_date} til {to_date}") must not
        # state the span backwards when the later date is spoken first
        _, forward = self._ask("march 1 2027", "june 5 2027")
        key, data = self._ask("june 5 2027", "march 1 2027")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["from_date"],
                         "monday, march first, twenty twenty seven")
        self.assertEqual(data["to_date"],
                         "saturday, june fifth, twenty twenty seven")
        self.assertEqual(data, forward)

    def test_across_new_year(self):
        key, data = self._ask("december 24 2026", "january 6 2027")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["num_days"], "thirteen days")

    def test_one_day_is_singular(self):
        key, data = self._ask("march 1 2027", "march 2 2027")
        self.assertEqual(data["num_days"], "one day")

    def test_same_day(self):
        key, data = self._ask("march 1 2027", "march 1 2027")
        self.assertEqual(key, "days_between_same")
        self.assertIn("date", data)

    def test_danish(self):
        key, data = self._ask("1. marts 2027", "5. juni 2027", lang="da-DK")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["num_days"], "seksoghalvfems dage")

    def test_unreadable_date_speaks_the_error(self):
        key, _ = self._ask("march 1 2027", "blorp")
        self.assertEqual(key, "extract_date_error")

    def test_missing_slot_speaks_the_error(self):
        key, _ = self._ask("march 1 2027", "")
        self.assertEqual(key, "extract_date_error")

    def test_both_phrasings_share_the_handler(self):
        # one date: the date and its distance from today
        message = Message("time_until", {"utterance": "how long until march 1 2027",
                                         "date": "march 1 2027"})
        with mock.patch.object(self.skill, "show_date"):
            key, data = self._handle(message)
        self.assertEqual(key, "date_relative_future")
        self.assertEqual(data["date"], "monday, march first, twenty twenty seven")
        # 2026-09-27 to 2027-03-01 by hand: 4 days to october 1, then 31 + 30 + 31 + 31 + 28
        self.assertEqual(data["num_days"].strip(), "one hundred and fifty five days")
        # two dates: the days between them
        key, data = self._ask("march 1 2027", "june 5 2027")
        self.assertEqual(key, "days_between")
        self.assertEqual(data["num_days"], "ninety six days")


if __name__ == "__main__":
    unittest.main()
