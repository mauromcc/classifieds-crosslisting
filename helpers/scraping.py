import os, time, re, requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from constants import HEADERS
from helpers.drivers import headless_driver
from helpers.cookies import ensure_logged_in
from helpers.abort import check_abort
from helpers.images import download_image, compute_image_hashes, hamming_distance_hex
from helpers.utils import is_match, scroll_to_load_all_items


# ---------------------------
# Collecting
# ---------------------------

def collect_listing_generic(url: str, marketplace: str, col_title, col_price, col_desc, first_img_selector=None, carousel_selector=None, price_filter=None) -> dict | None:
    """
    Generic collector that handles both listing details AND images in one call.
    Returns complete listing dict, or None if aborted.
    """
    listing = {
    "url": url, 
    "source": marketplace,
    "title": None, 
    "price": None, 
    "description": None, 
    "images": [], 
    "md5": None, 
    "phash": None,
    }

    # Get text details first
    result = collect_listing_details(url, marketplace, col_title, col_price, col_desc, price_filter)
    if result is None:  # aborted
        return None

    title, price, description = result
    if title is None or price is None or description is None:
        print(f"❌ Failed to collect required details from {marketplace.capitalize()}'s listing.")
        return listing  # incomplete but not aborted

    listing["title"] = title
    listing["price"] = price
    listing["description"] = description
    
    if check_abort():
        return None
    
    # Get images
    result = collect_listing_images(url, marketplace, first_img_selector, carousel_selector)
    if result is None:  # aborted
        return None

    images, md5, phash = result
    if not images:
        print(f"❌ Failed to collect images from {marketplace.capitalize()}'s listing.")
        return listing  # incomplete but not aborted 
    
    listing["images"] = images
    listing["md5"] = md5
    listing["phash"] = phash
    
    return listing

def collect_listing_details(url: str, marketplace: str, col_title, col_price, col_desc, price_filter=None) -> tuple[str, str, str] | None:
    """
    Scrape title, price, and description from a URL using BeautifulSoup.
    Returns (title, price, description) tuple, or None if aborted/failed.
    """

    if check_abort():
        return None

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"❌ Error loading {marketplace.capitalize()} page: {r.status_code}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # Title
        title_tag = soup.find(col_title) if isinstance(col_title, str) else soup.find(*col_title)
        title = title_tag.get_text(strip=True) if title_tag else None

        # Price
        if isinstance(col_price, list):
            tag_name, attr_name, attr_val = col_price
            if price_filter:
                price_tag = soup.find(tag_name, {attr_name: price_filter})
            else:
                price_tag = soup.find(tag_name, {attr_name: attr_val})
            price = price_tag.get_text(strip=True) if price_tag else None
        else:
            price_tag = soup.find(col_price)
            price = price_tag.get_text(strip=True) if price_tag else None

        # Description
        if isinstance(col_desc, list):
            tag_name, attr_name, attr_val = col_desc
            desc_tag = soup.find(tag_name, {attr_name: attr_val})
            if desc_tag:
                description = desc_tag.get("content") or desc_tag.get_text(" ", strip=True)
            else:
                description = None
        else:
            desc_tag = soup.find(col_desc)
            description = desc_tag.get_text(" ", strip=True) if desc_tag else None

        print(f'\n---\nTitle: {title}\nPrice: {price}\nDescription: {description}\n---')
        return title, price, description

    except Exception as e:
        print(f"⚠️ Error scraping listing details: {e}")
        return None

def collect_listing_images(url: str, marketplace: str, first_img_selector=None, carousel_selector=None) -> tuple[list, str, str] | None:
    """
    Open page in headless driver and collect images.
    Returns (images_local, md5, phash) tuple, or None if aborted/failed.
    """
    if check_abort():
        return None

    images = []
    driver = None

    print(f"🌍 Opening {marketplace.capitalize()} listing...")
    try:
        driver = headless_driver()
        if check_abort():
            return None
        print("⏳ Retrieving images...")
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img")))

        if check_abort():
            return None

        elems = []
        if marketplace == "vinted":
            if first_img_selector:
                try:
                    first_img = driver.find_element(By.CSS_SELECTOR, first_img_selector)
                    driver.execute_script("arguments[0].click();", first_img)
                    time.sleep(0.5)
                except Exception:
                    pass
            if carousel_selector:
                elems = driver.find_elements(By.CSS_SELECTOR, carousel_selector)
        elif marketplace == "wallapop":
            elems = driver.find_elements(By.CSS_SELECTOR, "img")
        
        seen = set()
        for i in range(len(elems)):
            try:
                img = elems[i]
                src = img.get_attribute("src")
                if (marketplace == "wallapop" and src and src not in seen and "cdn.wallapop.com" in src and "W640" in src) \
                or (marketplace == "vinted" and src and src not in seen):
                    images.append(src)
                    seen.add(src)
            except StaleElementReferenceException:
                continue
                print(f"⚠️ Error retrieving {marketplace.capitalize()} listing's images: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    if check_abort():
        return None

    # Download images locally
    images_local = [p for u in images if (p := safe_download_image(u)) is not None]
    if images_local:
        print(f"✅ Downloaded {len(images_local)} images")
    else:
        print("❌ No images downloaded")
        return ([], None, None)  # failed but not aborted

    # Compute hashes for first image
    md5, phash = compute_image_hashes(images[0]) if images else (None, None)
        
    if check_abort():
        return None

    return images_local, md5, phash

def safe_download_image(url: str) -> str | None:
    """Download image to local temp folder, return absolute path or None if failed."""
    try:
        return os.path.abspath(download_image(url))
    except Exception as e:
        print(f"⚠️ Failed to download {url[:50]}...: {e}")
        return None

# ---------------------------
# Checking
# ---------------------------
def check_listing_existence(listing, marketplace: str, login_selector: str, home_url: str, profile_url_resolver, chk_items: str, chk_title: str, chk_img, title_extractor, image_extractor) -> str | None:
    """
    Generic skeleton for marketplace 'check' functions.
    Returns URL if found, None if not found or aborted.
    """

    driver = None
    try:
        print(f"🔍 Checking if listing exists on {marketplace.capitalize()}...")
        driver = headless_driver()
        if check_abort():
            return None
        driver = ensure_logged_in(driver, login_selector, home_url, marketplace)
        if not driver:
            print(f"❌ Could not log in to {marketplace.capitalize()}")
            return None

        if check_abort(driver):
            return None

        profile_url = profile_url_resolver(driver)
        if not profile_url:
            print(f"❌ Could not determine profile URL for {marketplace.capitalize()}")
            return None

        driver.get(profile_url)

        if check_abort(driver):
            return None

        return find_listing_in_profile(listing, marketplace, driver, chk_items, chk_title, chk_img, title_extractor, image_extractor)

    except Exception as e:
        print(f"⚠️ {marketplace.capitalize()} check error: {e}")
        return None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def find_listing_in_profile(listing, marketplace: str, driver, chk_items, chk_title, chk_img, title_extractor, image_extractor, hamming_thresh=6) -> str | None:
    """
    Scroll through profile items and match by title first, then images.
    Returns URL if found, None otherwise.
    """
    if not driver:
        return None

    try:
        driver.get(driver.current_url)  # make sure page loaded
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img")))

        if check_abort(driver): 
            return None

        print("⏳ Scrolling profile page to load all listings...")
        items = scroll_to_load_all_items(driver, chk_items)
        if check_abort(driver): 
            return None
        if not items:
            print(f"❌ No listings found on {marketplace.capitalize()}")
            return None
        print(f"🟢 Found {len(items)} listings on {marketplace.capitalize()} profile")

        if check_abort(driver): 
            return None

        # Match by title
        print("🔍 Checking listings by title to find a match...")
        for item in items:
            if check_abort(driver):
                return None

            try:
                title_text = title_extractor(item, chk_title)
                try:
                    if marketplace == "wallapop":
                        href = item.get_attribute("href")
                    elif marketplace == "vinted":
                        href = item.find_element(By.CSS_SELECTOR, chk_title).get_attribute("href")
                except:
                        continue

                if not href:
                    print(f"⚠️ Found title '{title_text}' but href is None, skipping...")
                    continue

                if title_text and is_match(listing["title"], title_text):
                    print(f"✅ Match found by title: {title_text} -> {href}")
                    return href

            except Exception as e:
                print(f"⚠️ Title parse error: {e}")
                continue


        # Match by image
        print("❌ No title match found")
        print("🔍 Checking listings by image hashes to find a match...")
        for item in items:
            if check_abort(driver):
                return None

            try:
                try:
                    if marketplace == "wallapop":
                        href = item.get_attribute("href")
                    elif marketplace == "vinted":
                        href = item.find_element(By.CSS_SELECTOR, chk_title).get_attribute("href")
                except:
                    continue

                img_url = image_extractor(item, chk_img)
                
                if img_url:
                    cand_md5, cand_phash = compute_image_hashes(img_url)

                    # DEBUG PRINTS
                    # print(f"🖼️ Found item image: {img_url}")
                    # print(f"Listing md5: {listing.get('md5')}, candidate md5: {cand_md5}")
                    # print(f"Listing phash: {listing.get('phash')}, candidate phash: {cand_phash}")

                    if listing.get("md5") and cand_md5 and listing["md5"] == cand_md5:
                        print(f"✅ Exact md5 match: {href}")
                        return href
                    if listing.get("phash") and cand_phash:
                        ham = hamming_distance_hex(listing["phash"], cand_phash) 
                        if ham <= hamming_thresh:
                            print(f"✅ Perceptual match (hamming={ham}): {href}")
                            return href

            except Exception as e:
                print(f"⚠️ Item parse error (image check): {e}")
                continue

        print("❌ No image hash match found")

    except Exception as e:
        print(f"⚠️ Error in find_listing_in_profile: {e}")

    return None


