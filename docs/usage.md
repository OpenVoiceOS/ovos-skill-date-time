# Phrases for each intent
<!-- agent-hint
covers: example phrases for each intent of the en-US locale
source: locale/en-US/intents/*.intent
generated: no
verify: python docs/verify_phrases.py
see: speech.md, settings.md
-->

Each phrase on this page starts the intent in its section. `docs/verify_phrases.py` sends each quoted phrase through a padacioso container built from `locale/en-US/intents` and fails when a phrase starts a different intent or no intent.

The `.intent` files list more forms. At runtime the intent pipeline can also route phrasings that are not in the files.

## The time: `what_time_is_it`

- "What time is it?"
- "What time is it in Paris?"
- "What's the time now?"
- "What does the clock say right now?"

## A time from now: `what_time_will_it_be`

- "What time will it be in 5 minutes?"
- "What time will it be in an hour?"
- "What time will it be in Tokyo in 2 hours?"

When the phrase holds no length of time, the skill asks for one with `ask_offset.dialog`.

## The day: `what_day_is_it`

- "What day is it?"
- "What day is today?"
- "Tell me the current day in Sydney"

The answer is the date of today with its weekday.

## The weekday of a date: `weekday_for_date`

- "What day of the week is March twentieth?"
- "What weekday was July fourth?"
- "Is it Friday?"

A yes or no question that names a weekday ("is it Friday") gets a yes or no answer.

## Days until a date or between two dates: `time_until`

- "How far away is Christmas?"
- "How many days between March first and June fifth?"

A phrase with one date gives the date and the number of days from today. A phrase with two dates fills the `{start}` and `{end}` slots and gives the number of days between them.

## The month: `what_month_is_it`

- "What month is it?"

## The year: `what_year_is_it`

- "What year is it?"
- "Tell me the current year"

## The coming weekend: `date_future_weekend`

- "When is the coming weekend?"

## The last weekend: `date_last_weekend`

- "When was the last weekend?"

## The next leap year: `next_leap_year`

- "When is the next leap year?"

## Leap year questions: `is_leap_year`

- "Is this year a leap year?"
- "Is next year a leap year?"

---
[Home](index.md) · [Next →](speech.md)
