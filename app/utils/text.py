import re
import unicodedata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9\s-]", "", normalized).strip().lower()
    normalized = re.sub(r"[\s_-]+", "-", normalized)
    normalized = re.sub(r"^-+|-+$", "", normalized)
    return normalized
