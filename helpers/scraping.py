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
from helpers.utils import is_match, vinted_title_shorten, scroll_to_load_all_items


# ---------------------------
# Collecting
# ---------------------------

def collect_listing_generic(url: str, marketplace: str, col_title, col_price, col_desc, first_img_selector=None, carousel_selector=None, price_filter=None) -> dict:
    """
    Generic collector that handles both listing details AND images in one call.
    Returns complete listing dict ready to use.
    """
    # Get text details first
    listing = collect_listing_details(
        url, marketplace, col_title, col_price, col_desc, price_filter
    )
    
    if check_abort():
        return None
    
    # Get images
    images, md5, phash = collect_listing_images(
        url, marketplace, first_img_selector, carousel_selector
    )
    
    listing["images"] = images
    listing["md5"] = md5
    listing["phash"] = phash
    
    return listing

def collect_listing_details(url: str, marketplace: str, col_title, col_price, col_desc, price_filter=None) -> dict:
    """
    Scrape title, price, description from a URL using BeautifulSoup.
    `price_filter` can be a lambda function to filter element attributes.
    """
    listing = {
        "url": url, 
        "source": marketplace,
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
            print(f"❌ Error loading {marketplace.capitalize()} page: {r.status_code}")
            return listing
        soup = BeautifulSoup(r.text, "html.parser")

        # Title
        title_tag = soup.find(col_title) if isinstance(col_title, str) else soup.find(*col_title)
        listing["title"] = title_tag.get_text(strip=True) if title_tag else None

        # Price
        if isinstance(col_price, list):
            tag_name, attr_name, attr_val = col_price
            if price_filter:
                price_tag = soup.find(tag_name, {attr_name: price_filter})
            else:
                price_tag = soup.find(tag_name, {attr_name: attr_val})
            listing["price"] = price_tag.get_text(strip=True) if price_tag else None
        else:
            price_tag = soup.find(col_price)
            listing["price"] = price_tag.get_text(strip=True) if price_tag else None

        # Description
        if isinstance(col_desc, list):
            tag_name, attr_name, attr_val = col_desc
            desc_tag = soup.find(tag_name, {attr_name: attr_val})
            if desc_tag:
                listing["description"] = desc_tag.get("content") or desc_tag.get_text(" ", strip=True)
            else:
                None
        else:
            desc_tag = soup.find(col_desc)
            listing["description"] = desc_tag.get_text(" ", strip=True) if desc_tag else None

        print(f'\n---\nTitle: {listing["title"]}\nPrice: {listing["price"]}\nDescription: {listing["description"]}\n---')

    except Exception as e:
        print(f"⚠️ Error scraping listing details: {e}")

    return listing

def collect_listing_images(url: str, marketplace: str, first_img_selector=None, carousel_selector=None) -> list:
    """
    Open page in headless driver and collect images. Returns list of image URLs.
    `cdn_filter` can be a substring to filter URLs (e.g., Wallapop cdn).
    """
    images = []

    if check_abort():
        return images

    print(f"🌍 Opening {marketplace.capitalize()} listing...") 
    driver = headless_driver()
    print("⏳ Retrieving images...")
    try:
        driver.get(url)
        time.sleep(3)

        if check_abort():
            return images

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
        for img in elems:
            src = img.get_attribute("src")
            if (marketplace == "wallapop" and src and src not in seen and "cdn.wallapop.com" in src and "W640" in src) \
            or (marketplace == "vinted" and src and src not in seen):
                images.append(src)
                seen.add(src)
    except Exception as e:
        print(f"⚠️ Error retrieving {marketplace.capitalize()} listing's images: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

    if check_abort():
        return images

    # Download images locally
    images_local = [os.path.abspath(download_image(u)) for u in images]
    if images_local:
        print(f"✅ Downloaded {len(images_local)} images.")
    else:
        print("❌ No images downloaded.")

    # Compute hashes for first image
    if images:
        md5, phash = compute_image_hashes(images[0])
        return images_local, md5, phash

    if check_abort():
        return images

    return images_local, None, None


# ---------------------------
# Checking
# ---------------------------
def check_listing_existence(listing, marketplace: str, login_selector: str, home_url: str, profile_url_resolver, sel_items: str, sel_title: str, sel_img, title_extractor, image_extractor) -> str | None:
    """
    Generic skeleton for marketplace 'check' functions.
    Marketplace-specific profile URL logic and extractors are injected.
    """

    driver = None
    try:
        print(f"🔍 Checking if listing exists on {marketplace.capitalize()}...")
        driver = headless_driver()
        driver = ensure_logged_in(driver, login_selector, home_url, marketplace)
        if not driver:
            print(f"❌ Could not log in to {marketplace.capitalize()}.")
            return None

        profile_url = profile_url_resolver(driver)
        if not profile_url:
            print(f"❌ Could not determine profile URL for {marketplace.capitalize()}.")
            return None

        driver.get(profile_url)

        if check_abort(driver):
            return None

        return find_listing_in_profile(listing, marketplace, driver, sel_items, sel_title, sel_img, title_extractor, image_extractor)

    except Exception as e:
        print(f"⚠️ {marketplace.capitalize()} check error: {e}")
        return None

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return None

def find_listing_in_profile(listing, marketplace: str, driver, sel_items, sel_title, sel_img, title_extractor, image_extractor, hamming_thresh=6) -> str | None:
    """
    Scroll through profile items and match by title first, then images.
    Uses marketplace-specific extractors injected from each module.
    """
    if not driver:
        return None

    driver.get(driver.current_url)  # make sure page loaded
    time.sleep(3)

    if check_abort(driver): 
        return None

    print("⏳ Scrolling profile page to load all listings...")
    items = scroll_to_load_all_items(driver, sel_items)
    if not items:
        print(f"❌ No listings found on {marketplace.capitalize()}.")
        return None
    print(f"🟢 Found {len(items)} listings on {marketplace.capitalize()} profile.")

    if check_abort(driver): 
        return None

    # Match by titl
    print("🔍 Checking listings by title to find a match...")
    for item in items:
        try:
            title_text = title_extractor(item, sel_title)
            href = item.find_element(By.CSS_SELECTOR, sel_title).get_attribute("href")

            if title_text and is_match(listing["title"], title_text):
                print(f"✅ Match found by title: {title_text} -> {href}")
                return href

        except Exception as e:
            print(f"⚠️ Title parse error: {e}")
            continue

        if check_abort(driver): 
            return None


    # Match by image
    print("🔍 No title match found, checking by image hashes...")
    for item in items:
        try:
            href = item.find_element(By.CSS_SELECTOR, sel_title).get_attribute("href")
            img_url = image_extractor(item, sel_img)
            
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

        if check_abort(driver): 
            return None

    return None





def _empty_listing(url: str | None) -> dict:
    """Return an empty listing structure."""
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