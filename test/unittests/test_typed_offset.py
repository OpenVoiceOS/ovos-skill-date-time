"""what_time_will_it_be takes a typed slot {number:offset} (OVOS-INTENT-1 5.6).

The binding test asserts the bound SURFACE, never the match. On an engine
that does not honour the typed-slot map, `{number:offset}` behaves as
`{offset}` and the template binds every word between "in" and "minutes", so
"like ten" is bound; an engine that honours the map binds the span the map
lists, "ten". Both engines match the intent, so only the surface is evidence.
The engine is probed with a control sentence first and named in the result.
"""
import glob
import unittest
from os.path import dirname, join
from unittest import mock

from ovos_bus_client.message import Message
from ovos_spec_tools import declared_slot_types
from ovos_spec_tools.expansion import expand
from ovos_utils.fakebus import FakeBus

ROOT = dirname(dirname(dirname(__file__)))
LANG = "en-US"
SKILL_ID = "ovos-skill-date-time.openvoiceos"
UTTERANCE = "what time will it be in like ten minutes"


def _typed(utterance, surface, value):
    start = utterance.index(surface)
    return {"number": [{"span": [start, start + len(surface)],
                        "surface": surface, "value": value}]}


def _bound(samples, utterance, surface, value, slot):
    """The surface padatious binds for `slot`, with a map listing `surface`."""
    from ovos_padatious.opm import PadatiousPipeline
    pipeline = PadatiousPipeline(FakeBus(), {"instant_train": True})
    data = {"name": f"{SKILL_ID}:what_time_will_it_be", "skill_id": SKILL_ID,
            "lang": LANG, "samples": [s for t in samples for s in expand(t)],
            "slot_types": declared_slot_types(samples)}
    pipeline.register_intent(Message("padatious:register_intent", data,
                                     {"skill_id": SKILL_ID}))
    pipeline.train(Message("mycroft.skills.train", {}, {}))
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": LANG,
                       "typed_slots": _typed(utterance, surface, value)}, {})
    match = pipeline.match_high([utterance], LANG, message)
    return None if match is None else match.match_data.get(slot)


def _engine():
    """'honouring' or 'degrading', from the typed-slots campaign control:
    `set a timer for {number:amount} minutes` binds "twenty" only on an
    engine that uses the map, "about twenty" on one that does not."""
    from importlib.metadata import version
    got = _bound(["set a timer for {number:amount} minutes",
                  "timer {number:amount} minutes"],
                 "set a timer for about twenty minutes", "twenty", 20, "amount")
    kind = {"twenty": "honouring", "about twenty": "degrading"}.get(got)
    return kind, f"ovos-padatious {version('ovos-padatious')} ({kind}, control bound {got!r})"


class TestOffsetIsTyped(unittest.TestCase):

    def test_every_locale_declares_offset_as_number(self):
        for path in sorted(glob.glob(join(ROOT, "locale", "*", "intents",
                                          "what_time_will_it_be.intent"))):
            text = open(path, encoding="utf-8").read()
            self.assertNotIn("{offset}", text, path)
        self.assertEqual(glob.glob(join(ROOT, "locale", "*", "offset.entity")), [])

    def test_the_bound_surface_of_a_hedged_number(self):
        with open(join(ROOT, "locale", LANG, "intents",
                       "what_time_will_it_be.intent"), encoding="utf-8") as f:
            samples = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertEqual(declared_slot_types(samples).get("offset"), "number")
        kind, engine = _engine()
        self.assertIn(kind, ("honouring", "degrading"), engine)
        bound = _bound(samples, UTTERANCE, "ten", 10, "offset")
        expected = "ten" if kind == "honouring" else "like ten"
        print(f"engine: {engine}; {UTTERANCE!r} bound offset={bound!r}")
        self.assertEqual(bound, expected, f"engine: {engine}")


class TestHandlerReadsTheTypedSlot(unittest.TestCase):

    def setUp(self):
        from ovos_skill_date_time import TimeSkill
        self.skill = TimeSkill()
        self.skill._startup(FakeBus(), SKILL_ID)
        self.message = Message(f"{SKILL_ID}:what_time_will_it_be",
                               {"utterance": UTTERANCE, "offset": "ten",
                                "lang": LANG}, {})

    def test_no_typed_value_asks_for_the_offset(self):
        with mock.patch.object(self.skill, "typed_slot", return_value=None), \
                mock.patch.object(self.skill, "get_response", return_value=None) as ask, \
                mock.patch.object(self.skill, "speak_time") as speak:
            self.skill.handle_query_future_time(self.message)
        ask.assert_called_once_with("ask_offset")
        speak.assert_not_called()

    def test_an_answer_to_the_prompt_is_parsed(self):
        with mock.patch.object(self.skill, "typed_slot", return_value=None), \
                mock.patch.object(self.skill, "get_response", return_value="in ten minutes"), \
                mock.patch.object(self.skill, "_resolve_location", return_value=None), \
                mock.patch.object(self.skill, "speak_time") as speak:
            self.skill.handle_query_future_time(self.message)
        speak.assert_called_once()
        self.assertEqual(speak.call_args.args[0], "time_future")

    def test_a_typed_value_does_not_ask(self):
        with mock.patch.object(self.skill, "typed_slot", return_value=10), \
                mock.patch.object(self.skill, "get_response") as ask, \
                mock.patch.object(self.skill, "_resolve_location", return_value=None), \
                mock.patch.object(self.skill, "speak_time") as speak:
            self.skill.handle_query_future_time(self.message)
        ask.assert_not_called()
        self.assertEqual(speak.call_args.args[0], "time_future")
