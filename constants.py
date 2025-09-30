import os

# ---------------------------
# Constants / config
# ---------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIRED_FIELDS = ("title", "price", "description", "images")  # minimal fields to proceed
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# SUPPORTED_MARKETPLACES = ["vinted", "wallapop", "milanuncios"]
# MARKETPLACE_PATTERNS = {
#     "vinted": ("vinted.",),
#     "wallapop": ("wallapop.",),
#     # add later: "milanuncios": ("milanuncios.",), "olx": ("olx.",)
# }
MARKETPLACES = {
    "vinted": {
        "patterns": ("vinted.",),
    },
    "wallapop": {
        "patterns": ("wallapop.",),
    },
    "milanuncios": {
        "patterns": ("milanuncios.",),
    },
    # "olx": {
    #     "patterns": ("olx.",),
    # },
}
ABORT_FLAG = False