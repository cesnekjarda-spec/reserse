import re
import textwrap
import unicodedata
from collections import Counter
from urllib.parse import urlparse


STOPWORDS = {
    "a", "aby", "aj", "ale", "ani", "as", "asi", "az", "bez", "bude", "budou", "by", "byt",
    "byl", "byla", "byli", "bylo", "co", "do", "ho", "i", "jak", "je", "jeho", "jejich", "jejim",
    "její", "jen", "jenom", "jeste", "ji", "jine", "jiz", "jsme", "jsou", "jste", "k", "kam", "kde",
    "kdy", "ktera", "ktere", "ktereho", "kteri", "kterou", "ktery", "ma", "maji", "mate", "me", "mezi",
    "mi", "mit", "mne", "moc", "mu", "na", "nad", "nam", "napr", "nas", "nase", "ne", "nebo", "nejsou",
    "neni", "nez", "nich", "nim", "nove", "novy", "o", "od", "pak", "po", "pod", "podle", "pokud",
    "pro", "proto", "protoze", "pred", "pri", "se", "si", "sice", "sve", "svuj", "ta", "tak", "take",
    "takze", "ten", "tento", "teto", "tim", "to", "toho", "tom", "tomto", "tomu", "tu", "tuto", "ty",
    "u", "uz", "v", "vam", "vas", "vase", "ve", "vice", "vsak", "vy", "z", "za", "ze", "zde", "zpet",
    "about", "after", "all", "also", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "has", "have", "in", "into", "is", "it", "its", "more", "new", "of", "on", "or", "that",
    "the", "their", "this", "to", "was", "were", "will", "with",
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
    return value.lower() or "item"


def normalize_word(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return value.lower()


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def tokenize(value: str) -> list[str]:
    words = re.findall(r"[\w\-]{3,}", value.lower(), flags=re.UNICODE)
    cleaned: list[str] = []
    for word in words:
        normalized = normalize_word(word)
        if normalized in STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        if len(normalized) < 3:
            continue
        cleaned.append(normalized)
    return cleaned


def extract_keywords(texts: str | list[str], limit: int = 8) -> list[str]:
    if isinstance(texts, str):
        texts = [texts]

    counter: Counter[str] = Counter()
    for text in texts:
        if not text:
            continue
        counter.update(tokenize(text))
    return [word for word, _ in counter.most_common(limit)]


def shorten_text(value: str | None, width: int = 180) -> str:
    if not value:
        return ""
    return textwrap.shorten(normalize_whitespace(value), width=width, placeholder="…")


def split_sentences(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"(?<=[\.!?])\s+", normalize_whitespace(value))
    return [part.strip() for part in parts if len(part.strip()) > 30]


def top_sentences(texts: list[str], limit: int = 4) -> list[str]:
    sentences: list[str] = []
    for text in texts:
        for sentence in split_sentences(text):
            if sentence not in sentences:
                sentences.append(sentence)
    return sentences[:limit]


def domain_from_url(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).netloc or "").replace("www.", "")
