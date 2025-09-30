import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import time
import sys
import os
import traceback
import hashlib
import shutil
import threading
import keyboard
from difflib import SequenceMatcher
import pickle
import re
import io
try:
    from PIL import Image
except Exception:
    Image = None
try:
    import imagehash
    HAVE_IMAGEHASH = True
except Exception:
    HAVE_IMAGEHASH = False



# ---------------------------
# Constants / config
# ---------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_DIR = os.path.join(SCRIPT_DIR, "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)
SUPPORTED_MARKETPLACES = ["vinted", "wallapop", "milanuncios"]
REQUIRED_FIELDS = ("title", "price", "description", "images")  # minimal fields to proceed
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MARKETPLACE_PATTERNS = {
    "vinted": ("vinted.",),
    "wallapop": ("wallapop.",),
    # add later: "milanuncios": ("milanuncios.",), "olx": ("olx.",)
}
ABORT_FLAG = False


# ---------------------------
# Utilities
# ---------------------------

def vinted_title_shorten(raw_title: str) -> str:
    """Return substring up to the comma immediately before the first ':' if present,
       otherwise return the whole raw_title trimmed."""
    if not raw_title:
        return raw_title
    colon_idx = raw_title.find(":")
    if colon_idx == -1:
        return raw_title.strip()
    # find last comma before the colon
    comma_before = raw_title.rfind(",", 0, colon_idx)
    if comma_before != -1:
        return raw_title[:comma_before].strip()
    # fallback to up-to-colon (if no comma)
    return raw_title[:colon_idx].strip()

def save_cookies(driver, marketplace: str):
    path = os.path.join(COOKIES_DIR, f"{marketplace}_cookies.pkl")
    with open(path, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print(f"✅ Cookies saved for {marketplace}")

def load_cookies(driver, marketplace: str) -> bool:
    path = os.path.join(COOKIES_DIR, f"{marketplace}_cookies.pkl")
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            cookies = pickle.load(f)
    except (EOFError, pickle.UnpicklingError, Exception) as e:
        print(f"⚠️ Cookie file is empty or corrupted for {marketplace}: {e}")
        return False

    # map a sensible domain to visit first (so cookies can be added)
    domain_map = {
        "vinted": "https://www.vinted.es",
        "wallapop": "https://es.wallapop.com"
    }
    base = domain_map.get(marketplace, f"https://www.{marketplace}.com")
    try:
        driver.get(base)
        time.sleep(0.5)
    except Exception:
        # if navigating fails, still try to add cookies (some drivers accept it)
        pass

    for cookie in cookies:
        # sometimes Selenium/chrome is picky about cookie shape — try to add as-is, fallback to cleaned dict
        try:
            driver.add_cookie(cookie)
        except Exception:
            try:
                c = dict(cookie)
                # remove fields that Chrome may reject
                for k in ("sameSite", "same_site", "hostOnly"):
                    if k in c:
                        c.pop(k, None)
                driver.add_cookie(c)
            except Exception:
                continue
    return True

def safe_load_cookies(driver, marketplace: str) -> bool:
    """Try to load cookies, return True if successful, else open login flow."""
    try:
        loaded = load_cookies(driver, marketplace)
        if loaded:
            return True
        else:
            print(f"❌ No valid {marketplace} cookies. Logging in now...")
            driver.quit()  # close headless driver before manual login
            driver = ensure_logged_in(marketplace)
            return True
    except EOFError:
        print(f"⚠️ {marketplace.capitalize()} cookie file is empty or corrupted. Logging in now...")
        driver.quit()
        driver = ensure_logged_in(marketplace)
        return True
    except FileNotFoundError:
        print(f"❌ {marketplace.capitalize()} cookie file not found. Logging in now...")
        driver.quit()
        driver = ensure_logged_in(marketplace)
        return True
    except Exception as e:
        print(f"⚠️ Error checking cookies for {marketplace}: {e}")
        return False

def ensure_logged_in(driver, login_check_selector: str, homepage_url: str, cookie_file="cookies", force_visible_if_needed=True):
    """
    Always try cookies first. If not logged in:
      - If force_visible_if_needed=True: open a visible browser, wait for manual login,
        save cookies, and return False (so caller can retry headless).
      - If False: just return False.
    """
    if os.path.exists(cookie_file):
        load_cookies(driver, cookie_file)
        driver.get(homepage_url)
        time.sleep(3)
        if is_logged_in(driver, login_check_selector):
            print("🟢 Logged in using saved cookies.")
            return True

    if not force_visible_if_needed:
        print(f"❌ Not logged in for {homepage_url}. Please run once in visible mode first.")
        return False

    # Launch visible browser for manual login
    visible_driver = launch_driver()
    visible_driver.get(homepage_url)
    print(f"❗ Please log in manually on {homepage_url}. Press Enter here when done...")
    input()
    save_cookies(visible_driver, cookie_file)
    visible_driver.quit()
    print(f"⌛ Restarting headless session...")
    return False

def is_logged_in(driver, login_check_selector: str) -> bool:
    """Check if logged in by looking for an element that only exists when logged in."""
    try:
        driver.find_element(By.CSS_SELECTOR, login_check_selector)
        return True
    except:
        return False


def is_match(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Return True if two titles are similar enough (default ≥85%)."""
    if not title1 or not title2:
        return False
    ratio = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    return ratio >= threshold

def detect_marketplace(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for name, needles in MARKETPLACE_PATTERNS.items():
        if any(n in host for n in needles):
            return name
    return None

def download_image(url, folder="temp_images"):
    folder_path = os.path.join(SCRIPT_DIR, folder)
    os.makedirs(folder_path, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = url.split(".")[-1].split("?")[0]
    filename = f"{url_hash}.{ext}"
    path = os.path.join(folder_path, filename)
    if not os.path.exists(path):
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
    return path

# small in-memory cache to avoid repeated downloads of the same URL
_IMAGE_HASH_CACHE: dict[str, tuple[str | None, str | None]] = {}

def compute_image_hashes(url: str) -> tuple[str | None, str | None]:
    """
    Download image bytes and return (md5_hex, phash_hex_or_none).
    Uses imagehash.phash when available, otherwise falls back to a simple average-hash
    implemented with PIL. Returns (None, None) on failure.
    """
    if not url:
        return None, None

    # quick cache check
    if url in _IMAGE_HASH_CACHE:
        return _IMAGE_HASH_CACHE[url]

    try:
        # strip common tracking/query params as a first attempt (but keep fallback)
        tried_urls = [url]
        if "?" in url:
            tried_urls.insert(0, url.split("?", 1)[0])  # try without query first

        for u in tried_urls:
            try:
                resp = requests.get(u, timeout=10, headers=HEADERS)
                resp.raise_for_status()
                b = resp.content
                md5 = hashlib.md5(b).hexdigest()

                phash_hex = None
                if Image is not None:
                    try:
                        img = Image.open(io.BytesIO(b)).convert("RGB")
                        if HAVE_IMAGEHASH:
                            phash_hex = str(imagehash.phash(img))
                        else:
                            # fallback aHash (64-bit) using PIL only
                            small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
                            pixels = list(small.getdata())
                            avg = sum(pixels) / len(pixels)
                            bits = "".join("1" if p > avg else "0" for p in pixels)
                            phash_hex = hex(int(bits, 2))[2:].rjust(16, "0")
                    except Exception:
                        phash_hex = None

                _IMAGE_HASH_CACHE[url] = (md5, phash_hex)
                return md5, phash_hex
            except Exception:
                # try next candidate (e.g. stripped query)
                continue

    except Exception:
        pass

    _IMAGE_HASH_CACHE[url] = (None, None)
    return None, None

def hamming_distance_hex(h1: str | None, h2: str | None) -> int:
    if not h1 or not h2:
        return 9999
    try:
        i1 = int(h1, 16)
        i2 = int(h2, 16)
        return (i1 ^ i2).bit_count()  # Python 3.8+: .bit_count() is fast
    except Exception:
        return 9999

def remove_temp_folder(folder="temp_images", retries=5, delay=0.25):
    """
    Remove the temp images folder and its contents. On Windows a file can be briefly
    locked, so we retry a few times. Returns True if removed, False otherwise.
    """
    path = os.path.join(SCRIPT_DIR, folder)
    if not os.path.exists(path):
        return True  # already gone

    last_exc = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            # optionally recreate empty folder if you prefer:
            # os.makedirs(path, exist_ok=True)
            print(f"🧹 Cleaned temp folder: {path}")
            return True
        except Exception as e:
            last_exc = e
            time.sleep(delay)
    print(f"⚠️ Could not remove temp folder {path} after {retries} attempts. Error: {last_exc}")
    return False


def chrome_headless_options():
    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--disable-blink-features=AutomationControlled")
    o.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    o.add_experimental_option("useAutomationExtension", False)
    o.add_argument("--disable-gpu")
    o.add_argument("--log-level=3")
    o.add_argument("--silent")
    o.add_argument("--disable-logging")
    o.add_argument("--v=0")
    return o

def launch_driver():  # full Chrome (non-headless) with stealth profile for uploading
    chrome_options = Options()
    chrome_options.add_argument(r"--user-data-dir=C:\\SeleniumProfile")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--v=0")

    # Suppress chromedriver noise
    sys.stderr = open(os.devnull, "w")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    sys.stderr.close()
    sys.stderr = sys.__stderr__

    # Stealth
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    return driver

def headless_driver():
opts = chrome_headless_options()
sys.stderr = open(os.devnull, "w")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)
sys.stderr.close()
sys.stderr = sys.__stderr__
return driver


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
        print(f"⏭️ Skipping {m} (item already exists there)")

    if not destinations:
        print("❌ No available marketplaces left, item already exists everywhere.")
        return None

    print("Available destinations:")
    for i, dest in enumerate(destinations, 1):
        print(f"{i}. {dest}")

    choice = input("Choose destination marketplace: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(destinations)):
        print("❌ Invalid choice.")
        return None

    return destinations[int(choice) - 1]

def listen_for_abort():
    global ABORT_FLAG
    keyboard.add_hotkey("esc", lambda: set_abort()) # Esc will set a flag
    keyboard.wait() # Keep this thread alive

def set_abort():
    global ABORT_FLAG
    ABORT_FLAG = True
    print("\n⛔ ESC pressed. Aborting current run...")



# ---------------------------
# Collectors (read-only, scrape info from a URL)
# ---------------------------

def collect_listing(url: str) -> dict:
    src = detect_marketplace(url)
    if src == "vinted":
        return collect_from_vinted(url)
    elif src == "wallapop":
        return collect_from_wallapop(url)
        # future marketplaces:
        # elif src == "olx": ...
        # elif src == "milanuncios": ...
    else:
        print("❌ Marketplace not supported yet.")
        return {
            "source": None,
            "url": url,
            "title": None,
            "price": None,
            "description": None,
            "image_urls": [],
            "images": [],
            "md5": None,
            "phash": None,
        }
            

def collect_from_vinted(url: str) -> dict:
    """
    Collects listing data from a Vinted URL.
    Returns a dictionary with keys: title, price, description, images
    Missing elements are returned as None or empty list.
    """
    if ABORT_FLAG:
            return listing

    listing = {
        "source": "vinted",
        "url": url,
        "title": None,
        "price": None,
        "description": None,
        "image_urls": [],
        "images": [],
        "md5": None,
        "phash": None,
    }

    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"❌ Error loading Vinted page: {r.status_code}")
            return listing
        soup = BeautifulSoup(r.text, "html.parser")

        if ABORT_FLAG:
            return listing

        # 1) Text via requests
        title_tag = soup.find("h1")
        listing["title"] = title_tag.get_text(strip=True) if title_tag else None

        price_tag = soup.find("div", {"data-testid": "item-price"})
        listing["price"] = price_tag.get_text(strip=True) if price_tag else None

        desc_tag = soup.find("div", {"itemprop": "description"})
        listing["description"] = desc_tag.get_text(" ", strip=True) if desc_tag else None

        if ABORT_FLAG:
            return listing

        print(f'"Title: {listing["title"]}"\n"Price: {listing["price"]}"\n"Description: {listing["description"]}"')

        # 2) Images via Selenium (headless)
        print("⏳ Retrieving images (Vinted)...")
        d = headless_driver()
        try:
            d.get(url)
            time.sleep(3)
            if ABORT_FLAG:
                return listing
            try:
                first_img = d.find_element(By.CSS_SELECTOR, "img[data-testid^='item-photo']")
                d.execute_script("arguments[0].click();", first_img)
                time.sleep(0.5)
                seen = set()
                for img in d.find_elements(By.CSS_SELECTOR, "img[data-testid='image-carousel-image-shown'], img[data-testid='image-carousel-image']"):
                    src = img.get_attribute("src")
                    if src and src not in seen:
                        listing["image_urls"].append(src)
                        seen.add(src)
            except Exception:
                print("⚠️ No image carousel found, skipping images.")
        finally:
            d.quit()

        if ABORT_FLAG:
            return listing

        listing["images"] = [os.path.abspath(download_image(u)) for u in listing["image_urls"]]
        if listing["images"]:
            print(f"✅ Downloaded {len(listing['images'])} images")
        else:
            print("❌ No images downloaded.")

        # 3) Image hash (first image)
        if listing["image_urls"]:
            md5, phash = compute_image_hashes(listing["image_urls"][0])
            listing["md5"] = md5
            listing["phash"] = phash
        else:
            listing["md5"] = None
            listing["phash"] = None

    except Exception as e:
        print(f"⚠️ Error collecting from Vinted: {e}")

    if ABORT_FLAG:
        return listing

    return listing


def collect_from_wallapop(url: str) -> dict:
    """
    Collects listing data from a Wallapop URL.
    Returns a dictionary with keys: title, price, description, images
    Missing elements are returned as None or empty list.
    """
    listing = {
        "source": "wallapop",
        "url": url,
        "title": None,
        "price": None,
        "description": None,
        "image_urls": [],
        "images": [],
        "md5": None,
        "phash": None,
    }

    if ABORT_FLAG:
        return listing

    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"❌ Error loading Wallapop page: {r.status_code}")
            return listing
        soup = BeautifulSoup(r.text, "html.parser")
    
        if ABORT_FLAG:
            return listing

        # 1) Text via requests
        title_tag = soup.find("h1")
        listing["title"] = title_tag.get_text(strip=True) if title_tag else None

        price_tag = soup.find("span", {"class": lambda x: x and "Price" in x})
        listing["price"] = price_tag.get_text(strip=True) if price_tag else None

        desc_meta = soup.find("meta", attrs={"name": "og:description"})
        listing["description"] = desc_meta["content"].strip() if desc_meta else None

        print(f'"Title: {listing["title"]}"\n"Price: {listing["price"]}"\n"Description: {listing["description"]}"')

        if ABORT_FLAG:
            return listing

        # 2) Images via Selenium (headless)
        print("⏳ Retrieving images (Wallapop)...")
        d = headless_driver()
        try:
            d.get(url)
            time.sleep(3)

            if ABORT_FLAG:
                return listing

            seen = set()
            for img in d.find_elements(By.CSS_SELECTOR, "img"):
                src = img.get_attribute("src")
                if src and "cdn.wallapop.com" in src and "W640" in src:
                    if src not in seen:
                        listing["image_urls"].append(src)
                        seen.add(src)
        except Exception as e:
            print(f"⚠️ Error retrieving Wallapop images: {e}")
        finally:
            d.quit()

        if ABORT_FLAG:
            return listing

        listing["images"] = [os.path.abspath(download_image(u)) for u in listing["image_urls"]]
        if listing["images"]:
            print(f"✅ Downloaded {len(listing['images'])} images")
        else:
            print("❌ No images downloaded.")

        # 3) Image hash (first image)
        if listing["image_urls"]:
            md5, phash = compute_image_hashes(listing["image_urls"][0])
            listing["md5"] = md5
            listing["phash"] = phash
        else:
            listing["md5"] = None
            listing["phash"] = None

    except Exception as e:
        print(f"⚠️ Error collecting from Wallapop: {e}")

    if ABORT_FLAG:
        return listing

    return listing



# ---------------------------
# Marketplace checkers (read-only, scrape/check your own listings for duplicates)
# ---------------------------

def check_wallapop(listing) -> str | None:
    """Return URL if the listing exists in Wallapop account (headless)."""
    try:
        driver = headless_driver()
        safe_load_cookies(driver, "wallapop")  # will log in if cookies missing
        driver.get("https://es.wallapop.com/app/catalog/published")
        time.sleep(3)

        # Scroll to load all items
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Collect items
        items = driver.find_elements(By.CSS_SELECTOR, "tsl-catalog-item a.item-details")
        print(f"🟢 Found {len(items)} items on Wallapop profile.")

        # --- Step 1: Check by title ---
        for item in items:
            try:
                title = item.find_element(By.CSS_SELECTOR, ".info-title").text.strip()
                href = item.get_attribute("href")
                if is_match(listing["title"], title):
                    print(f"✅ Match found by title: {title} -> {href}")
                    return href
            except Exception as e:
                print(f"⚠️ Title parse error: {e}")
                continue

        # --- Step 2: Check by image hashes, if title check failed ---
        for item in items:
            try:
                href = item.get_attribute("href")
                parent = item.find_element(By.XPATH, "./ancestor::div[contains(@class, 'row')]")
                avatar_divs = parent.find_elements(By.CSS_SELECTOR, "div.ItemAvatar")
                for avatar in avatar_divs:
                    style = avatar.get_attribute("style")
                    if "url(" in style:
                        match = re.search(r'url\([\"]?([^\")]+)', style)
                        if match:
                            img_url = match.group(1)
                            cand_md5, cand_phash = compute_image_hashes(img_url.split("?")[0])

                            if listing.get("md5") and cand_md5 and listing["md5"] == cand_md5:
                                print(f"✅ Exact md5 match: {href}")
                                return href

                            phash_a = listing.get("phash")
                            phash_b = cand_phash
                            if phash_a and phash_b:
                                ham = hamming_distance_hex(phash_a, phash_b)
                                if ham <= 6:  # tweak threshold if needed
                                    print(f"✅ Perceptual match (hamming={ham}): {href}")
                                    return href

            except Exception as e:
                print(f"⚠️ Item parse error (image check): {e}")
                continue

    except Exception as e:
        print(f"⚠️ Wallapop check error: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return None

def check_vinted(listing) -> str | None:
    """Return URL if the listing exists in Vinted account (headless)."""
    driver = None
    try:
        homepage_url = "https://www.vinted.es/"
        login_check_selector = "button#user-menu-button"  # appears only if logged in
        cookie_file = "vinted"

        # Step 1: Open homepage to extract user_id
        driver = headless_driver()
        logged_in = ensure_logged_in(driver, login_check_selector, homepage_url, cookie_file, force_visible_if_needed=True)

        if not logged_in:
            driver.quit() # Close failed headless driver
            driver = headless_driver() # Relaunch headless driver with fresh cookies
            load_cookies(driver, cookie_file)
            driver.get(homepage_url)
            time.sleep(3)

        html = driver.page_source
        m = re.search(r'"userId":"?(\d+)"?', html) or re.search(r'consentId=(\d+)', html)
        user_id = m.group(1) if m else None
        if not user_id:
            print("❌ Could not find Vinted user ID. Are you logged in?")
            return None
        else:
            print(f"🟢 Found Vinted user ID: {user_id}")

        # Open listings page
        listings_url = f"https://www.vinted.es/member/{user_id}"
        driver.get(listings_url)
        time.sleep(3)

        # Scroll to load all items
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Collect items
        items = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='grid-item']")
        if not items:
            print("❌ No listings found on Vinted.")
            return None
        print(f"🟢 Found {len(items)} listings on Vinted profile.")


        # --- Step 1: Check by title ---
        for item in items:
            try:
                overlay = item.find_element(By.CSS_SELECTOR, "a.new-item-box__overlay--clickable")
                raw_title = overlay.get_attribute("title").strip()
                short_title = vinted_title_shorten(raw_title)  # ✅ use helper here
                href = overlay.get_attribute("href")

                # DEBUG PRINTS
                print(f"🟢 Found item: raw_title='{raw_title}', short_title='{short_title}', href='{href}'")
                print(f"Comparing with listing title: '{listing['title']}'")
                ratio = SequenceMatcher(None, listing["title"].lower(), short_title.lower()).ratio()
                print(f"Similarity ratio: {ratio:.2f}")

                if is_match(listing["title"], short_title):
                    print(f"✅ Match found by title: {short_title} -> {href}")
                    return href
            except Exception as e:
                print(f"⚠️ Title parse error: {e}")
                continue

        # --- Step 2: Check by image hashes, if title check failed ---
        for item in items:
            try:
                overlay = item.find_element(By.CSS_SELECTOR, "a.new-item-box__overlay--clickable")
                href = overlay.get_attribute("href")
                img_elem = item.find_element(By.CSS_SELECTOR, "img.web_ui__Image__content")
                img_url = img_elem.get_attribute("src").split("?")[0]

                cand_md5, cand_phash = compute_image_hashes(img_url)

                # DEBUG PRINTS
                print(f"🖼️ Found item image: {img_url}")
                print(f"Listing md5: {listing.get('md5')}, candidate md5: {cand_md5}")
                print(f"Listing phash: {listing.get('phash')}, candidate phash: {cand_phash}")

                if listing.get("md5") and cand_md5 and listing["md5"] == cand_md5:
                    print(f"✅ Exact md5 match: {href}")
                    return href

                phash_a = listing.get("phash")
                phash_b = cand_phash
                if phash_a and phash_b:
                    ham = hamming_distance_hex(phash_a, phash_b)
                    print(f"Hamming distance: {ham}")
                    if ham <= 6:
                        print(f"✅ Perceptual match (hamming={ham}): {href}")
                        return href

            except Exception as e:
                print(f"⚠️ Item parse error (image check): {e}")
                continue

    except Exception as e:
        print(f"⚠️ Vinted check error: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return None


def check_existing_in_other_marketplaces(listing: dict):
    title = listing.get("title")
    first_img = listing["images"][0] if listing["images"] else None

    for marketplace in SUPPORTED_MARKETPLACES:
        if marketplace == listing["source"]:
            continue

        print(f"🔍 Checking on {marketplace.capitalize()}...")

        found_url = None
        if marketplace == "wallapop":
            found_url = check_wallapop(listing)
        elif marketplace == "vinted":
            found_url = check_vinted(listing)
        # else:
        #     found_url = fake_check_marketplace(marketplace, title, first_img)

        if found_url:
            listing["exists_in"][marketplace] = found_url
            print(f"✅ Already exists on {marketplace}: {found_url}")
        else:
            listing["exists_in"][marketplace] = None
            print(f"❌ Not found on {marketplace}")



# ---------------------------
# Uploaders (write, push new listings)
# ---------------------------

def upload_listing(destination: str, listing: dict):
    if destination == "vinted":
        return upload_to_vinted(listing)
    elif destination == "wallapop":
        return upload_to_wallapop(listing)
    # future marketplaces:
    # elif destination == "olx": ...
    # elif destination == "milanuncios": ...
    else:
        print("❌ Marketplace not supported yet.")
        return None

def upload_to_vinted(listing: dict):
    driver = None
    print("⏳ Opening Vinted upload page...")
    driver = launch_driver()
    driver.get("https://www.vinted.es/items/new")
    time.sleep(5)

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # Login check
    if "member/signup" in driver.current_url:
        print("❌ Not logged in. Please log in manually in the opened browser.")
        input("Press Enter after logging in to continue...")
        driver.get("https://www.vinted.es/items/new")
        time.sleep(3)

    # Images
    print("⏳ Uploading images...")
    try:
        driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys("\n".join(listing["images"]))
        print("✅ Images uploaded")
    except Exception as e:
        print("⚠️ Error uploading images:", e)
        input("👉 Fix images manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # Title
    try:
        ti = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "title")))
        ti.clear()
        ti.send_keys(listing["title"])
        print("✅ Title filled")
    except Exception as e:
        print("⚠️ Title not filled automatically:", e)
        input("👉 Fill title manually, then press Enter to continue...")

    # Description
    try:
        di = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "description")))
        di.clear()
        di.send_keys(listing["description"])
        print("✅ Description filled")
    except Exception as e:
        print("⚠️ Description not filled automatically:", e)
        input("👉 Fill description manually, then press Enter to continue...")

    # Price
    try:
        price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
        pi = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "price")))
        pi.clear()
        pi.send_keys(price_cleaned)
        print("✅ Price filled")
    except Exception as e:
        print("⚠️ Price not filled automatically:", e)
        input("👉 Fill price manually, then press Enter to continue...")

    # Category (first suggestion)
    try:
        ci = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "category")))
        ci.click()
        time.sleep(0.5)
        fs = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[id^='catalog-suggestion-']")))
        fs.click()
        print("✅ First category selected")
    except Exception as e:
        print("⚠️ Category not selected automatically:", e)
        input("👉 Select category manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    print("🎉 Vinted upload step complete. Review and publish manually if needed.")

    return driver

def upload_to_wallapop(listing: dict):
    driver = None
    print("⏳ Opening Wallapop upload page...")
    driver = launch_driver()
    driver.get("https://es.wallapop.com/app/catalog/upload/consumer-goods")
    time.sleep(5)

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # Login check
    if "login?redirectUrl" in driver.current_url:
        print("❌ Not logged in. Please log in manually in the opened browser.")
        input("Press Enter after logging in to continue...")
        driver.get("https://es.wallapop.com/app/catalog/upload/consumer-goods")
        time.sleep(3)

    # Title
    try:
        title_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "summary")))
        title_input.clear()
        title_input.send_keys(listing["title"])
        print("✅ Title filled")
    except Exception as e:
        print("⚠️ Could not fill title automatically:", e)
        input("👉 Fill the title manually, then press Enter to continue...")

    # "Continuar"
    try:
        continuar_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "walla-button[data-testid='continue-button']"))
        )
        continuar_btn.click()
        print("✅ Clicked 'Continuar'")
    except Exception as e:
        print("⚠️ Could not click 'Continuar':", e)
        input("👉 Click 'Continuar' manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # Images
    print("⏳ Uploading images...")
    time.sleep(2)
    try:
        driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys("\n".join(listing["images"]))
        print("✅ Images uploaded")
    except Exception as e:
        print("⚠️ Error uploading images:", e)
        input("👉 Upload images manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # "Continuar" again
    try:
        continuar_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "walla-button[data-testid='continue-button']"))
        )
        continuar_buttons[-1].click()
        print("✅ Clicked 'Continuar'")
    except Exception as e:
        print("⚠️ Could not click 'Continuar':", e)
        input("👉 Click 'Continuar' manually, then press Enter to continue...")

    # Category
    try:
        category_dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[role="listbox"][aria-label="Categoría y subcategoría"]'))
        )
        category_dropdown.click()
        print("✅ Opened the category dropdown")
    except Exception as e:
        print("⚠️ Error opening category dropdown:", e)
        input("👉 Open/select category manually, then press Enter to continue...")

    time.sleep(1)

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    try:
        first_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.sc-walla-dropdown-item"))
        )
        first_option.click()
        print("✅ First category selected")
    except Exception as e:
        print("⚠️ Error selecting category:", e)
        input("👉 Select category manually, then press Enter to continue...")

    # Description (AI keep/replace)
    try:
        description_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "description")))
        current_ai = description_input.get_attribute("value").strip()

        print("\n📝 Wallapop AI-generated description:\n---\n" + current_ai + "\n---")
        print("\n📝 Scraped description:\n---\n" + listing["description"] + "\n---")
        choice = input("Keep AI (k) or Replace with scraped (r)? (k/r): ").strip().lower()
        if choice == "r":
            description_input.clear()
            description_input.send_keys(listing["description"])
            print("✅ Scraped description used")
        else:
            print("✅ Kept AI description")
    except Exception as e:
        print("⚠️ Could not process description automatically:", e)
        input("👉 Fill/verify the description manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    # Price
    try:
        price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
        price_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "sale_price")))
        price_input.clear()
        price_input.send_keys(price_cleaned)
        print("✅ Price filled")
    except Exception as e:
        print("⚠️ Error filling price:", e)
        input("👉 Fill price manually, then press Enter to continue...")

    if ABORT_FLAG:
        try:
            if driver:
                driver.quit()
        except NameError:
            print("driver was never created")
            pass
        except Exception:
            print("driver exists but is already closed or invalid")
            pass
        try:
            remove_temp_folder("temp_images")
        except Exception as e:
            print("⚠️ Error while cleaning temp folder:", e)
        return driver

    print("🎉 Wallapop upload step complete. Review and publish manually.")

    return driver



# ---------------------------
# Main loop
# ---------------------------

if __name__ == "__main__":
    threading.Thread(target=listen_for_abort, daemon=True).start()
    while True:
        driver = None
        try:
            if ABORT_FLAG:
                continue

            # Step 0: Ensure logged in to each marketplace before starting loop
            for mp in SUPPORTED_MARKETPLACES:
                cookie_file = os.path.join(COOKIES_DIR, f"{mp}_cookies.pkl")
                if not os.path.exists(cookie_file):
                    print(f"🚨 No saved cookies for {mp}. You need to log in first.")
                    driver = ensure_logged_in(mp)
                    driver.quit()

            # Step 1: Collect
            source_url = input("\nEnter the listing URL: ").strip()
            source = detect_marketplace(source_url)
            if not source:
                print("❌ Could not detect marketplace from URL.")
                continue

            listing = collect_listing(source_url)
            if not check_required(listing): # Validate required fields, if missing, goes back to again step
                continue

            if ABORT_FLAG:
                continue

            # Step 1.5: Check if it already exists elsewhere
            listing["exists_in"] = {} # prepare holder
            check_existing_in_other_marketplaces(listing)

            if ABORT_FLAG:
                continue

            # Step 2: Choose destination (exclude source)
            destination = choose_destination(listing["source"], listing)
            if not destination:
                continue

            if ABORT_FLAG:
                continue

            # Step 3: Upload to destination
            driver = upload_listing(destination, listing)

        except Exception as e:
            print("\n❌ An error occurred:", e)
            traceback.print_exc()
        finally:
            ABORT_FLAG = False  # reset for next loop
            again = input("\nDo you want to submit another listing? (y/n): ").strip().lower()
                
            # Close driver
            try:
                if driver:
                    driver.quit()
            except NameError:
                print("driver was never created")
                pass
            except Exception:
                print("driver exists but is already closed or invalid")
                pass

            # Cleanup temp images
            try:
                remove_temp_folder("temp_images")
            except Exception as e:
                print("⚠️ Error while cleaning temp folder:", e)

            if again != "y":
                break       

            
