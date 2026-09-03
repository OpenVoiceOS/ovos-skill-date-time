"""Regression test for the is.leap.year.intent dialog-data bug.

Bug: when the queried year was NOT a leap year, the "no" dialogs were fed
``get_next_leap_year(...)`` instead of the actually-queried year, so e.g.
"is 2025 a leap year" spoke "No, 2028 is not a leap year" -- doubly wrong,
since the dialog template says "{year} is not a leap year" but named the
next leap year instead of the queried one.
"""
import datetime
import unittest
from unittest.mock import patch

from ovos_utils.messagebus import FakeBus

from ovos_skill_date_time import TimeSkill

SKILL_ID = "ovos-skill-date-time.openvoiceos"


class TestLeapYearDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = TimeSkill()
        cls.skill._startup(FakeBus(), SKILL_ID)

    def _run(self, utterance: str, fixed_now: datetime.datetime):
        with patch.object(self.skill, "get_datetime", return_value=fixed_now), \
             patch.object(self.skill, "speak_dialog") as speak_dialog:
            self.skill.handle_is_leap_year(
                type("Msg", (), {"data": {"utterance": utterance}})()
            )
        return speak_dialog

    def test_non_leap_current_year_speaks_queried_year(self):
        # 2025 is not a leap year; the "no" dialog must name 2025, not the
        # next leap year (2028).
        now = datetime.datetime(2025, 6, 1)
        speak_dialog = self._run("is this year a leap year", now)
        speak_dialog.assert_called_once_with(
            "leap.year.current.no", {"year": 2025}
        )

    def test_leap_current_year_still_speaks_positive_dialog(self):
        # 2024 is a leap year; behavior must remain unchanged.
        now = datetime.datetime(2024, 6, 1)
        speak_dialog = self._run("is this year a leap year", now)
        speak_dialog.assert_called_once_with(
            "leap.year.current.yes", {"year": 2024}
        )

    def test_non_leap_next_year_speaks_queried_year(self):
        # queried from 2025 -> next_year 2026, not a leap year; dialog must
        # name 2026, not some further-future leap year.
        now = datetime.datetime(2025, 6, 1)
        speak_dialog = self._run("is next year a leap year", now)
        speak_dialog.assert_called_once_with(
            "leap.year.next.no", {"year": 2026}
        )

    def test_leap_next_year_still_speaks_positive_dialog(self):
        # queried from 2023 -> next_year 2024, a leap year.
        now = datetime.datetime(2023, 6, 1)
        speak_dialog = self._run("is next year a leap year", now)
        speak_dialog.assert_called_once_with(
            "leap.year.next.yes", {"year": 2024}
        )

    def test_non_leap_either_scope_names_the_true_next_leap_year(self):
        # queried from 2026 -> current_year 2026, next_year 2027, neither
        # leap; the true next leap year after 2027 is 2028. The buggy code
        # asked get_next_leap_year(next_year + 1) = get_next_leap_year(2028),
        # which -- since get_next_leap_year returns the next leap year
        # STRICTLY AFTER its argument -- skips 2028 and answers 2032.
        now = datetime.datetime(2026, 6, 1)
        speak_dialog = self._run("is this year a leap year or next", now)
        speak_dialog.assert_called_once_with(
            "leap.year.either.no", {"year": 2028}
        )


if __name__ == "__main__":
    unittest.main()
