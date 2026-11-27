"""Spoken dates, times and years: the chronologia writer where it writes the
language, ovos-date-parser for every other language and for relative dates."""
import datetime
from typing import Optional

from chronologia.spoken import UnsupportedForm, spoken_date as _date, \
    spoken_time as _time, spoken_year as _year, writes
from ovos_date_parser import nice_date, nice_time, nice_year


def spoken_date(dt: datetime.datetime, lang: str,
                now: Optional[datetime.datetime] = None) -> str:
    """The date with its weekday. With ``now``, ovos-date-parser speaks
    "today", "tomorrow" and drops the year it shares with ``now``."""
    if now is None and writes(lang):
        try:
            return _date(lang, day=dt.day, month=dt.month, year=dt.year,
                         weekday=dt.weekday())
        except UnsupportedForm:
            pass
    return nice_date(dt, lang=lang, now=now)


def spoken_day_month(dt: datetime.datetime, lang: str) -> str:
    """The weekday, the day and the month, with no year."""
    if writes(lang):
        try:
            return _date(lang, day=dt.day, month=dt.month,
                         weekday=dt.weekday())
        except UnsupportedForm:
            pass
    return ', '.join(nice_date(dt, lang=lang).split(', ')[:2])


def spoken_time(dt: datetime.datetime, lang: str, use_24hour: bool) -> str:
    if writes(lang):
        try:
            if use_24hour:
                return _time(lang, dt.hour, dt.minute)
            return _time(lang, dt.hour, dt.minute, clock="12h",
                         style="phrase", period=True)
        except UnsupportedForm:
            pass
    return nice_time(dt, lang=lang, speech=True, use_24hour=use_24hour,
                     use_ampm=not use_24hour)


def spoken_year(dt: datetime.datetime, lang: str) -> str:
    if writes(lang):
        try:
            return _year(lang, dt.year)
        except UnsupportedForm:
            pass
    return nice_year(dt, lang=lang)
