import os

# ---------------------------
# Constants / config
# ---------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIRED_FIELDS = ("title", "price", "description", "images")  # minimal fields to proceed
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MARKETPLACES = {
    "vinted": {
        "patterns": ("vinted.",),
        "collector": None,  
        "checker": None,    
        "uploader": None,   
    },
    "wallapop": {
        "patterns": ("wallapop.",),
        "collector": None,  
        "checker": None,    
        "uploader": None,   
    },
    "milanuncios": {
        "patterns": ("milanuncios.",),
        "collector": None,
        "checker": None,
        "uploader": None,
    },
}

ABORT_FLAG = False


# ---------------------------
# Registration helper
# ---------------------------
def register_marketplace(name: str, collector=None, checker=None, uploader=None):
    """Register marketplace functions after they're imported."""
    if name in MARKETPLACES:
        if collector:
            MARKETPLACES[name]["collector"] = collector
        if checker:
            MARKETPLACES[name]["checker"] = checker
        if uploader:
            MARKETPLACES[name]["uploader"] = uploader