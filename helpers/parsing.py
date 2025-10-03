from urllib.parse import urlparse

from constants import MARKETPLACES, REQUIRED_FIELDS
from helpers.abort import check_abort



# ---------------------------
# Collect
# ---------------------------
def detect_marketplace(url: str) -> str | None:
    """Detect marketplace from URL using patterns in MARKETPLACES config."""
    host = urlparse(url).netloc.lower()
    for name, config in MARKETPLACES.items():
        patterns = config.get("patterns", ())
        if any(pattern in host for pattern in patterns):
            return name
    return None

def check_required(listing: dict) -> bool:
    """Verify all required fields are present in listing."""
    if not listing:  # catches None or empty dict
        return False

    missing = [k for k in REQUIRED_FIELDS if not listing.get(k)]
    if missing:
        print("❌ Missing required fields:", ", ".join(missing))
        return False
    return True

def collect_listing(url: str, source: str) -> dict:    
    """Collect listing details using the registered collector function."""
    config = MARKETPLACES.get(source)
    
    if not config:
        print(f"❌ Unknown marketplace: {source}")
        return _empty_listing(url, source)
    
    collector = config.get("collector")
    
    if not collector:
        print(f"❌ Collector not implemented for {source.capitalize()}")
        return _empty_listing(url, source)
    
    return collector(url)
   

# ---------------------------
# Checker
# ---------------------------
def check_existing_in_other_marketplaces(listing: dict):
    """Check if listing exists in other marketplaces using registered checker functions."""
    source = listing.get("source")
    
    for marketplace, config in MARKETPLACES.items():
        if marketplace == source:
            continue
        
        checker = config.get("checker")
        if not checker:
            print(f"⚠️ Checker not implemented for {marketplace.capitalize()}, skipping...")
            continue
        
        found_url = checker(listing)
        
        if check_abort():
            return None
        
        if found_url:
            listing["exists_in"][marketplace] = found_url
            print(f"✅ Already exists on {marketplace.capitalize()}: {found_url}")
        else:
            listing["exists_in"][marketplace] = None
            print(f"❌ Not found on {marketplace.capitalize()}")


# ---------------------------
# Uploader
# ---------------------------
def choose_destination(source: str, listing: dict) -> str | None:
    """Let user choose a destination marketplace, excluding source and existing."""
    # Get all marketplaces except source
    destinations = [m for m in MARKETPLACES.keys() if m != source]
    skipped = []

    # Remove marketplaces where item already exists
    if "exists_in" in listing:
        filtered = []
        for m in destinations:
            if listing["exists_in"].get(m, False):
                skipped.append(m)
            else:
                filtered.append(m)
        destinations = filtered

    # Show skipped marketplaces
    for m in skipped:
        print(f"⏭️ Skipping {m.capitalize()}, item already exists there.")

    if not destinations:
        print("❌ No available marketplaces left, item already exists everywhere.")
        return None

    print("Available destinations:")
    for i, dest in enumerate(destinations, 1):
        print(f"{i}. {dest.capitalize()}")

    choice = input("Choose destination marketplace: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(destinations)):
        print("❌ Invalid choice.")
        return None

    return destinations[int(choice) - 1]

def upload_listing(destination: str, listing: dict):
    """Upload listing using the registered uploader function."""
    config = MARKETPLACES.get(destination)
    
    if not config:
        print(f"❌ Unknown marketplace: {destination}")
        return None
    
    uploader = config.get("uploader")
    
    if not uploader:
        print(f"❌ Uploader not implemented for {destination.capitalize()}")
        return None
    
    return uploader(listing)



def _empty_listing(url: str, source: str | None) -> dict:
    """Return an empty listing structure."""
    return {
        "url": url,
        "source": source,
        "title": None,
        "price": None,
        "description": None,
        "images": [],
        "md5": None,
        "phash": None,
    }