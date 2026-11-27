"""A comma after the time must not change the time the handler reads.

"mañana a las 8, por favor" names tomorrow at 08:00. With the comma glued to
the hour, older date parsers read tomorrow at 00:00. The expected instant is
tomorrow's date at 08:00, counted by hand.
"""
import datetime
import unittest
from unittest import mock

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus
from ovos_utils.time import now_local

SKILL_ID = "ovos-skill-date-time.openvoiceos"


class TestFutureTimeWithPunctuation(unittest.TestCase):

    def setUp(self):
        from ovos_skill_date_time import TimeSkill
        self.skill_class = TimeSkill
        self.skill = TimeSkill()
        self.skill._startup(FakeBus(), SKILL_ID)

    def _spoken(self, lang, utterance):
        message = Message(f"{SKILL_ID}:what_time_will_it_be",
                          {"utterance": utterance, "lang": lang}, {})
        with mock.patch.object(self.skill_class, "lang",
                               new_callable=mock.PropertyMock,
                               return_value=lang), \
                mock.patch.object(self.skill, "typed_slot", return_value=None), \
                mock.patch.object(self.skill, "_resolve_location", return_value=None), \
                mock.patch.object(self.skill, "speak_time") as speak:
            today = now_local().date()
            self.skill.handle_query_future_time(message)
        speak.assert_called_once()
        self.assertEqual(speak.call_args.args[0], "time_future")
        return speak.call_args.kwargs["anchor_date"], today

    def test_es_tomorrow_at_eight_with_comma(self):
        spoken, today = self._spoken(
            "es-ES", "qué hora será mañana a las 8, por favor")
        tomorrow = today + datetime.timedelta(days=1)
        self.assertEqual((spoken.date(), spoken.hour, spoken.minute),
                         (tomorrow, 8, 0))
