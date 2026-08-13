"""Entity-file registration coverage for ovos-skill-date-time (en-US).

register_entity_file() feeds the values shipped under locale/en-US/*.entity
to the intent engine as TRAINING DATA / confidence hints for the
{location}/{date}/{weekday}/{offset} slots. This does NOT limit what a slot
can capture -- any word can still fill a slot, by design. What it changes is
confidence: an utterance whose slot value is a known entity scores higher
(padacioso boosts a recognized value to conf 1.0) than the same template
with an arbitrary word (typically ~0.9-0.96 depending on slot count), and
that shift CAN move a query across the padacioso "high" band threshold
(conf_high = 0.95), though the effect is not guaranteed to be positive for
every template -- with the full, realistically-sized locale/en-US/*.entity
lists (dozens to ~100 values), a recognized value does not reliably hit
1.0 the way a toy 1-2 item entity list does; the exact score padacioso
assigns depends on entity-list size and the number of competing samples.
This suite therefore only asserts what is reliably true: a valid entity
value still routes and gets the slot tagged correctly. It intentionally
does NOT assert that registration guarantees a specific confidence
delta -- that would overclaim what a "training hint" does.

Run: pytest test/end2end/test_entity_constraints.py -v --timeout=120
"""
import time
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"

# HIGH band only (padacioso conf_high threshold 0.95) -- this isolates the
# confidence-bias effect of entity registration from the medium/low fuzzy
# bands, which accept any slot value regardless of registration.
PIPELINE = ["ovos-padacioso-pipeline-plugin-high"]


class TestEntityConstraints(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=150)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _emit_and_wait(self, utterance, intent_msg_type, deadline_s=20, settle_s=4):
        matched = []
        handler = lambda msg: matched.append(msg)
        self.minicroft.bus.on(intent_msg_type, handler)
        try:
            session = Session(f"e2e-entity-{hash((utterance, intent_msg_type))}")
            session.lang = LANG
            session.pipeline = PIPELINE
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            )
            deadline = time.monotonic() + deadline_s
            while not matched and time.monotonic() < deadline:
                self.minicroft.bus.emit(message)
                waited = time.monotonic() + settle_s
                while not matched and time.monotonic() < waited:
                    time.sleep(0.2)
        finally:
            self.minicroft.bus.remove(intent_msg_type, handler)
        return matched

    def _assert_match(self, utterance, intent_file, slot=None, slot_value=None):
        intent_name = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
        intent_msg_type = f"{SKILL_ID}:{intent_name}"
        matched = self._emit_and_wait(utterance, intent_msg_type)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to {intent_file} at high confidence "
            f"(padacioso conf_high=0.95) -- registered entity values should "
            f"score high enough to clear this band",
        )
        if slot is not None:
            # padacioso lowercases matched slot text; compare case-insensitively
            got = matched[0].data.get(slot)
            self.assertEqual(
                (got or "").lower(), (slot_value or "").lower(),
                f"{utterance!r} matched {intent_file} but slot {slot!r} was "
                f"{matched[0].data.get(slot)!r}, expected {slot_value!r}",
            )

    # --- {location} on what.time.is.it.intent ---
    def test_location_valid_matches(self):
        self._assert_match(
            "current time in Tokyo", "what.time.is.it.intent",
            slot="location", slot_value="Tokyo",
        )

    # --- {offset} on what.time.will.it.be.intent ---
    def test_offset_valid_matches(self):
        self._assert_match(
            "in five hour from now what time will it be",
            "what.time.will.it.be.intent",
        )

    # NOTE: unregistered/unlisted slot values remain matchable by design --
    # entity files are training hints, not an allow-list. E.g. "current time
    # in Zzyzxvania" and "in bananas hour from now what time will it be"
    # still route (at a lower, non-boosted confidence) both with and without
    # registration. That is correct behavior for an open-vocabulary slot and
    # is intentionally NOT asserted against here.
