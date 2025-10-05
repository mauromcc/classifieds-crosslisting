import time, re

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from constants import register_marketplace
from helpers.scraping import collect_listing_generic, check_listing_existence, find_listing_in_profile
from helpers.uploader import upload_listing_generic
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.utils import vinted_title_shorten
from helpers.abort import check_abort



MARKETPLACE = "vinted"

# ---------------------------
# URLs & Selectors
# ---------------------------
HOME_URL = "https://www.vinted.es/"
PROFILE_URL = "https://www.vinted.es/member/"
UPLOAD_URL = "https://www.vinted.es/items/new"
LOGIN_SELECTOR = "button#user-menu-button"

COL_ITEM_HTML_TITLE = "h1"
COL_ITEM_HTML_PRICE = ["div", "data-testid", "item-price"]
COL_ITEM_HTML_DESCRIPTION = ["div", "itemprop", "description"]
COL_ITEM_FIRST_IMG = "img[data-testid^='item-photo']"
COL_ITEM_CAROUSEL_IMGS = "img[data-testid='image-carousel-image-shown'], img[data-testid='image-carousel-image']"

CHK_PROFILE_ITEMS = "div[data-testid='grid-item']"
CHK_PROFILE_TITLE = "a.new-item-box__overlay--clickable"
CHK_PROFILE_IMG = "img.web_ui__Image__content"

UPL_ITEM_TITLE = (By.ID, "title")
UPL_ITEM_DESCRIPTION = (By.ID, "description")
UPL_ITEM_PRICE = (By.ID, "price")
UPL_ITEM_CATEGORY = (By.ID, "category")
UPL_ITEM_CATEGORY_FIRST = (By.CSS_SELECTOR, "[id^='catalog-suggestion-']")
UPL_ITEM_CATEGORY_OPEN = (By.CSS_SELECTOR, "div.input-dropdown[data-testid='catalog-select-dropdown-content']")
UPL_ITEM_IMG_INPUT = (By.CSS_SELECTOR, 'input[type="file"]')
UPL_ITEM_IMG_PREVIEW = (By.CSS_SELECTOR, "div[data-testid^='image-wrapper-']")
UPLOAD_SEQUENCE = [
    "images",
    "category",
    "title",
    "description",
    "price"
]


# ---------------------------
# Collector
# ---------------------------
def collect_from_vinted(url: str) -> dict:
    col_selectors = {
        "col_title": COL_ITEM_HTML_TITLE,
        "col_price": COL_ITEM_HTML_PRICE,
        "col_price_filter": None,
        "col_description": COL_ITEM_HTML_DESCRIPTION,
        "col_img_extractor": vinted_collect_img_extractor,
    }
    return collect_listing_generic(
        url=url,
        marketplace=MARKETPLACE,
        col_selectors=col_selectors
    )

def vinted_collect_img_extractor(driver):
    try:
        first_img = driver.find_element(By.CSS_SELECTOR, COL_ITEM_FIRST_IMG)
        driver.execute_script("arguments[0].click();", first_img)
        time.sleep(0.5)
    except Exception:
        pass
    
    images = []
    elems = driver.find_elements(By.CSS_SELECTOR, COL_ITEM_CAROUSEL_IMGS)
    seen = set()
    for i in range(len(elems)):
        try:
            img = elems[i]
            src = img.get_attribute("src")
            if src and src not in seen:
                images.append(src)
                seen.add(src)
        except StaleElementReferenceException as e:
            print(f"⚠️ Error retrieving {MARKETPLACE.capitalize()} listing's images: {e}")
            continue
                

    return images

# ---------------------------
# Checker
# ---------------------------
def check_on_vinted(listing) -> str | None:
    chk_selectors = {
        "home_url": HOME_URL,
        "login_selector": LOGIN_SELECTOR,
        "profile_url_resolver": vinted_profile_resolver,
        "chk_items": CHK_PROFILE_ITEMS,
        "chk_title": CHK_PROFILE_TITLE,
        "chk_img": CHK_PROFILE_IMG,
        "chk_title_extractor": vinted_check_title_extractor,
        "chk_href_extractor": vinted_check_href_extractor,
        "chk_image_extractor": vinted_check_image_extractor,
    }
    return check_listing_existence(
        listing=listing,
        marketplace=MARKETPLACE,
        chk_selectors=chk_selectors
    )

def vinted_profile_resolver(driver):
    # Extract user_id from page source
    html = driver.page_source
    m = re.search(r'"userId":"?(\d+)"?', html) or re.search(r'consentId=(\d+)', html)
    if m:
        user_id = m.group(1)
        print(f"🟢 Found {MARKETPLACE.capitalize()} user ID: {user_id}")
        return f"{PROFILE_URL}{user_id}"
    else:
        print(f"❌ Could not extract {MARKETPLACE.capitalize()} user ID.")
        return None

def vinted_check_title_extractor(item, chk_title):
    """Extracts and shortens the title string for Vinted items."""
    try:
        elem = item.find_element(By.CSS_SELECTOR, chk_title)
        raw_title = elem.get_attribute("title").strip()
        return vinted_title_shorten(raw_title)
    except:
        return None

def vinted_check_href_extractor(item, chk_title):
    return item.find_element(By.CSS_SELECTOR, chk_title).get_attribute("href")

def vinted_check_image_extractor(item, chk_img):
    """Extracts the main image URL for Vinted items."""
    try:
        img_elem = item.find_element(By.CSS_SELECTOR, chk_img)
        return img_elem.get_attribute("src").split("?")[0]
    except:
        return None


# ---------------------------
# Uploader
# ---------------------------
def upload_to_vinted(listing: dict):
    print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
    driver = visible_driver()
    ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
    driver.get(UPLOAD_URL)

    upl_selectors = {
        "upl_title": UPL_ITEM_TITLE,
        "upl_description": UPL_ITEM_DESCRIPTION,
        "upl_desc_resolver": None,
        "upl_price": UPL_ITEM_PRICE,
        "upl_category": UPL_ITEM_CATEGORY,
        "upl_category_first": UPL_ITEM_CATEGORY_FIRST,
        "upl_category_resolver": vinted_upload_category_resolver,
        "upl_image_input": UPL_ITEM_IMG_INPUT,
        "upl_image_preview": UPL_ITEM_IMG_PREVIEW,
        "upl_continue_btn": None,
    }

    upload_listing_generic(
        driver=driver, 
        listing=listing,
        marketplace=MARKETPLACE, 
        upl_selectors=upl_selectors,
        upl_sequence=UPLOAD_SEQUENCE, 
    )

    return driver


def vinted_upload_category_resolver(driver, category_dropdown):
    try:
        driver.find_element(*UPL_ITEM_CATEGORY_OPEN)
        return True
    except:
        return False





# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    collector=collect_from_vinted,
    checker=check_on_vinted,
    uploader=upload_to_vinted
)