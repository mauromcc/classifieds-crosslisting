import time, re

from selenium.webdriver.common.by import By

from constants import register_marketplace
from helpers.scraping import collect_listing_generic, check_listing_existence, find_listing_in_profile
from helpers.uploader import upload_listing_common
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

SEL_PROFILE_ITEMS = "div[data-testid='grid-item']"
SEL_PROFILE_TITLE = "a.new-item-box__overlay--clickable"
SEL_PROFILE_IMG = "img.web_ui__Image__content"

SEL_UPLOAD_TITLE = "title"
SEL_UPLOAD_DESCRIPTION = "description"
SEL_UPLOAD_PRICE = "price"
SEL_UPLOAD_CATEGORY = "category"
SEL_UPLOAD_CATEGORY_OPTION = "[id^='catalog-suggestion-']"
SEL_UPLOAD_FILE = 'input[type="file"]'



# ---------------------------
# Collector
# ---------------------------
def collect_from_vinted(url: str) -> dict:
    return collect_listing_generic(
        url,
        MARKETPLACE,
        COL_ITEM_HTML_TITLE,
        COL_ITEM_HTML_PRICE,
        COL_ITEM_HTML_DESCRIPTION,
        first_img_selector=COL_ITEM_FIRST_IMG,
        carousel_selector=COL_ITEM_CAROUSEL_IMGS
    )


# ---------------------------
# Checker
# ---------------------------
def check_on_vinted(listing) -> str | None:
    return check_listing_existence(
        listing,
        MARKETPLACE,
        LOGIN_SELECTOR,
        HOME_URL,
        vinted_profile_resolver,
        SEL_PROFILE_ITEMS,
        SEL_PROFILE_TITLE,
        SEL_PROFILE_IMG,
        vinted_title_extractor,
        vinted_image_extractor
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

def vinted_title_extractor(item, sel_title):
    """Extracts and shortens the title string for Vinted items."""
    try:
        elem = item.find_element(By.CSS_SELECTOR, sel_title)
        raw_title = elem.get_attribute("title").strip()
        return vinted_title_shorten(raw_title)
    except:
        return None

def vinted_image_extractor(item, sel_img):
    """Extracts the main image URL for Vinted items."""
    try:
        img_elem = item.find_element(By.CSS_SELECTOR, sel_img)
        return img_elem.get_attribute("src").split("?")[0]
    except:
        return None

# ---------------------------
# Uploader
# ---------------------------
def upload_to_vinted(listing: dict):
    driver = visible_driver()
    ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
    driver.get(UPLOAD_URL)

    selectors = {
        "title": SEL_UPLOAD_TITLE,
        "description": SEL_UPLOAD_DESCRIPTION,
        "price": SEL_UPLOAD_PRICE,
        "category": SEL_UPLOAD_CATEGORY,
        "category_option": SEL_UPLOAD_CATEGORY_OPTION,
        "file_input": SEL_UPLOAD_FILE
    }

    upload_listing_common(driver, listing, selectors)
    return driver





# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    collector=collect_from_vinted,
    checker=check_on_vinted,
    uploader=upload_to_vinted
)