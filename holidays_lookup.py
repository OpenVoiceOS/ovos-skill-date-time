# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Holiday names in date questions: "when is christmas", "how many days
until easter", "hvornår er det jul", "what day of the week is christmas".

ovos-date-parser's extract_datetime() does not know holiday names, so these
questions fell back to "now" and were answered with today's date. Holidays are
looked up with the `holidays` library (pure calendar arithmetic, no network):

- locale/<lang>/holidays.json maps what people say ("christmas", "jul",
  "påske") to the library's own name for the holiday ("Christmas Day",
  "Juledag") or to EASTER (Easter Sunday is not a public holiday everywhere).
- Anything else is matched against the library's own names for the country,
  so a holiday that is not in the list still works when it is said by name.
- The country is the device's location, then the language's region (a Danish
  device in the US still knows when "jul" is).
"""
import json
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dateutil.easter import easter

try:
    import holidays as _holidays
except ImportError:  # pragma: no cover - a declared dependency
    _holidays = None

LOCALE_DIR = Path(__file__).resolve().parent / "locale"
EASTER = "__EASTER__"


@lru_cache(maxsize=None)
def holiday_aliases(lang: str) -> Dict[str, str]:
    """locale/<lang>/holidays.json, keys lower case, longest first."""
    lang = (lang or "").lower()
    for folder in LOCALE_DIR.iterdir() if LOCALE_DIR.is_dir() else []:
        if folder.name.lower() == lang and (folder / "holidays.json").is_file():
            data = json.loads((folder / "holidays.json").read_text(encoding="utf-8"))
            items = {k.lower(): v for k, v in data.items() if not k.startswith("_")}
            return dict(sorted(items.items(), key=lambda kv: len(kv[0]), reverse=True))
    return {}


def _language_for(country_cls, lang: str) -> Optional[str]:
    """The library's name language closest to `lang` ("en-US" -> "en_US",
    "da-DK" -> "da"), or None for the country's default."""
    supported = getattr(country_cls, "supported_languages", ()) or ()
    wanted = lang.replace("-", "_").lower()
    primary = wanted.split("_")[0]
    for candidate in supported:
        if candidate.lower() == wanted:
            return candidate
    for candidate in supported:
        if candidate.lower() == primary:
            return candidate
    for candidate in supported:
        if candidate.lower().startswith(primary + "_"):
            return candidate
    return None


@lru_cache(maxsize=64)
def _country_holidays(country: str, lang: str, years: Tuple[int, ...]) -> Dict[date, str]:
    if _holidays is None or not country:
        return {}
    cls = getattr(_holidays, country.upper(), None)
    if cls is None:
        return {}
    kwargs = {"years": list(years)}
    categories = getattr(cls, "supported_categories", None)
    if categories:
        # every category: Halloween is "unofficial" in the US, Grundlovsdag
        # "optional" in Denmark - category names differ per country
        kwargs["categories"] = categories
    language = _language_for(cls, lang)
    if language:
        kwargs["language"] = language
    try:
        return dict(cls(**kwargs))
    except Exception:
        return {}


def _countries(location_country: Optional[str], lang: str) -> List[str]:
    region = lang.split("-")[-1] if "-" in (lang or "") else ""
    out = []
    for c in (location_country, region):
        if c and len(c) == 2 and c.upper() not in out:
            out.append(c.upper())
    return out


def _next_easter(today: date) -> date:
    for year in (today.year, today.year + 1):
        if easter(year) >= today:
            return easter(year)
    return easter(today.year + 1)


def _fold(text: str) -> str:
    """lower case, accents off: the intent parser hands over "noel" and
    "paske" for "noël" and "påske"."""
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(_fold(phrase))}(?!\w)", text) is not None


def find_holiday(text: str, lang: str, today: date,
                 location_country: Optional[str] = None) -> Optional[Tuple[str, date]]:
    """(name, next date on or after today) of a holiday named in `text`,
    or None. The name is the library's own (or the spoken one for Easter)."""
    text = _fold(text or "")
    if not text:
        return None
    years = (today.year, today.year + 1)
    countries = _countries(location_country, lang)
    for spoken, official in holiday_aliases(lang).items():
        if not _contains(text, spoken):
            continue
        if official == EASTER:
            return spoken, _next_easter(today)
        for country in countries:
            days = sorted(d for d, name in _country_holidays(country, lang, years).items()
                          if official.lower() in name.lower() and d >= today)
            if days:
                return official, days[0]
    # said by the library's own name ("when is grundlovsdag", "when is labor day")
    for country in countries:
        names = {}
        for d, name in sorted(_country_holidays(country, lang, years).items()):
            for part in name.split(";"):
                part = part.strip()
                if d >= today and _fold(part) not in names:
                    names[_fold(part)] = (part, d)
        for low in sorted(names, key=len, reverse=True):
            if len(low) >= 4 and _contains(text, low):
                return names[low]
    return None


def holiday_on(day: date, lang: str, location_country: Optional[str] = None) -> Optional[str]:
    """The holiday on `day` where the device is, or None."""
    for country in _countries(location_country, lang)[:1]:
        return _country_holidays(country, lang, (day.year,)).get(day)
    return None


def next_holiday(today: date, lang: str,
                 location_country: Optional[str] = None) -> Optional[Tuple[str, date]]:
    """The first holiday after today where the device is."""
    for country in _countries(location_country, lang)[:1]:
        upcoming = sorted((d, n) for d, n in _country_holidays(
            country, lang, (today.year, today.year + 1)).items() if d > today)
        if upcoming:
            return upcoming[0][1], upcoming[0][0]
    return None
