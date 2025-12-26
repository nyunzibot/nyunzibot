# =========================
# TAGS
# =========================
NEGATIVE_TAGS = (
    "-loli -shota -young -underage -child -minor -kid "
    "-furry -anthro -feral -animal -bestiality -horse -dog "
    "-rape -raped -nonconsensual -forced -dubious_consent "
    "-incest -family -twins "
    "-gore -blood -death -guro -snuff -mutilation "
    "-scat -watersports -vomit -diaper -feces -urine -peeing -piss -enema "
    "-inflation -vore -oviposition -egg -stomach_bulge "
    "-pregnant -birth -lactation -impregnation "
    "-prolapse -gap -gaping "
    "-amputee -disfigured -deformed "
    "-ugly_bastard -old_man -fat_man "
    "-giant -mini -micro -macro "
    "-tentacles -monster -slime -demon -alien"
)

# Tags that can be passed in extra_tags even though they're in NEGATIVE_TAGS
ALLOWED_OVERRIDES = {"furry", "anthro"}

# Common base tag options for autocomplete
BASE_TAG_OPTIONS = [
    # "futa_on_female",
    # "futa_on_futa",
    # "futanari",
    # "yuri",
    # "lesbian",
    # "straight",
    # "yaoi",
    # "gay",
    # "solo",
    # "1girl",
    # "2girls",
    # "1boy",
    # "group_sex",
]

# Base tags (edit freely)
PLAP_BASE = "futa_on_female"
SUCC_BASE = "futa_on_female"
BOUNCE_BASE = "futa_on_female"

# SFW Tags for Safebooru (cuddle command)
CUDDLE_BASE = "2girls"  # Safe base that works well on Safebooru
CUDDLE_POSITIVE_SETS = [
    "hug",
    "cuddling",
    "embrace",
    "hugging",
    "yuri",
    "hand_holding",
    "lap_pillow",
    "sleeping",
    "petting",
    "head_on_shoulder",
    "leaning_on_person",
    "princess_carry",
    "cheek_to_cheek",
    "nuzzle",
    "smile",
    "blush",
    "closed_eyes",
    "happy",
]

# SFW negative tags for Safebooru (minimal, just quality filters)
NEGATIVE_TAGS_SFW = (
    "-lowres -bad_anatomy -bad_hands -missing_fingers "
    "-extra_digits -fewer_digits -cropped -worst_quality "
    "-low_quality -normal_quality -jpeg_artifacts -signature "
    "-watermark -username -blurry"
)

# Rotate positives to avoid “same top few” posts
# NOTE: Preserving the exact behavior from your original file:
# these are missing commas on purpose (as in original), which concatenates strings.
PLAP_POSITIVE_SETS = [
    "sex_from_behind",
    "bent_over",
    "doggy_style",
    "mating_press",
    "standing_sex",
    "lifting_partner",
    "legs_over_head",
    "against_wall",
    "anal",
    "vaginal",
    "missionary",
    #"blush",
    "spooning",
    "grab_waist",
    "hair_pull",
    "looking_back",
    "mid_sex",
    "after_sex",
    "cum_inside",
    "creampie",
    "x-ray",
    "cross_section"
]

BOUNCE_POSITIVE_SETS = [
    "cowgirl",
    "riding",
    "sex_from_front",
    "reverse_cowgirl",
    "on_top",
    "straddling",
    "sitting_on_lap",
    "grinding",
    "female_on_top",
    "breast_press",
    "looking_down",
    "pushed_breasts",
    "nipples",
    "leaning_forward",
    "leaning_back",
    "hands_on_chest",
    "shimapan"
]

SUCC_POSITIVE_SETS = [
    "oral",
    "fellatio",
    "blowjob",
    "face_fucking",
    "deepthroat",
    "throat_fucking",
    "irrumatio",
    "cum_in_mouth",
    "saliva",
    "tongue_out",
    "messy_face",
    "hand_on_head",
    "looking_up",
    "cum_on_face",
    "open_mouth",
    "cheek_bulge"
]

# Rotate artist/style boosts (optional quality)
ARTIST_BOOSTS = [
    # "rikolo",
    # "nyl2",
    # "nyunnzi",
    # "exga",
    # "affect3d",
    # "lewdua",
    # "zer0",
    # "afrobull",
    # "bouquetman",
    # "aanix",
    # "grand_cupido",
]
