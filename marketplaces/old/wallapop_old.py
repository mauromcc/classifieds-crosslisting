import os, re, time, requests
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from constants import HEADERS
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.abort import check_abort
from helpers.utils import is_match, scroll_to_load_all_items
from helpers.images import download_image, compute_image_hashes, hamming_distance_hex, remove_temp_folder



# ---------------------------
# CSS Selectors & URLs
# ---------------------------
MARKETPLACE = "wallapop"
HOME_URL = "https://es.wallapop.com"
PROFILE_URL = "https://es.wallapop.com/app/catalog/published"
UPLOAD_URL = "https://es.wallapop.com/app/catalog/upload/consumer-goods"
LOGIN_SELECTOR = "img[data-testid='user-avatar']"
COL_ITEM_HTML_TITLE = "h1"
COL_ITEM_HTML_PRICE = ["span", "class", "Price"]
COL_ITEM_HTML_DESCRIPTION = ["meta", "name", "og:description"]
SEL_PROFILE_ITEMS = "tsl-catalog-item a.item-details"
SEL_ITEM_TITLE = ".info-title"
SEL_UPLOAD_TITLE = "summary"
SEL_UPLOAD_DESCRIPTION = "description"
SEL_UPLOAD_PRICE = "sale_price"
SEL_UPLOAD_CONTINUE_BTN = "walla-button[data-testid='continue-button']"
# SEL_UPLOAD_CATEGORY = 'div[role="listbox"][aria-label="Categoría y subcategoría"]'
# SEL_UPLOAD_CATEGORY_OPTION = "div.sc-walla-dropdown-item"
SEL_UPLOAD_CATEGORY = 'div.walla-dropdown__inner-input[aria-label="Categoría y subcategoría"]'
SEL_UPLOAD_CATEGORY_OPTION = 'div.sc-walla-dropdown-item'
SEL_UPLOAD_FILE = 'input[type="file"]'



# ---------------------------
# Collector
# ---------------------------
def collect_from_wallapop(url: str) -> dict:
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

    if check_abort(): 
        return None

    try:
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"❌ Error loading Wallapop page: {r.status_code}")
            return listing
        soup = BeautifulSoup(r.text, "html.parser")
    
        if check_abort(): 
            return None


        # Text
        title_tag = soup.find(COL_ITEM_HTML_TITLE)
        listing["title"] = title_tag.get_text(strip=True) if title_tag else None
        price_tag = soup.find(COL_ITEM_HTML_PRICE[0], {COL_ITEM_HTML_PRICE[1]: lambda x: x and COL_ITEM_HTML_PRICE[2] in x})
        listing["price"] = price_tag.get_text(strip=True) if price_tag else None
        desc_meta = soup.find(COL_ITEM_HTML_DESCRIPTION[0], attrs={COL_ITEM_HTML_DESCRIPTION[1]: COL_ITEM_HTML_DESCRIPTION[2]})
        listing["description"] = desc_meta["content"].strip() if desc_meta else None

        print(f'\n---\n"Title: {listing["title"]}"\n"Price: {listing["price"]}"\n"Description: {listing["description"]}"\n---')

        if check_abort(): 
            return None


        # Images
        print(f"🌍 Opening {MARKETPLACE.capitalize()} listing...")
        d = headless_driver()
        print("⏳ Retrieving images...")
        try:
            d.get(url)
            time.sleep(3)

            if check_abort(): 
                return None

            seen = set()
            for img in d.find_elements(By.CSS_SELECTOR, "img"):
                src = img.get_attribute("src")
                if src and "cdn.wallapop.com" in src and "W640" in src and src not in seen:
                    if src not in seen:
                        listing["image_urls"].append(src)
                        seen.add(src)
        except Exception as e:
            print(f"⚠️ Error retrieving Wallapop listing's images: {e}")
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
        print(f"⚠️ Error collecting listing details from Wallapop: {e}")

    if check_abort(): 
        return None

    return listing


# ---------------------------
# Checker
# ---------------------------
def check_wallapop(listing) -> str | None:
    """Return URL if the listing exists in Wallapop account (headless)."""
    driver = None
    try:
        # Open profile listings page
        print(f"🌍 Checking if listing exists on {MARKETPLACE.capitalize()}...")
        driver = headless_driver()
        # input("👉 Press Enter to continue.")
        driver = ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE) # override drive in case logged out
        if not driver:
            print(f"❌ Could not log in. Aborting check on {MARKETPLACE.capitalize()}...")
            return None
        driver.get(PROFILE_URL)
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
                title = item.find_element(By.CSS_SELECTOR, SEL_ITEM_TITLE).text.strip()
                href = item.get_attribute("href")
                if is_match(listing["title"], title):
                    print(f"✅ Match found by title: {title} -> {href}")
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
                href = item.get_attribute("href")
                parent = item.find_element(By.XPATH, "./ancestor::div[contains(@class, 'row')]")
                avatar_divs = parent.find_elements(By.CSS_SELECTOR, "div.ItemAvatar")
                for avatar in avatar_divs:
                    style = avatar.get_attribute("style")
                    if "url(" in style:
                        match = re.search(r'url\([\"]?([^\")]+)', style)
                        if match:
                            img_url = match.group(1).split("?")[0]
                            cand_md5, cand_phash = compute_image_hashes(img_url)

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
# Uploader
# ---------------------------
def upload_to_wallapop(listing: dict):
    driver = None
    try:
        print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
        driver = visible_driver()
        ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
        driver.get(UPLOAD_URL)
        time.sleep(5)

        if check_abort(driver): 
            return None

        # Title
        try:
            title_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_TITLE)))
            title_input.clear()
            title_input.send_keys(listing["title"])
            print("✅ Title filled")
        except Exception as e:
            print("⚠️ Could not fill title automatically:", e)
            input("👉 Fill the title manually, then press Enter to continue...")

        # "Continuar"
        try:
            continuar_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_UPLOAD_CONTINUE_BTN))
            )
            continuar_btn.click()
            print("✅ Clicked 'Continuar'")
        except Exception as e:
            print("⚠️ Could not click 'Continuar':", e)
            input("👉 Click 'Continuar' manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        # Images
        print("⏳ Uploading images...")
        time.sleep(2)
        try:
            driver.find_element(By.CSS_SELECTOR, SEL_UPLOAD_FILE).send_keys("\n".join(listing["images"]))
            print("✅ Images uploaded")
        except Exception as e:
            print("⚠️ Error uploading images:", e)
            input("👉 Upload images manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        # "Continuar" again
        try:
            continuar_buttons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL_UPLOAD_CONTINUE_BTN))
            )
            continuar_buttons[-1].click()
            print("✅ Clicked 'Continuar'")
        except Exception as e:
            print("⚠️ Could not click 'Continuar':", e)
            input("👉 Click 'Continuar' manually, then press Enter to continue...")

        # Category
        try:
            category_dropdown = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_UPLOAD_CATEGORY))
            )
            # driver.execute_script("arguments[0].scrollIntoView(true);", category_dropdown)
            category_dropdown.click()
            print("✅ Opened the category dropdown")
        except Exception as e:
            print("⚠️ Error opening category dropdown:", e)
            input("👉 Open/select category manually, then press Enter to continue...")

        time.sleep(1)

        if check_abort(driver): 
            return None

        try:
            first_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_UPLOAD_CATEGORY_OPTION))
            )
            # driver.execute_script("arguments[0].scrollIntoView(true);", first_option)
            first_option.click()
            print("✅ First category selected")
        except Exception as e:
            print("⚠️ Error selecting category:", e)
            input("👉 Select category manually, then press Enter to continue...")

        # Description (AI keep/replace)
        try:
            description_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_DESCRIPTION)))
            current_ai = description_input.get_attribute("value").strip()

            print(f"\n📝 {MARKETPLACE.capitalize()} AI-generated description:\n---\n" + current_ai + "\n---")
            print("\n📝 Scraped description:\n---\n" + listing["description"] + "\n---")
            choice = input("👉 Keep AI (k) or Replace with scraped (r)? (k/r): ").strip().lower()
            if choice == "r":
                description_input.clear()
                description_input.send_keys(listing["description"])
                print("✅ Scraped description used")
            else:
                print("✅ Kept AI description")
        except Exception as e:
            print("⚠️ Could not process description automatically:", e)
            input("👉 Fill/verify the description manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        # Price
        try:
            price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
            price_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, SEL_UPLOAD_PRICE)))
            price_input.clear()
            price_input.send_keys(price_cleaned)
            print("✅ Price filled")
        except Exception as e:
            print("⚠️ Error filling price:", e)
            input("👉 Fill price manually, then press Enter to continue...")

        if check_abort(driver): 
            return None

        print(f"🎉 Listing uploaded on {MARKETPLACE.capitalize()}. Review and publish it manually.")
    
    except Exception as e:
        print(f"⚠️ {MARKETPLACE.capitalize()} upload error: {e}")

    return driver

