from urllib.parse import urlparse

from constants import SUPPORTED_MARKETPLACES, REQUIRED_FIELDS, MARKETPLACE_PATTERNS
from helpers.abort import check_abort
from marketplaces.vinted import collect_from_vinted, check_on_vinted, upload_to_vinted
from marketplaces.wallapop import collect_from_wallapop, check_on_wallapop, upload_to_wallapop



# ---------------------------
# Required field checking & choosing marketplaces
# ---------------------------
def detect_marketplace(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for name, needles in MARKETPLACE_PATTERNS.items():
        if any(n in host for n in needles):
            return name
    return None

def check_required(listing: dict) -> bool:
    missing = [k for k in REQUIRED_FIELDS if not listing.get(k)]
    if missing:
        print("❌ Missing required fields:", ", ".join(missing))
        return False
    return True

def choose_destination(source, listing):
    # Start with all possible destinations except the source
    destinations = [m for m in SUPPORTED_MARKETPLACES if m != source]
    skipped = []

    # Remove marketplaces where this item was already found
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

def collect_listing(url: str, source: str) -> dict:
    if source == "vinted":
        return collect_from_vinted(url)
    elif source == "wallapop":
        return collect_from_wallapop(url)
    # future marketplaces:
    # elif src == "olx": ...
    # elif src == "milanuncios": ...
    else:
        print("❌ Marketplace not supported yet.")
        return {
            "url": url,
            "source": None,
            "title": None,
            "price": None,
            "description": None,
            "image_urls": [],
            "images": [],
            "md5": None,
            "phash": None,
        }
   


def check_existing_in_other_marketplaces(listing: dict):
    title = listing.get("title")
    first_img = listing["images"][0] if listing["images"] else None

    for marketplace in SUPPORTED_MARKETPLACES:
        if marketplace == listing["source"]:
            continue

        found_url = None
        if marketplace == "wallapop":
            found_url = check_on_wallapop(listing)
        elif marketplace == "vinted":
            found_url = check_on_vinted(listing)
        # else:
        #     found_url = fake_check_marketplace(marketplace, title, first_img)

        if check_abort(): 
            return None

        if found_url:
            listing["exists_in"][marketplace] = found_url
            print(f"✅ Already exists on {marketplace.capitalize()}: {found_url}")
        else:
            listing["exists_in"][marketplace] = None
            print(f"❌ Not found on {marketplace.capitalize()}")

def upload_listing(destination: str, listing: dict):
    if destination == "vinted":
        return upload_to_vinted(listing)
    elif destination == "wallapop":
        return upload_to_wallapop(listing)
    # future marketplaces:
    # elif destination == "olx": ...
    # elif destination == "milanuncios": ...
    else:
        print(f"❌ {destination.capitalize()} marketplace not supported yet.")
        return None

