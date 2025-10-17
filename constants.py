import os

# ---------------------------
# Constants / config
# ---------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIRED_FIELDS = ("title", "price", "description", "images")  # minimal fields to proceed
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
MARKETPLACES = {
    "vinted": {
        "patterns": ("vinted.",),
        "config": None,
        "collector": None,  
        "checker": None,    
        "uploader": None,   
    },
    "wallapop": {
        "patterns": ("wallapop.",),
        "config": None,
        "collector": None,  
        "checker": None,    
        "uploader": None,   
    },
    "milanuncios": {
        "patterns": ("milanuncios.",),
        "config": None,
        "collector": None,
        "checker": None,
        "uploader": None,
    },
}

ABORT_FLAG = False


# ---------------------------
# Registration helper
# ---------------------------
def register_marketplace(name: str, config: dict = None, collector=None, checker=None, uploader=None):
    """
    Register marketplace with its config (selectors, URLs, extractors, etc.) and functions.
    
    Args:
        name: Marketplace name
        config: Dict containing all marketplace-specific configuration
        collector, checker, uploader: Function references
    """
    if name in MARKETPLACES:
        if config:
            MARKETPLACES[name]["config"] = config
        if collector:
            MARKETPLACES[name]["collector"] = collector
        if checker:
            MARKETPLACES[name]["checker"] = checker
        if uploader:
            MARKETPLACES[name]["uploader"] = uploader