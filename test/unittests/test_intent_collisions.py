"""No sentence may expand under two intents of one locale.

The m2v classifier trains on every expanded template line labelled with its
intent, so a sentence that two intents produce teaches it two answers. A typed
slot (``{date:date}``) is filled by a parser, so it stands for one placeholder
value; an untyped slot is filled with the values of the locale's
``<slot>.entity`` file.
"""
import itertools
import re
from collections import defaultdict
from pathlib import Path
from unittest import TestCase

from ovos_spec_tools.expansion import expand

LOCALE_DIR = Path(__file__).parent.parent.parent / "locale"
MAX_FILLS = 5000


def _normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[?!.,’']", "", text.lower())).strip()


def _entity_values(locale, slot):
    path = locale / f"{slot}.entity"
    if not path.exists():
        return ["X"]
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _sentences(locale, intent_file):
    sentences = set()
    for line in intent_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        typed = set(re.findall(r"\{(\w+):\w+\}", line))
        for template in expand(line):
            slots = re.findall(r"\{([^{}]+)\}", template)
            fills = itertools.product(*(
                [f"<{s}>"] if s in typed else _entity_values(locale, s)
                for s in slots))
            for fill in itertools.islice(fills, MAX_FILLS):
                text = template
                for slot, value in zip(slots, fill):
                    text = text.replace("{%s}" % slot, value, 1)
                sentences.add(_normalize(text))
    return sentences


class TestIntentCollisions(TestCase):

    def test_no_sentence_belongs_to_two_intents(self):
        collisions = []
        for locale in sorted(p for p in LOCALE_DIR.iterdir() if p.is_dir()):
            owners = defaultdict(list)
            for intent_file in sorted((locale / "intents").glob("*.intent")):
                for sentence in _sentences(locale, intent_file):
                    owners[sentence].append(intent_file.stem)
            for sentence, intents in sorted(owners.items()):
                if len(intents) > 1:
                    collisions.append(f"{locale.name}: {sentence!r} -> {intents}")
        self.assertEqual(collisions, [], "\n".join(collisions[:50]))
