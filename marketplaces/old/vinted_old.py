import os, re, time, requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from constants import HEADERS
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.abort import check_abort
from helpers.utils import is_match, vinted_title_shorten, scroll_to_load_all_items
from helpers.images import download_image, compute_image_hashes, hamming_distance_hex, remove_temp_folder



# ---------------------------
# CSS Selectors & URLs
# ---------------------------
MARKETPLACE = "vinted"
HOME_URL = "https://www.vinted.es/"
PROFILE_URL = "https://www.vinted.es/member/"
UPLOAD_URL = "https://www.vinted.es/items/new"
LOGIN_SELECTOR = "button#user-menu-button"
COL_ITEM_HTML_TITLE = "h1"
COL_ITEM_HTML_PRICE = ["div", "data-testid", "item-price"]
COL_ITEM_HTML_DESCRIPTION = ["div", "itemprop", "description"]
COL_ITEM_FIRST_IMG = "img[data-testid^='item-photo']"
COL_ITEM_CAROUSEL_IMGS = "img[data-testid='image-carousel-image-shown'], img[data-testid='image-carousel-image']"
SEL_PROFILE_ITEMS = "div[data-testid='grid-item']"
SEL_PROFILE_OVERLAY = "a.new-item-box__overlay--clickable"
SEL_PROFILE_IMG = "img.web_ui__Image__content"
SEL_UPLOAD_TITLE = "title"
SEL_UPLOAD_DESCRIPTION = "description"
SEL_UPLOAD_PRICE = "price"
SEL_UPLOAD_CATEGORY = "category"
SEL_UPLOAD_CATEGORY_OPTION = "[id^='catalog-suggestion-']"
SEL_UPLOAD_FILE = 'input[type="file"]'



# ---------------------------
# Collector (read-only, scrape info from a URL)
# ---------------------------
def collect_from_vinted(url: str) -> dict:
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

    if check_abort(): 
        return None

    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"❌ Error loading Vinted page: {r.status_code}")
            return listing
        soup = BeautifulSoup(r.text, "html.parser")

        # Text
        title_tag = soup.find(COL_ITEM_HTML_TITLE)
        listing["title"] = title_tag.get_text(strip=True) if title_tag else None
        price_tag = soup.find(COL_ITEM_HTML_PRICE[0], {COL_ITEM_HTML_PRICE[1]: COL_ITEM_HTML_PRICE[2]})
        listing["price"] = price_tag.get_text(strip=True) if price_tag else None
        desc_tag = soup.find(COL_ITEM_HTML_DESCRIPTION[0], {COL_ITEM_HTML_DESCRIPTION[1]: COL_ITEM_HTML_DESCRIPTION[2]})
        listing["description"] = desc_tag.get_text(" ", strip=True) if desc_tag else None

        if check_abort(): 
            return None

        print(f'\n---\n"Title: {listing["title"]}"\n"Price: {listing["price"]}"\n"Description: {listing["description"]}"\n---')

        # Images
        print(f"🌍 Opening {MARKETPLACE.capitalize()} listing...")
        d = headless_driver()
        print("⏳ Retrieving images...")
        try:
            d.get(url)
            time.sleep(3)

            if check_abort(): 
                return None

            try:
                first_img = d.find_element(By.CSS_SELECTOR, COL_ITEM_FIRST_IMG)
                d.execute_script("arguments[0].click();", first_img)
                time.sleep(0.5)
                seen = set()
                for img in d.find_elements(By.CSS_SELECTOR, COL_ITEM_CAROUSEL_IMGS):
                    src = img.get_attribute("src")
                    if src and src not in seen:
                        listing["image_urls"].append(src)
                        seen.add(src)
            except Exception as e:
                print(f"⚠️ Error retrieving Vinted listing's images: {e}")
        finally:
            d.quit()

        if check_abort(): 
            return None

        listing["images"] = [os.path.abspath(download_image(u)) for u in listing["image_urls"]]
        if listing["images"]:
            print(f"✅ Downloaded {len(listing['images'])} images")
        else:
            print("❌ No images downloaded.")

        # Image hash (first image)
        if listing["image_urls"]:
            listing["md5"], listing["phash"] = compute_image_hashes(listing["image_urls"][0])

    except Exception as e:
        print(f"⚠️ Error collecting listing details from Vinted: {e}")
        return []

    if check_abort(): 
        return None

    return listing


# ---------------------------
# Checker
# ---------------------------
def check_vinted(listing) -> str | None:
    """Return URL if the listing exists in Vinted account (headless)."""
    driver = None
    try:
        # Open homepage to extract user_id
        print(f"🔍 Checking if listing exists on {MARKETPLACE.capitalize()}...")
        driver = headless_driver()
        driver = ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE) # override drive in case logged out
        if not driver:
            print(f"❌ Could not log in. Aborting check on {MARKETPLACE.capitalize()}...")
            return None
        html = driver.page_source
        m = re.search(r'"userId":"?(\d+)"?', html) or re.search(r'consentId=(\d+)', html)
        if m:
            user_id = m.group(1) 
            print(f"🟢 Found Vinted user ID: {user_id}")
        else:
            print("❌ Could not find Vinted user ID even after login.")
            driver.quit()
            return None

        if check_abort(driver): 
            return None

        # Open profile listings page
        driver.get(f"{PROFILE_URL}{user_id}")
        time.sleep(3)

        if check_abort(driver): 
            return None

        # Scroll and find all items
        print("⏳ Scrolling profile page to load all listings...")
        items = scroll_to_load_all_items(driver, SEL_PROFILE_ITEMS)
        if not items:
            print(f"❌ No listings found on {MARKETPLACE.capitalize()}.")
            return None
        print(f"🟢 Found {len(items)} listings on {MARKETPLACE.capitalize()} profile.")

        if check_abort(driver): 
            return None

        # --- Step 1: Check by title ---
        print("🔍 Checking listings by title to find a match...")
        for item in items:
            try:
                overlay = item.find_element(By.CSS_SELECTOR, SEL_PROFILE_OVERLAY)
                raw_title = overlay.get_attribute("title").strip()
                short_title = vinted_title_shorten(raw_title)
                href = overlay.get_attribute("href")

                # DEBUG PRINTS
                # print(f"🟢 Found item: raw_title='{raw_title}', short_title='{short_title}', href='{href}'")
                # print(f"Comparing with listing title: '{listing['title']}'")
                # ratio = SequenceMatcher(None, listing["title"].lower(), short_title.lower()).ratio()
                # print(f"Similarity ratio: {ratio:.2f}")

                if is_match(listing["title"], short_title):
                    print(f"✅ Match found by title: {short_title} -> {href}")
                    return href
            except Exception as e:
                print(f"⚠️ Title parse error: {e}")
                continue

            if check_abort(driver): 
                return None

        # --- Step 2: Check by image hashes, if title check failed ---
        print("🔍 No title match found, checking by image hashes...")
        for item in items:
            try:
                overlay = item.find_element(By.CSS_SELECTOR, SEL_PROFILE_OVERLAY)
                href = overlay.get_attribute("href")
                img_elem = item.find_element(By.CSS_SELECTOR, SEL_PROFILE_IMG)
                img_url = img_elem.get_attribute("src").split("?")[0]

                cand_md5, cand_phash = compute_image_hashes(img_url)

                # DEBUG PRINTS
                # print(f"🖼️ Found item image: {img_url}")
                # print(f"Listing md5: {listing.get('md5')}, candidate md5: {cand_md5}")
                # print(f"Listing phash: {listing.get('phash')}, candidate phash: {cand_phash}")

                if listing.get("md5") and cand_md5 and listing["md5"] == cand_md5:
                    print(f"✅ Exact md5 match: {href}")
                    return href
                if listing.get("phash") and cand_phash:
                    ham = hamming_distance_hex(listing.get("phash"), cand_phash)
                    if ham <= 6:  # tweak threshold if needed
                        print(f"✅ Perceptual match (hamming={ham}): {href}")
                        return href

            except Exception as e:
                print(f"⚠️ Item parse error (image check): {e}")
                continue

            if check_abort(driver): 
                return None

    except Exception as e:
        print(f"⚠️ {MARKETPLACE.capitalize()} check error: {e}")
        return None
    finally:
        if check_abort(driver): 
            return None
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return None


# ---------------------------
# Uploader (write, push new listings)
# ---------------------------
def upload_to_vinted(listing: dict):
    driver = None
    try:
        print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
        driver = visible_driver()
        ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
        driver.get(UPLOAD_URL)
        time.sleep(5)

        if check_abort(driver): 
            return None

        # Images
        print("⏳ Uploading images...")
        try:
            driver.find_element(By.CSS_SELECTOR, SEL_UPLOAD_FILE).send_keys("\n".join(listing["images"]))
            print("✅ Images uploaded")
        except Exception as e:
            print("⚠️ Error uploading images:", e)
            input("👉 Fix images manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        # Title
        try:
            title_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_TITLE)))
            title_input.clear()
            title_input.send_keys(listing["title"])
            print("✅ Title filled")
        except Exception as e:
            print("⚠️ Title not filled automatically:", e)
            input("👉 Fill title manually, then press Enter to continue...")

        # Description
        try:
            description_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_DESCRIPTION)))
            description_input.clear()
            description_input.send_keys(listing["description"])
            print("✅ Description filled")
        except Exception as e:
            print("⚠️ Description not filled automatically:", e)
            input("👉 Fill description manually, then press Enter to continue...")

        # Price
        try:
            price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
            price_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_PRICE)))
            price_input.clear()
            price_input.send_keys(price_cleaned)
            print("✅ Price filled")
        except Exception as e:
            print("⚠️ Price not filled automatically:", e)
            input("👉 Fill price manually, then press Enter to continue...")

        # Category (first suggestion)
        try:
            category_dropdown = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, SEL_UPLOAD_CATEGORY)))
            category_dropdown.click()
            time.sleep(0.5)
            first_option = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_UPLOAD_CATEGORY_OPTION)))
            first_option.click()
            print("✅ First category selected")
        except Exception as e:
            print("⚠️ Category not selected automatically:", e)
            input("👉 Select category manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        print(f"🎉 Listing uploaded on {MARKETPLACE.capitalize()}. Review and publish it manually.")

    except Exception as e:
        print(f"⚠️ {MARKETPLACE.capitalize()} upload error: {e}")

    return driver

