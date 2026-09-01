import glob
import unittest
from os.path import dirname, join

_LOCALE_DIR = join(dirname(dirname(dirname(__file__))), "locale")


class TestEntityFilesHoldValuesNotSentences(unittest.TestCase):
    """A ``.entity`` file must hold example VALUES for its slot, not whole
    intent sentences. A slot reference (``{...}``) or a line ending in
    sentence punctuation is a sign the file was populated with intent
    utterances instead of entity samples.
    """

    def test_no_entity_line_is_a_slotted_sentence(self):
        offenders = []
        for path in sorted(glob.glob(join(_LOCALE_DIR, "*", "*.entity"))):
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, start=1):
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    if "{" in line or "}" in line:
                        offenders.append(f"{path}:{lineno}: {line!r} (contains a slot)")
                    elif line[-1] in ".?!":
                        offenders.append(f"{path}:{lineno}: {line!r} (ends in sentence punctuation)")
        self.assertFalse(offenders, "\n".join(offenders))
