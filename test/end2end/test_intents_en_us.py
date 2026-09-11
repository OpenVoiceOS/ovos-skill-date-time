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
import time
from pathlib import Path
from unittest import TestCase, mock

import pytz
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session
from ovos_date_parser import nice_date, nice_day, nice_month, nice_time, nice_year
from ovoscope import get_minicroft

SKILL_ID = "ovos-skill-date-time.openvoiceos"
LANG = "en-US"
LOCALE_EN_US = Path(__file__).parent.parent.parent / "locale" / "en-US" / "dialog"

# The intent files are padacioso samples. Exact expansions score in the -high
# band while the slotted variants land lower, so register all three bands.
PIPELINE = [
    "ovos-padacioso-pipeline-plugin-high",
    "ovos-padacioso-pipeline-plugin-medium",
    "ovos-padacioso-pipeline-plugin-low",
]

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
# False, use_ampm=False) when no location slot; handle_current_date ->
# nice_date(dt, lang); handle_current_day -> nice_day(now, lang);
# handle_current_month -> nice_month(now, lang); handle_current_year ->
# nice_year(now, lang)). Using the same well-tested formatting library the
# skill imports still verifies what the *skill* does on its own: that it
# freezes/derives the right anchor datetime, resolves the right session
# timezone, calls the right formatter, and speaks the right dialog file --
# a handler that used the wrong anchor, the wrong timezone, or the wrong
# dialog family fails these checks even though ovos_date_parser itself is
# never in question.
_EFFECTS = {
    "what.time.is.it.intent": {
        "dialog": "time.current",
        "slot": "time",
        "value": nice_time(_LOCAL_DT, lang=LANG, speech=True, use_24hour=False, use_ampm=False),
    },
    "current_date.intent": {
        "dialog": "date",
        "slot": "date",
        "value": nice_date(_LOCAL_DT, lang=LANG),
    },
    "what.day.is.it.intent": {
        "dialog": "day.current",
        "slot": "day",
        "value": nice_day(_LOCAL_DT, lang=LANG),
    },
    "what.month.is.it.intent": {
        "dialog": "month.current",
        "slot": "month",
        "value": nice_month(_LOCAL_DT, lang=LANG),
    },
    "what.year.is.it.intent": {
        "dialog": "year.current",
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
    """Shared MiniCroft boot for all padacioso intent-routing and effect checks.

    All cases share ONE MiniCroft boot rather than one boot per intent
    (as previously split across TestQueryTime/TestCurrentDate/etc.). Each
    boot trains a full padatious/padacioso container and starts the whole
    skill/intent-service stack, which is real CPU work; a CI runner with a
    handful of these booting concurrently or back-to-back can blow past any
    reasonable per-test deadline. Merging into a single boot cuts that cost
    proportionally to the number of classes removed.
    """

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID], max_wait=150)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _assert_intent(self, utterance: str, intent_file: str):
        # ovos_workshop.intents strips a trailing ".intent" suffix off the
        # registered intent name before it ever reaches the bus, so the
        # dispatched message type never carries ".intent" -- see the matching
        # comment in test_golden_utterances.py._assert_intent for the full
        # explanation (same bug, same fix, both files historically built
        # this event name off the raw ".intent"-suffixed argument).
        intent_name = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
        intent_msg_type = f"{SKILL_ID}:{intent_name}"
        matched = []
        handler = lambda msg: matched.append(msg)
        self.minicroft.bus.on(intent_msg_type, handler)
        try:
            session = Session(f"e2e-en_us-{intent_file}-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            )
            # Under parallel CI load a freshly booted minicroft may not have
            # finished registering intents when the first utterance fires, so
            # re-emit until the intent routes or the deadline elapses.
            deadline = time.monotonic() + 45
            while not matched and time.monotonic() < deadline:
                self.minicroft.bus.emit(message)
                waited = time.monotonic() + 5
                while not matched and time.monotonic() < waited:
                    time.sleep(0.2)
        finally:
            self.minicroft.bus.remove(intent_msg_type, handler)
        self.assertTrue(
            matched,
            f"{utterance!r} did not route to {intent_file}",
        )

    def _assert_effect(self, utterance: str, intent_file: str):
        """Assert routing AND that the frozen, pinned-timezone value was spoken."""
        intent_name = intent_file[:-len(".intent")] if intent_file.endswith(".intent") else intent_file
        intent_msg_type = f"{SKILL_ID}:{intent_name}"
        matched = []
        spoken = []
        intent_handler_fn = lambda msg: matched.append(msg)
        speak_handler_fn = lambda msg: spoken.append(msg.data.get("utterance", ""))
        self.minicroft.bus.on(intent_msg_type, intent_handler_fn)
        self.minicroft.bus.on("speak", speak_handler_fn)
        try:
            session = Session(f"e2e-en_us-effect-{intent_file}-{hash(utterance)}")
            session.lang = LANG
            session.pipeline = PIPELINE
            # Session.timezone (OVOS-SESSION-1 §3.5) is a read-only view over
            # session.location['tz']; that key is the one to set explicitly.
            session.location["tz"] = PINNED_TZ
            message = Message(
                "recognizer_loop:utterance",
                {"utterances": [utterance], "lang": LANG},
                {"session": session.serialize()},
            )
            with mock.patch("ovos_skill_date_time.now_local", side_effect=_frozen_now_local):
                deadline = time.monotonic() + 45
                while not matched and time.monotonic() < deadline:
                    self.minicroft.bus.emit(message)
                    waited = time.monotonic() + 5
                    while not matched and time.monotonic() < waited:
                        time.sleep(0.2)
                # the speak message follows the intent-handler message on the
                # same thread; give it a brief settle window
                settle_deadline = time.monotonic() + 3
                while not spoken and time.monotonic() < settle_deadline:
                    time.sleep(0.1)
        finally:
            self.minicroft.bus.remove(intent_msg_type, intent_handler_fn)
            self.minicroft.bus.remove("speak", speak_handler_fn)
        self.assertTrue(matched, f"{utterance!r} did not route to {intent_file}")
        self.assertTrue(spoken, f"expected a spoken response for {utterance!r}")
        expected_lines = _RENDERED[intent_file]
        self.assertTrue(
            any(utt in expected_lines for utt in spoken),
            f"expected one of {expected_lines!r} to be spoken for {utterance!r} "
            f"(frozen {_LOCAL_DT.isoformat()} in {PINNED_TZ}), got {spoken!r}",
        )

    # --- what.time.is.it.intent ---
    def test_what_time_is_it(self):
        self._assert_intent("what time is it", "what.time.is.it.intent")

    def test_whats_the_time(self):
        self._assert_intent("what's the time now", "what.time.is.it.intent")

    def test_what_time_is_it_in_location(self):
        self._assert_intent("current time in tokyo", "what.time.is.it.intent")

    def test_what_time_is_it_effect(self):
        self._assert_effect("what time is it", "what.time.is.it.intent")

    # --- current_date.intent ---
    def test_what_date_is_it(self):
        self._assert_intent("what date is it", "current_date.intent")

    def test_tell_me_the_date(self):
        self._assert_intent("tell me the date", "current_date.intent")

    def test_what_date_is_it_effect(self):
        self._assert_effect("what date is it", "current_date.intent")

    # --- what.day.is.it.intent ---
    def test_what_day_is_it(self):
        self._assert_intent("what day is it", "what.day.is.it.intent")

    def test_what_day_is_it_effect(self):
        self._assert_effect("what day is it", "what.day.is.it.intent")

    # --- what.month.is.it.intent ---
    def test_what_month_is_it(self):
        self._assert_intent("what month is it", "what.month.is.it.intent")

    def test_what_month_is_it_effect(self):
        self._assert_effect("what month is it", "what.month.is.it.intent")

    # --- what.year.is.it.intent ---
    def test_what_year_is_it(self):
        self._assert_intent("what year is it", "what.year.is.it.intent")

    def test_what_year_is_it_effect(self):
        self._assert_effect("what year is it", "what.year.is.it.intent")
