"""End-to-end intent-routing test for ovos-skill-date-time (it-IT).

Covers the offset query "che ora sarà tra {number:offset} minuti". The slot is
typed (OVOS-INTENT-1 5.6); there is no offset.entity.

Run: pytest test/end2end/ -v
"""
from unittest import TestCase

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "it-IT"


class TestIntentRoutingItIt(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], max_wait=150, lang=LANG)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _assert_intent(self, utterance: str, intent_file: str):
        session = Session(f"e2e-it_it-{intent_file}-{hash(utterance)}")
        session.lang = LANG
        session.pipeline = PIPELINE
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        )
        capture = CaptureSession(self.minicroft,
                                 eof_msgs=["mycroft.skill.handler.start"])
        capture.capture(message, timeout=30)
        TALLY.assert_routed(utterance, f"{SKILL_ID}:{intent_file}",
                            [m.msg_type for m in capture.finish()])

    # --- what_time_will_it_be.intent ---
    def test_che_ora_sara_tra_10_minuti(self):
        self._assert_intent(
            "che ora sarà tra 10 minuti", "what_time_will_it_be.intent"
        )
