"""Dates and times the skill reads through chronologia, at a fixed "now".

Each expected value is counted on the calendar by hand from NOW, a Saturday.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import pytz
from ovos_bus_client.message import Message

SKILL_ID = "ovos-skill-date-time.openvoiceos"
ZONE = pytz.timezone("Europe/Copenhagen")
NOW = ZONE.localize(datetime(2026, 10, 17, 12, 0))  # a Saturday


class TestChronologiaReading(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._xdg = tempfile.TemporaryDirectory(prefix="date-time-chronologia-")
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

    def _patched(self, lang, now):
        return (mock.patch.object(self.skill, "get_datetime", return_value=now),
                mock.patch.object(type(self.skill), "lang", new_callable=mock.PropertyMock,
                                  return_value=lang))

    def _last_weekend(self, now):
        """The (saturday, sunday) dates the skill speaks for the last weekend."""
        clock, lang = self._patched("en-US", now)
        with clock, lang, mock.patch("ovos_skill_date_time.spoken_day_month",
                                     side_effect=lambda dt, lang: dt.date().isoformat()), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_date_last_weekend(Message("date_last_weekend", {}))
        data = speak.call_args.args[1]
        return data["saturday_date"], data["sunday_date"]

    def test_the_last_weekend_is_the_one_that_has_ended(self):
        for now, expected in (
                (NOW, ("2026-10-10", "2026-10-11")),
                (NOW + timedelta(days=1), ("2026-10-10", "2026-10-11")),
                (NOW + timedelta(days=2), ("2026-10-17", "2026-10-18")),
                (NOW + timedelta(days=6), ("2026-10-17", "2026-10-18"))):
            self.assertEqual(self._last_weekend(now), expected, now.strftime("%A"))

    def _future_time(self, utterance, now=NOW):
        clock, lang = self._patched("en-US", now)
        with clock, lang, mock.patch.object(self.skill, "speak_time") as speak, \
                mock.patch.object(self.skill, "get_response", return_value=None) as ask, \
                mock.patch.object(self.skill, "handle_query_time"):
            self.skill.handle_query_future_time(Message("what_time_will_it_be",
                                                        {"utterance": utterance}))
        ask.assert_not_called()
        return speak.call_args.kwargs["anchor_date"]

    def test_a_length_with_no_direction_word_is_counted_from_now(self):
        self.assertEqual(self._future_time("what time will it be if I wait two hours"),
                         NOW + timedelta(hours=2))

    def test_the_future_time_is_counted_from_the_session_clock(self):
        now = ZONE.localize(datetime(2017, 6, 27, 13, 4))
        self.assertEqual(self._future_time("what time will it be in three hours", now),
                         now + timedelta(hours=3))

    def test_the_day_said_beside_today_is_checked_against_today(self):
        clock, lang = self._patched("en-US", NOW)
        for utterance, expected in (("it's friday today, right", "weekday_matches_date_today_no"),
                                    ("it's saturday today, right", "weekday_matches_date_today_yes")):
            with clock, lang, mock.patch.object(self.skill, "speak_dialog") as speak:
                self.skill.handle_weekday(Message("weekday_for_date", {"utterance": utterance}))
            self.assertEqual(speak.call_args.args[0], expected, utterance)

    def test_a_date_with_slashes_is_the_date_until_which_days_are_counted(self):
        clock, lang = self._patched("en-US", NOW)
        with clock, lang, mock.patch("ovos_skill_date_time.spoken_date",
                                     side_effect=lambda dt, lang: dt.date().isoformat()), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_time_until(Message("time_until",
                                                 {"utterance": "how many days until 12/25/2026"}))
        key, data = speak.call_args.args
        self.assertEqual(key, "date_relative_future")
        self.assertEqual(data["date"], "2026-12-25")

    def test_the_days_until_a_date_said_with_until(self):
        clock, lang = self._patched("hu-HU", NOW)
        with clock, lang, mock.patch("ovos_skill_date_time.spoken_date",
                                     side_effect=lambda dt, lang: dt.date().isoformat()), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            self.skill.handle_time_until(Message("time_until",
                                                 {"utterance": "hány nap van még október 31-ig"}))
        key, data = speak.call_args.args
        self.assertEqual(key, "date_relative_future")
        self.assertEqual(data["date"], "2026-10-31")

    def test_the_date_an_until_phrase_names(self):
        for lang, text in (("fi-FI", "1. tammikuuta asti"), ("hu-HU", "január 1-ig")):
            clock, patched_lang = self._patched(lang, NOW)
            with clock, patched_lang:
                found = self.skill._parse_date(text, NOW)
            self.assertEqual(found.replace(tzinfo=None), datetime(2027, 1, 1), (lang, text))

    def test_a_date_in_another_season_takes_the_offset_of_its_own_date(self):
        # Copenhagen keeps CEST (+02:00) on 17 October and CET (+01:00) on 1 January
        clock, lang = self._patched("en-US", NOW)
        with clock, lang:
            found = self.skill._parse_date("january 1", NOW)
        self.assertEqual(found.utcoffset(), timedelta(hours=1))
        self.assertEqual(found.replace(tzinfo=None), datetime(2027, 1, 1))
        self.assertEqual(NOW.utcoffset(), timedelta(hours=2))

    def test_a_clock_in_a_named_zone_is_converted_to_the_session_zone(self):
        # 15:00 UTC on 17 October is 17:00 in Copenhagen (CEST, +02:00)
        for lang, utterance in (("fr-FR", "quelle heure sera-t-il à 15 heures UTC"),
                                ("pt-PT", "que horas serão às 15 horas UTC")):
            clock, patched_lang = self._patched(lang, NOW)
            with clock, patched_lang, mock.patch.object(self.skill, "speak_time") as speak, \
                    mock.patch.object(self.skill, "get_response", return_value=None), \
                    mock.patch.object(self.skill, "handle_query_time"):
                self.skill.handle_query_future_time(Message("what_time_will_it_be",
                                                            {"utterance": utterance}))
            found = speak.call_args.kwargs["anchor_date"]
            self.assertEqual(found, pytz.utc.localize(datetime(2026, 10, 17, 15)), utterance)
            self.assertEqual(found.replace(tzinfo=None), datetime(2026, 10, 17, 17), utterance)

    def _spoken_date(self, handler, intent, utterance):
        """The dialog and its data, with each date spoken as its ISO instant."""
        clock, lang = self._patched("en-US", NOW)
        with clock, lang, mock.patch("ovos_skill_date_time.spoken_date",
                                     side_effect=lambda dt, lang, **_: dt.isoformat()), \
                mock.patch.object(self.skill, "speak_dialog") as speak:
            handler(Message(intent, {"utterance": utterance}))
        return speak.call_args.args

    def test_the_days_until_a_clock_in_a_named_zone(self):
        # 09:00 UTC on 25 December is 10:00 in Copenhagen (CET, +01:00)
        key, data = self._spoken_date(self.skill.handle_time_until, "time_until",
                                      "how many days until december 25 at 9 am utc")
        self.assertEqual(key, "date_relative_future")
        self.assertEqual(data["date"], "2026-12-25T10:00:00+01:00")

    def test_a_past_weekday_at_a_clock_in_a_named_zone(self):
        # the Friday before Saturday 17 October is 16 October; 09:00 GMT is 11:00 CEST
        key, data = self._spoken_date(self.skill.handle_query_date, "date",
                                      "what date was friday at 9 am gmt")
        self.assertEqual(key, "date")
        self.assertEqual(data["date"], "2026-10-16T11:00:00+02:00")

    def test_a_past_calendar_date_is_its_last_occurrence(self):
        # 15 May 2026 lies before Saturday 17 October 2026; 15 May 2027 lies after it
        for utterance, expected in (("what was the date on may 15", "2026-05-15T00:00:00+02:00"),
                                    ("what is the date on may 15", "2027-05-15T00:00:00+02:00")):
            key, data = self._spoken_date(self.skill.handle_query_date, "date", utterance)
            self.assertEqual(data["date"], expected, utterance)


if __name__ == "__main__":
    unittest.main()
