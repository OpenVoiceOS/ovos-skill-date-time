"""End-to-end intent-routing AND effect tests for ovos-skill-date-time (en-US).

Each routing case feeds an utterance through a MiniCroft stack and asserts it
routes to the expected ``.intent`` handler. Coverage spans the current-time
query (bare and with a ``{location}`` slot) and the current-date/day/month/
year queries.

The effect tests below go further: routing alone passes even when a handler
speaks the wrong dialog, speaks nothing, or speaks an untranslated key. Each
effect test freezes the wall clock, pins the session timezone explicitly,
computes the expected spoken line independently (from the shipped
``.dialog`` template plus a value computed by ``ovos_date_parser`` against
the frozen, pinned-timezone datetime -- never read back from the skill's own
speak call), and asserts the handler actually said that line.

Run: pytest test/end2end/ -v
"""
import datetime
from pathlib import Path
from unittest import TestCase, mock

import pytz
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_date_parser import nice_date, nice_month, nice_time, nice_year
from ovoscope import CaptureSession
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"
LOCALE_EN_US = Path(__file__).parent.parent.parent / "locale" / "en-US" / "dialog"

# Every effect test pins this timezone on the Session explicitly, rather than
# inheriting whatever timezone the test machine happens to run in. Pinned
# because a user near midnight can be on a different date in another zone,
# and because the frozen instant below is deliberately not near a US/Eastern
# DST boundary (2024-03-15, after the 2024-03-10 spring-forward) so the
# local offset is unambiguous.
PINNED_TZ = "America/New_York"
FROZEN_UTC = datetime.datetime(2024, 3, 15, 16, 30, 0, tzinfo=pytz.UTC)


def _frozen_now_local(tz: datetime.tzinfo = None) -> datetime.datetime:
    """Stand-in for ``ovos_utils.time.now_local`` used by every effect test.

    Always returns the same frozen instant, converted into whatever timezone
    the skill asks for. This removes the race between "now" as computed by
    the test and "now" as computed a few milliseconds later by the skill.
    """
    tz = tz or pytz.timezone(PINNED_TZ)
    return FROZEN_UTC.astimezone(tz)


def _dialog_lines(name: str) -> list:
    """Read a dialog file's template lines directly from disk.

    Independent of the skill handler under test: this never reads back
    anything the handler spoke, only what is shipped on the filesystem.
    """
    path = LOCALE_EN_US / f"{name}.dialog"
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _rendered_lines(dialog_name: str, slot: str, value: str) -> set:
    """Substitute ``value`` for ``{slot}`` in every line of a dialog file.

    Produces the set of exact strings the handler is allowed to have
    spoken for this intent, given this independently-computed value.
    """
    return {line.replace("{%s}" % slot, value) for line in _dialog_lines(dialog_name)}


# The local datetime the frozen clock resolves to under the pinned timezone,
# computed once so every expected value below derives from the SAME anchor.
_LOCAL_DT = FROZEN_UTC.astimezone(pytz.timezone(PINNED_TZ))

# Expected values, one per intent, each computed by ovos_date_parser against
# the frozen/pinned datetime with the exact arguments the handler itself
# passes (see __init__.py: handle_query_time -> nice_time(..., use_24hour=
# False, use_ampm=True) when no location slot; handle_current_day ->
# nice_date(dt, lang);
# handle_current_month -> nice_month(now, lang); handle_current_year ->
# nice_year(now, lang)). Using the same well-tested formatting library the
# skill imports still verifies what the *skill* does on its own: that it
# freezes/derives the right anchor datetime, resolves the right session
# timezone, calls the right formatter, and speaks the right dialog file --
# a handler that used the wrong anchor, the wrong timezone, or the wrong
# dialog family fails these checks even though ovos_date_parser itself is
# never in question.
_EFFECTS = {
    "what_time_is_it.intent": {
        "dialog": "time_current",
        "slot": "time",
        # The 12-hour clock speaks the meridiem: dev's own
        # test_12h_local_time_says_ampm asserts "a.m." is in the spoken time,
        # and this row is the same clock at 12:30 in the afternoon.
        "value": nice_time(_LOCAL_DT, lang=LANG, speech=True, use_24hour=False, use_ampm=True),
    },
    "what_day_is_it.intent": {
        "dialog": "date",
        "slot": "date",
        "value": nice_date(_LOCAL_DT, lang=LANG),
    },
    "what_month_is_it.intent": {
        "dialog": "month_current",
        "slot": "month",
        "value": nice_month(_LOCAL_DT, lang=LANG),
    },
    "what_year_is_it.intent": {
        "dialog": "year_current",
        "slot": "year",
        "value": nice_year(_LOCAL_DT, lang=LANG),
    },
}

_RENDERED = {
    intent: _rendered_lines(spec["dialog"], spec["slot"], spec["value"])
    for intent, spec in _EFFECTS.items()
}


class TestExpectedLinesDisjoint(TestCase):
    """The five effect fixtures above must never overlap.

    Guards against the effect tests silently degrading into routing tests:
    if two intents' rendered expected lines shared a member, a handler that
    spoke the WRONG one of the two dialogs would still pass its effect
    check. No MiniCroft boot needed; this only reads dialog templates plus
    the values computed above.
    """

    def test_pairwise_disjoint(self):
        intents = list(_RENDERED)
        for i, left in enumerate(intents):
            for right in intents[i + 1:]:
                overlap = _RENDERED[left] & _RENDERED[right]
                self.assertFalse(
                    overlap,
                    f"{left} and {right} expected lines overlap: {overlap!r}",
                )


class TestIntentRouting(TestCase):
    """Shared MiniCroft boot for all intent-routing and effect checks."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG, max_wait=150)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _fire(self, utterance: str, session: Session):
        session.lang = LANG
        session.pipeline = PIPELINE
        message = Message(
            "recognizer_loop:utterance",
            {"utterances": [utterance], "lang": LANG},
            {"session": session.serialize()},
        )
        capture = CaptureSession(self.minicroft,
                                 eof_msgs=["ovos.utterance.handled"])
        capture.capture(message, timeout=30)
        return capture.finish()

    def _assert_intent(self, utterance: str, intent_file: str):
        session = Session(f"e2e-en_us-{intent_file}-{hash(utterance)}")
        messages = self._fire(utterance, session)
        TALLY.assert_routed(utterance, f"{SKILL_ID}:{intent_file}",
                            [m.msg_type for m in messages])

    def _assert_effect(self, utterance: str, intent_file: str):
        """Assert routing AND that the frozen, pinned-timezone value was spoken."""
        session = Session(f"e2e-en_us-effect-{intent_file}-{hash(utterance)}")
        # Session.timezone (OVOS-SESSION-1 §3.5) is a read-only view over
        # session.location['tz']; that key is the one to set explicitly.
        session.location["tz"] = PINNED_TZ
        with mock.patch("ovos_skill_date_time.now_local", side_effect=_frozen_now_local):
            messages = self._fire(utterance, session)
        TALLY.assert_routed(utterance, f"{SKILL_ID}:{intent_file}",
                            [m.msg_type for m in messages])
        spoken = [m.data.get("utterance", "") for m in messages
                  if m.msg_type in ("speak", "ovos.utterance.speak")]
        self.assertTrue(spoken, f"expected a spoken response for {utterance!r}")
        expected_lines = _RENDERED[intent_file]
        self.assertTrue(
            any(utt in expected_lines for utt in spoken),
            f"expected one of {expected_lines!r} to be spoken for {utterance!r} "
            f"(frozen {_LOCAL_DT.isoformat()} in {PINNED_TZ}), got {spoken!r}",
        )

    # --- what_time_is_it.intent ---
    def test_what_time_is_it(self):
        self._assert_intent("what time is it", "what_time_is_it.intent")

    def test_whats_the_time(self):
        self._assert_intent("what's the time now", "what_time_is_it.intent")

    def test_what_time_is_it_in_location(self):
        self._assert_intent("current time in tokyo", "what_time_is_it.intent")

    def test_what_time_is_it_effect(self):
        self._assert_effect("what time is it", "what_time_is_it.intent")

    # --- what_day_is_it.intent: day and date requests share one intent ---
    def test_what_date_is_it(self):
        self._assert_intent("what date is it", "what_day_is_it.intent")

    def test_tell_me_the_date(self):
        self._assert_intent("tell me the date", "what_day_is_it.intent")

    def test_what_date_is_it_effect(self):
        self._assert_effect("what date is it", "what_day_is_it.intent")

    def test_what_day_is_it(self):
        self._assert_intent("what day is it", "what_day_is_it.intent")

    def test_what_day_is_it_effect(self):
        self._assert_effect("what day is it", "what_day_is_it.intent")

    # --- what_month_is_it.intent ---
    def test_what_month_is_it(self):
        self._assert_intent("what month is it", "what_month_is_it.intent")

    def test_what_month_is_it_effect(self):
        self._assert_effect("what month is it", "what_month_is_it.intent")

    # --- what_year_is_it.intent ---
    def test_what_year_is_it(self):
        self._assert_intent("what year is it", "what_year_is_it.intent")

    def test_what_year_is_it_effect(self):
        self._assert_effect("what year is it", "what_year_is_it.intent")
