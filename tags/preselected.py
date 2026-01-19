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
        # --- Original Legacy Items ---
        {'id': [13192677, 13192674], 'site': 'gelbooru'},
        {'id': 13187839, 'site': 'gelbooru'},
        {'id': 13241578, 'site': 'gelbooru'},
        {'id': 13245752, 'site': 'gelbooru'},
        {'id': [6281096, 6281095], 'site': 'safebooru'},
        {'id': 6269562, 'site': 'safebooru'},
        
        # --- Pixiv Multi-Page Items (Flattened) ---
        {'id': 139834330, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139790018, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139705172, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139667347, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139588487, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139548472, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139259019, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139167661, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 139124297, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138973841, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138700228, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138665211, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138541989, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138470201, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138436038, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138055898, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 138014311, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137976719, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137907951, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137870947, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137831558, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137791749, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137748175, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137678392, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5]},
        {'id': 137635947, 'site': 'pixiv', 'pages': [0, 1, 2, 3]},
        {'id': 137345148, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 137040718, 'site': 'pixiv', 'pages': [0, 1, 2, 3]},
        {'id': 136633371, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4]},
        {'id': 136261973, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4]},
        {'id': 136169005, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135940587, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5]},
        {'id': 135859266, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135744643, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135707141, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135669799, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4]},
        {'id': 135669664, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135545990, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135513126, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6, 7]},
        {'id': 135474749, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135352685, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135311415, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5]},
        {'id': 135273301, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135240209, 'site': 'pixiv', 'pages': [0, 1]},
        {'id': 135200531, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135166747, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135126033, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135076225, 'site': 'pixiv', 'pages': [0, 1]},
        {'id': 135040233, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 135040094, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134964027, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134925521, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134890897, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134855541, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134808116, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134765819, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134728357, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134693419, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134658536, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134620136, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134581977, 'site': 'pixiv', 'pages': [0, 1]},
        {'id': 134537422, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134491951, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134416543, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134378363, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134341771, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134304805, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134260893, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134220354, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]},
        {'id': 134178980, 'site': 'pixiv', 'pages': [0, 1, 2, 3, 4, 5, 6]}
    ],
    'hug': [
    ],
    'pat': [
    ],
    'poke': [
    ],
    'cuddle': [
        {'id': 13302146, 'site': 'gelbooru'},
        {'id': 13287762, 'site': 'gelbooru'},
        {'id': 13068847, 'site': 'gelbooru'},
        {'id': 119199250, 'site': 'pixiv', 'pages': [0]},
    ],
    'tuck': [
    ],
}
