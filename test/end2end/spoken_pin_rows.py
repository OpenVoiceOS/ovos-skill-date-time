"""Hand-written utterances and expected spoken slots for test_spoken_writers.py.

The clock is frozen at Wednesday 2026-03-04 14:35 in Europe/Lisbon. Each
expected value is written by hand from the locale grammar, not read back from
ovos-date-parser. Every row is machine-written and needs_manual until a native
speaker of the locale confirms it.

Row: (case, utterance, dialog, slot, expected). Cases: time, date, weekday,
tomorrow, weekday_of, month, year, days_until. "weekday_of" and "days_until"
name Friday 2026-03-20, 16 days after the frozen day.
"""

ROWS = {
    "pt-PT": [
        ("time", "que horas são", "time_current", "time", "três menos vinte e cinco da tarde"),
        ("date", "qual é a data de hoje", "date", "date", "quarta-feira, quatro de março de dois mil e vinte e seis"),
        ("weekday", "que dia da semana é hoje", "weekday_current", "weekday", "quarta-feira"),
        ("tomorrow", "que dia da semana é amanhã", "weekday_at_date_future", "weekday", "quinta-feira"),
        ("weekday_of", "que dia da semana é vinte de março", "weekday_at_date_future", "weekday", "sexta-feira"),
        ("month", "em que mês estamos", "month_current", "month", "março"),
        ("year", "em que ano estamos", "year_current", "year", "dois mil e vinte e seis"),
        ("days_until", "quantos dias faltam até vinte de março", "date_relative_future", "num_days", "dezasseis dias"),
    ],
    "pt-BR": [
        ("time", "que horas são", "time_current", "time", "três menos vinte e cinco da tarde"),
        ("date", "qual é a data de hoje", "date", "date", "quarta-feira, quatro de março de dois mil e vinte e seis"),
        ("weekday", "que dia da semana é hoje", "weekday_current", "weekday", "quarta-feira"),
        ("tomorrow", "que dia da semana é amanhã", "weekday_at_date_future", "weekday", "quinta-feira"),
        ("weekday_of", "que dia da semana é vinte de março", "weekday_at_date_future", "weekday", "sexta-feira"),
        ("month", "em que mês estamos", "month_current", "month", "março"),
        ("year", "em que ano estamos", "year_current", "year", "dois mil e vinte e seis"),
        ("days_until", "quantos dias faltam até vinte de março", "date_relative_future", "num_days", "dezesseis dias"),
    ],
    "es-ES": [
        ("time", "qué hora es", "time_current", "time", "las tres menos veinticinco de la tarde"),
        ("date", "cuál es la fecha de hoy", "date", "date", "miércoles, cuatro de marzo de dos mil veintiséis"),
        ("weekday", "qué día de la semana es hoy", "weekday_current", "weekday", "miércoles"),
        ("tomorrow", "qué día de la semana es mañana", "weekday_at_date_future", "weekday", "jueves"),
        ("weekday_of", "qué día de la semana es el veinte de marzo", "weekday_at_date_future", "weekday", "viernes"),
        ("month", "en qué mes estamos", "month_current", "month", "marzo"),
        ("year", "en qué año estamos", "year_current", "year", "dos mil veintiséis"),
        ("days_until", "cuántos días faltan para el veinte de marzo", "date_relative_future", "num_days", "dieciséis días"),
    ],
    "fr-FR": [
        ("time", "quelle heure est-il", "time_current", "time", "trois heures moins vingt-cinq de l'après-midi"),
        ("date", "quelle est la date d'aujourd'hui", "date", "date", "mercredi quatre mars deux-mille-vingt-six"),
        ("weekday", "quel jour de la semaine sommes-nous", "weekday_current", "weekday", "mercredi"),
        ("tomorrow", "quel jour de la semaine serons-nous demain", "weekday_at_date_future", "weekday", "jeudi"),
        ("weekday_of", "quel jour de la semaine tombe le vingt mars", "weekday_at_date_future", "weekday", "vendredi"),
        ("month", "en quel mois sommes-nous", "month_current", "month", "mars"),
        ("year", "en quelle année sommes-nous", "year_current", "year", "deux-mille-vingt-six"),
        ("days_until", "combien de jours jusqu'au vingt mars", "date_relative_future", "num_days", "seize jours"),
    ],
    "it-IT": [
        ("time", "che ore sono", "time_current", "time", "due e trentacinque del pomeriggio"),
        ("date", "che data è oggi", "date", "date", "mercoledì, quattro marzo, duemilaventisei"),
        ("weekday", "che giorno della settimana è oggi", "weekday_current", "weekday", "mercoledì"),
        ("tomorrow", "che giorno della settimana è domani", "weekday_at_date_future", "weekday", "giovedì"),
        ("weekday_of", "che giorno della settimana è il venti marzo", "weekday_at_date_future", "weekday", "venerdì"),
        ("month", "in che mese siamo", "month_current", "month", "marzo"),
        ("year", "in che anno siamo", "year_current", "year", "duemilaventisei"),
        ("days_until", "quanti giorni mancano al venti marzo", "date_relative_future", "num_days", "sedici giorni"),
    ],
    "de-DE": [
        ("time", "wie spät ist es", "time_current", "time", "zwei uhr fünfunddreißig nachmittags"),
        ("date", "welches Datum ist heute", "date", "date", "Mittwoch, vierter März, zweitausendsechsundzwanzig"),
        ("weekday", "welcher Wochentag ist heute", "weekday_current", "weekday", "Mittwoch"),
        ("tomorrow", "welcher Wochentag ist morgen", "weekday_at_date_future", "weekday", "Donnerstag"),
        ("weekday_of", "welcher Wochentag ist der zwanzigste März", "weekday_at_date_future", "weekday", "Freitag"),
        ("month", "welcher Monat ist es", "month_current", "month", "März"),
        ("year", "welches Jahr haben wir", "year_current", "year", "zweitausendsechsundzwanzig"),
        ("days_until", "wie viele Tage sind es noch bis zum zwanzigsten März", "date_relative_future", "num_days", "sechzehn Tage"),
    ],
    "nl-NL": [
        ("time", "hoe laat is het", "time_current", "time", "vijfentwintig voor drie 's middags"),
        ("date", "wat is de datum vandaag", "date", "date", "woensdag, vier maart, tweeduizend zesentwintig"),
        ("weekday", "welke dag van de week is het vandaag", "weekday_current", "weekday", "woensdag"),
        ("tomorrow", "welke dag van de week is het morgen", "weekday_at_date_future", "weekday", "donderdag"),
        ("weekday_of", "op welke dag van de week valt twintig maart", "weekday_at_date_future", "weekday", "vrijdag"),
        ("month", "welke maand is het", "month_current", "month", "maart"),
        ("year", "welk jaar is het", "year_current", "year", "tweeduizend zesentwintig"),
        ("days_until", "hoeveel dagen zijn er nog tot twintig maart", "date_relative_future", "num_days", "zestien dagen"),
    ],
    "da-DK": [
        ("time", "hvad er klokken", "time_current", "time", "to femogtredive om eftermiddagen"),
        ("date", "hvad er datoen i dag", "date", "date", "onsdag, den fjerde marts, to tusind og seksogtyve"),
        ("weekday", "hvilken ugedag er det i dag", "weekday_current", "weekday", "onsdag"),
        ("tomorrow", "hvilken ugedag er det i morgen", "weekday_at_date_future", "weekday", "torsdag"),
        ("weekday_of", "hvad er ugedag for den tyvende marts", "weekday_at_date_future", "weekday", "fredag"),
        ("month", "hvilken måned er det", "month_current", "month", "marts"),
        ("year", "hvilket år er det", "year_current", "year", "to tusind og seksogtyve"),
        ("days_until", "hvor mange dage er der tilbage indtil den tyvende marts", "date_relative_future", "num_days", "seksten dage"),
    ],
    "en-US": [
        ("time", "what time is it", "time_current", "time", "two thirty five p.m."),
        ("date", "what's the date today", "date", "date", "wednesday, march fourth, twenty twenty six"),
        ("weekday", "what day of the week is it", "weekday_current", "weekday", "wednesday"),
        ("tomorrow", "what day of the week is tomorrow", "weekday_at_date_future", "weekday", "thursday"),
        ("weekday_of", "what day of the week is march twentieth", "weekday_at_date_future", "weekday", "friday"),
        ("month", "what month is it", "month_current", "month", "march"),
        ("year", "what year is it", "year_current", "year", "twenty twenty six"),
        ("days_until", "how many days until march twentieth", "date_relative_future", "num_days", "sixteen days"),
    ],
}
