import random
from .tag_sets import NEGATIVE_TAGS, ARTIST_BOOSTS

def build_tags(base: str, positives: list[str]) -> str:
    # pick 1–2 positives to keep queries effective but not too strict
    k = 2 if len(positives) >= 2 else 1
    p = random.sample(positives, k=k)
    return f"{base} {' '.join(p)} {NEGATIVE_TAGS}".strip()

def build_tag_ladder(base: str, positives: list[str]) -> list[str]:
    """Tag fallback ladder:
    strict/high-quality -> relax step-by-step -> base only.
    Also optionally injects a rotating artist boost for quality.
    """
    artist = random.choice(ARTIST_BOOSTS) if ARTIST_BOOSTS else None

    quality_strict = []
    focus_strict = []

    k = 2 if len(positives) >= 2 else 1
    p = random.sample(positives, k=k)

    ladders: list[list[str]] = [
        [base, *p, *quality_strict, *focus_strict, artist],
        [base, *p, *quality_strict, artist],
        [base, *p, artist],
        [base, *p],
        [base],
    ]

    out: list[str] = []
    for parts in ladders:
        parts = [x for x in parts if x]
        out.append(f"{' '.join(parts)} {NEGATIVE_TAGS}".strip())
    return out
