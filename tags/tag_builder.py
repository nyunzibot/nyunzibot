import random
from .tag_sets import NEGATIVE_TAGS, ARTIST_BOOSTS

def build_tags(base: str, positives: list[str]) -> str:
    # pick 1–2 positives to keep queries effective but not too strict
    k = 1
    p = random.sample(positives, k=k)
    return f"{base} {' '.join(p)} {NEGATIVE_TAGS}".strip()

def build_tag_ladder(base: str, positives: list[str], negative_tags: str = None) -> list[str]:
    """Tag fallback ladder:
    strict/high-quality -> relax step-by-step -> base only.
    Also optionally injects a rotating artist boost for quality.
    
    Args:
        base: The base tag (e.g., "2girls")
        positives: List of positive tags to sample from
        negative_tags: Optional custom negative tags string (defaults to NEGATIVE_TAGS)
    """
    neg = negative_tags if negative_tags is not None else NEGATIVE_TAGS
    artist = random.choice(ARTIST_BOOSTS) if ARTIST_BOOSTS else None

    quality_strict = []
    focus_strict = []

    k = 1
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
        out.append(f"{' '.join(parts)} {neg}".strip())
    return out
