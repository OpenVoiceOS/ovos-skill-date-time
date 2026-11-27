"""Which writer speaks each value: chronologia for pt-PT, ovos-date-parser
for other locales and for dates relative to a reference day."""
import datetime
import unittest

from ovos_skill_date_time.speech import spoken_date, spoken_day_month, \
    spoken_time, spoken_year

DT = datetime.datetime(2026, 3, 4, 14, 35)  # a Wednesday


class TestSpeech(unittest.TestCase):
    def test_pt_pt_comes_from_chronologia(self):
        # the chronologia writer joins the weekday with no comma
        self.assertEqual(spoken_date(DT, "pt-PT"),
                         "quarta-feira quatro de março de dois mil e vinte e seis")
        self.assertEqual(spoken_day_month(DT, "pt-PT"), "quarta-feira quatro de março")
        self.assertEqual(spoken_year(DT, "pt-PT"), "dois mil e vinte e seis")
        self.assertEqual(spoken_time(DT, "pt-PT", use_24hour=True),
                         "catorze e trinta e cinco")
        self.assertEqual(spoken_time(DT, "pt-PT", use_24hour=False),
                         "três menos vinte e cinco da tarde")

    def test_a_reference_day_keeps_the_relative_words(self):
        self.assertEqual(spoken_date(DT, "pt-PT", now=DT), "hoje")
        self.assertEqual(spoken_date(DT + datetime.timedelta(days=1), "pt-PT", now=DT),
                         "amanhã")

    def test_other_locales_come_from_ovos_date_parser(self):
        self.assertEqual(spoken_date(DT, "en-US"),
                         "wednesday, march fourth, twenty twenty six")
        self.assertEqual(spoken_day_month(DT, "en-US"), "wednesday, march fourth")
        self.assertEqual(spoken_year(DT, "en-US"), "twenty twenty six")
        self.assertEqual(spoken_time(DT, "en-US", use_24hour=False), "two thirty five p.m.")


if __name__ == "__main__":
    unittest.main()
