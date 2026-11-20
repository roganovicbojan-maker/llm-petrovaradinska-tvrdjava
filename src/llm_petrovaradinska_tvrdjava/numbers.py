import re
import unicodedata

from .reviews import SERBIAN_CYRILLIC

DIGITS = re.compile(r"(?<!\d)[+−-]?\d+(?:[.,]\d+)*")
GROUPED = re.compile(r"[+−-]?[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?")
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


def numeric_tokens(text: str) -> set[str]:
    numbers = {
        (raw.replace(".", "") if GROUPED.fullmatch(raw) else raw)
        .replace("−", "-")
        .replace(",", ".")
        .removeprefix("+")
        for raw in DIGITS.findall(text)
    }
    # Serbian "što" is a conjunction. Keep it apart from the number "sto".
    text = re.sub(r"\b(?:što|што)\b", "|", text.casefold())
    text = unicodedata.normalize("NFKD", text.translate(SERBIAN_CYRILLIC))
    text = "".join(char for char in text if not unicodedata.combining(char))
    group: list[str] = []
    tokens = re.findall(r"[^\W\d_]+|[^\s]", text)
    for index, word in enumerate([*tokens, ""]):
        if word in WORDS:
            group.append(word)
        elif word == "i" and group and index + 1 < len(tokens) and tokens[index + 1] in SMALL:
            continue
        elif group:
            numbers.add(str(spelled_number(group)))
            group.clear()
    return numbers
