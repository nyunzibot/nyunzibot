# =========================
# PRE-SELECTED SFW IMAGES BY GELBOORU ID
# =========================
# Format: "category": [item1, item2, ...]
# Each item can be:
#   - A single Gelbooru post ID: 13192674
#   - A list of IDs for image pairs/groups: [13192674, 12345678]
# These will be fetched from Gelbooru API and prioritized before regular booru fetching.

PRESELECTED_SFW = {
    'kiss': [
        # Example: {'id': 12345, 'site': 'gelbooru'}
        # Or list of IDs: {'id': [123, 456], 'site': 'gelbooru'}
        {'id': [13192677, 13192674], 'site': 'gelbooru'},
        {'id': 13187839, 'site': 'gelbooru'},
    ],
    'hug': [
    ],
    'pat': [
    ],
    'poke': [
    ],
    'cuddle': [
    ],
    'tuck': [
    ],
}
