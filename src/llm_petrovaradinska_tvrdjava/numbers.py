import re
import unicodedata

from .reviews import SERBIAN_CYRILLIC

NUMBER = r"\d+(?:[.,\u00a0\u202f]\d+)*"
DIGITS = re.compile(rf"(?<!\d)[+\u2212-]?{NUMBER}")
GROUPED = re.compile(r"^[+\u2212-]?\d{1,3}(?:[.\u00a0\u202f]\d{3})+(?:,\d+)?$")
SMALL = {
    "nula": 0,
    "jedan": 1,
    "jedna": 1,
    "jedno": 1,
    "dva": 2,
    "dve": 2,
    "tri": 3,
    "cetiri": 4,
    "pet": 5,
    "sest": 6,
    "sedam": 7,
    "osam": 8,
    "devet": 9,
    "deset": 10,
    "jedanaest": 11,
    "dvanaest": 12,
    "trinaest": 13,
    "cetrnaest": 14,
    "petnaest": 15,
    "sesnaest": 16,
    "sedamnaest": 17,
    "osamnaest": 18,
    "devetnaest": 19,
    "dvadeset": 20,
    "trideset": 30,
    "cetrdeset": 40,
    "pedeset": 50,
    "sezdeset": 60,
    "sedamdeset": 70,
    "osamdeset": 80,
    "devedeset": 90,
    "sto": 100,
    "stotinu": 100,
    "stotina": 100,
    "stotine": 100,
    "dvesta": 200,
    "dvesto": 200,
    "trista": 300,
    "cetiristo": 400,
    "petsto": 500,
    "seststo": 600,
    "sedamsto": 700,
    "osamsto": 800,
    "devetsto": 900,
}
SCALES = {"hiljadu": 1000, "hiljada": 1000, "hiljade": 1000, "milion": 1000000, "miliona": 1000000}
WORDS = SMALL.keys() | SCALES.keys()
NUMBER_WORD = "(?:" + "|".join(sorted(WORDS, key=lambda word: (-len(word), word))) + ")"
QUANTITY = rf"(?:{NUMBER}|{NUMBER_WORD}(?:\s+(?:i\s+)?{NUMBER_WORD}){{0,8}})"
RANGE = re.compile(rf"(?<!\w)({QUANTITY})\s*(?:[\u2013\u2014-]|\bdo\b)\s*({QUANTITY})(?!\w)")


def spelled_number(words: list[str]) -> int:
    total = group = 0
    for word in words:
        if word in SCALES:
            total += (group or 1) * SCALES[word]
            group = 0
        elif word in {"stotina", "stotine"} and 1 <= group <= 9:
            group *= 100
        else:
            group += SMALL[word]
    return total + group


def normalize_digits(raw: str) -> str:
    if GROUPED.fullmatch(raw):
        raw = re.sub(r"[.\u00a0\u202f]", "", raw)
    return raw.replace("\u2212", "-").replace(",", ".").removeprefix("+")


def numeric_ranges(text: str) -> set[tuple[str, str]]:
    text = re.sub(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", " ", text)
    ranges = set()
    for low, high in RANGE.findall(normalize_words(text)):
        a, b = numeric_tokens(low), numeric_tokens(high)
        if len(a) == len(b) == 1:
            ranges.add((a.pop(), b.pop()))
    return ranges


def continues_number(group: list[str], word: str, conjunction: bool = False) -> bool:
    previous = group[-1]
    if word in SCALES:
        return not conjunction and (previous not in SCALES or SCALES[previous] > SCALES[word])
    if previous in SCALES:
        return True
    before, after = SMALL[previous], SMALL[word]
    if not conjunction and word in {"stotina", "stotine"} and 1 <= before <= 9:
        return True
    return (before >= 100 and after < 100) or (20 <= before < 100 and 0 < after < 10)


def normalize_words(text: str) -> str:
    # Keep the conjunction separate from the number "sto" before removing accents.
    text = re.sub(r"\b(?:\u0161to|\u0448\u0442\u043e)\b", "|", text.casefold())
    text = unicodedata.normalize("NFD", text.translate(SERBIAN_CYRILLIC))
    return "".join(char for char in text if not unicodedata.combining(char))


def numeric_tokens(text: str) -> set[str]:
    numbers = {normalize_digits(raw) for raw in DIGITS.findall(text)}
    text = normalize_words(text)
    group: list[str] = []
    tokens = re.findall(r"[^\W\d_]+|[^\s]", text)
    for index, word in enumerate([*tokens, ""]):
        if (
            word == "i"
            and group
            and index + 1 < len(tokens)
            and tokens[index + 1] in SMALL
            and continues_number(group, tokens[index + 1], conjunction=True)
        ):
            continue
        if group and (word not in WORDS or not continues_number(group, word)):
            numbers.add(str(spelled_number(group)))
            group.clear()
        if word in WORDS:
            group.append(word)
    return numbers
