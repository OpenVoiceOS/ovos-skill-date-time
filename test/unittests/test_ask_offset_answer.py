"""The answer to the ask_offset prompt is a length of time.

what_time_will_it_be asks "In how many minutes or hours?" (cs "Za kolik
minut nebo hodin?") when the utterance holds no offset. The answer is a
length, such as "half an hour" or "2 hodiny". A length alone is not a date,
so the handler reads the answer as a duration from now first, and as a date
only when it holds no duration. The expected time is now plus the length the
answer names, counted by hand.
"""
import datetime
import unittest
from unittest import mock

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

SKILL_ID = "ovos-skill-date-time.openvoiceos"


class TestAnswerToTheOffsetPrompt(unittest.TestCase):

    def setUp(self):
        from ovos_skill_date_time import TimeSkill
        self.skill_class = TimeSkill
        self.skill = TimeSkill()
        self.skill._startup(FakeBus(), SKILL_ID)

    def _future_time(self, lang, utterance, answer):
        """The anchor the handler speaks, and the instants around the call."""
        message = Message(f"{SKILL_ID}:what_time_will_it_be",
                          {"utterance": utterance, "lang": lang}, {})
        with mock.patch.object(self.skill_class, "lang",
                               new_callable=mock.PropertyMock,
                               return_value=lang), \
                mock.patch.object(self.skill, "typed_slot", return_value=None), \
                mock.patch.object(self.skill, "get_response",
                                  return_value=answer) as ask, \
                mock.patch.object(self.skill, "_resolve_location", return_value=None), \
                mock.patch.object(self.skill, "speak_time") as speak:
            before = datetime.datetime.now(datetime.timezone.utc)
            self.skill.handle_query_future_time(message)
            after = datetime.datetime.now(datetime.timezone.utc)
        ask.assert_called_once_with("ask_offset")
        speak.assert_called_once()
        self.assertEqual(speak.call_args.args[0], "time_future")
        return speak.call_args.kwargs["anchor_date"], before, after

    def assert_now_plus(self, lang, utterance, answer, length):
        spoken, before, after = self._future_time(lang, utterance, answer)
        self.assertIsNotNone(spoken.tzinfo, spoken)
        self.assertGreaterEqual(spoken, before + length - datetime.timedelta(seconds=1))
        self.assertLessEqual(spoken, after + length + datetime.timedelta(seconds=1))

    def test_en_half_an_hour(self):
        self.assert_now_plus("en-US", "what time will it be", "half an hour",
                             datetime.timedelta(minutes=30))

    def test_en_ten_minutes(self):
        self.assert_now_plus("en-US", "what time will it be", "ten minutes",
                             datetime.timedelta(minutes=10))

    def test_en_two_hours(self):
        self.assert_now_plus("en-US", "what time will it be", "2 hours",
                             datetime.timedelta(hours=2))

    def test_cs_two_hours(self):
        self.assert_now_plus("cs-CZ", "jaký bude čas", "2 hodiny",
                             datetime.timedelta(hours=2))

    def test_cs_ten_minutes(self):
        self.assert_now_plus("cs-CZ", "jaký bude čas", "10 minut",
                             datetime.timedelta(minutes=10))

    def test_cs_half_an_hour(self):
        self.assert_now_plus("cs-CZ", "jaký bude čas", "půl hodiny",
                             datetime.timedelta(minutes=30))

    def test_an_answer_with_no_duration_is_read_as_a_date(self):
        """A date answer still reaches extract_datetime."""
        spoken, before, _ = self._future_time("en-US", "what time will it be",
                                              "tomorrow")
        self.assertEqual(spoken.date(),
                         (before.astimezone(spoken.tzinfo)
                          + datetime.timedelta(days=1)).date())


    def test_a_zero_length_is_now(self):
        """A zero length is a length, not midnight."""
        self.assert_now_plus("en-US", "what time will it be", "0 minutes",
                             datetime.timedelta(0))

    def test_an_answer_the_normalizer_empties_speaks_the_time(self):
        """"?" normalizes to "", where extract_duration returns a bare None;
        the handler falls back to the current time instead of raising."""
        message = Message(f"{SKILL_ID}:what_time_will_it_be",
                          {"utterance": "what time will it be", "lang": "en-US"}, {})
        with mock.patch.object(self.skill_class, "lang",
                               new_callable=mock.PropertyMock,
                               return_value="en-US"), \
                mock.patch.object(self.skill, "typed_slot", return_value=None), \
                mock.patch.object(self.skill, "get_response", return_value="?"), \
                mock.patch.object(self.skill, "handle_query_time") as now_time:
            self.skill.handle_query_future_time(message)
        now_time.assert_called_once()

if __name__ == "__main__":
    unittest.main()
