import time, re

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from constants import register_marketplace
from helpers.scraping import collect_listing_generic, check_listing_existence
from helpers.images import extract_images_generic
from helpers.uploader import upload_listing_generic
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.utils import vinted_title_shorten
from helpers.abort import check_abort



MARKETPLACE = "vinted"

# ---------------------------
# Vinted-specific configuration
# ---------------------------
CONFIG = {
    # URLs
    "home_url": "https://www.vinted.es/",
    "profile_url": "https://www.vinted.es/member/",
    "upload_url": "https://www.vinted.es/items/new",
    
    "login_selector": (By.CSS_SELECTOR,"button#user-menu-button"),
    
    # Collection selectors
    "use_driver_for_details": False,
    "col_title": ["h1", "class", "web_ui__Text__title"],
    "col_price": ["div", "data-testid", "item-price"],
    "col_price_filter": None,
    "col_description": ["div", "itemprop", "description"],
    "col_first_img": (By.CSS_SELECTOR, "img[data-testid^='item-photo']"),
    "col_carousel_imgs": (By.CSS_SELECTOR, "img[data-testid='image-carousel-image-shown'], img[data-testid='image-carousel-image']"),
    "col_image_css": (By.CSS_SELECTOR, "img"),
    "col_image_filter": None,
    "col_image_pre_hook": None,
    
    # Check selectors
    "chk_items": (By.CSS_SELECTOR, "div[data-testid='grid-item']"),
    "chk_title": (By.CSS_SELECTOR, "a.new-item-box__overlay--clickable"),
    "chk_image": (By.CSS_SELECTOR, "img.web_ui__Image__content"),
    
    # Upload selectors
    "upl_title": (By.ID, "title"),
    "upl_description": (By.ID, "description"),
    "upl_price": (By.ID, "price"),
    "upl_category": (By.ID, "category"),
    "upl_category_first": (By.CSS_SELECTOR, "[id^='catalog-suggestion-']"),
    "upl_category_open": (By.CSS_SELECTOR, "div.input-dropdown[data-testid='catalog-select-dropdown-content']"),
    "upl_image_input": (By.CSS_SELECTOR, 'input[type="file"]'),
    "upl_image_preview": (By.CSS_SELECTOR, "div[data-testid^='image-wrapper-']"),
    "upl_continue_btn": None,
    "upl_sequence": ["images", "title", "description", "price", "category"],
}


# ---------------------------
# Collector
# ---------------------------
def collect_from_vinted(url: str) -> dict:
    """Collect listing from Vinted."""
    return collect_listing_generic(url, MARKETPLACE, CONFIG)

def col_image_pre_hook(driver):
    """Click first image to open Vinted carousel."""
    try:
        first_img = driver.find_element(*CONFIG["col_first_img"])
        driver.execute_script("arguments[0].click();", first_img)
        time.sleep(0.5)
    except Exception:
        pass

def col_image_extractor(driver):
    """Extract images from Vinted listing page."""
    return extract_images_generic(
        driver=driver,
        css_selector=CONFIG["col_carousel_imgs"],
        filter_func=CONFIG["col_image_filter"],
        pre_extract_hook=CONFIG["col_image_pre_hook"],
        marketplace=MARKETPLACE
    )

# ---------------------------
# Checker
# ---------------------------
def check_on_vinted(listing) -> str | None:
    """Check if listing exists on Vinted."""
    return check_listing_existence(listing, MARKETPLACE, CONFIG)

def profile_url_resolver(driver):
    """Extract user_id from page source and build profile URL."""
    html = driver.page_source
    m = re.search(r'"userId":"?(\d+)"?', html) or re.search(r'consentId=(\d+)', html)
    if m:
        user_id = m.group(1)
        print(f"🟢 Found {MARKETPLACE.capitalize()} user ID: {user_id}")
        return f"{CONFIG['profile_url']}{user_id}"
    else:
        print(f"❌ Could not extract {MARKETPLACE.capitalize()} user ID.")
        return None

def chk_title_extractor(item):
    """Extracts and shortens the title string for Vinted items."""
    try:
        elem = item.find_element(*CONFIG["chk_title"])
        raw_title = elem.get_attribute("title").strip()
        return vinted_title_shorten(raw_title)
    except:
        return None

def chk_href_extractor(item):
    """Extract href from Vinted item."""
    return item.find_element(*CONFIG["chk_title"]).get_attribute("href")

def chk_image_extractor(item):
    """Extracts the main image URL for Vinted items."""
    try:
        img_elem = item.find_element(*CONFIG["chk_image"])
        return img_elem.get_attribute("src").split("?")[0]
    except:
        return None


# ---------------------------
# Uploader
# ---------------------------
def upload_to_vinted(listing: dict):
    """Upload listing to Vinted."""
    print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
    driver = visible_driver()
    ensure_logged_in(driver, CONFIG["login_selector"], CONFIG["home_url"], MARKETPLACE)
    driver.get(CONFIG["upload_url"])

    return upload_listing_generic(driver, listing, MARKETPLACE, CONFIG)

def upl_category_resolver(driver, category_dropdown):
    try:
        driver.find_element(*CONFIG["upl_category_open"])
        return True
    except:
        return False



# Add extractors to config
CONFIG["col_image_pre_hook"] = col_image_pre_hook
CONFIG["col_image_extractor"] = col_image_extractor
CONFIG["profile_url_resolver"] = profile_url_resolver
CONFIG["chk_title_extractor"] = chk_title_extractor
CONFIG["chk_href_extractor"] = chk_href_extractor
CONFIG["chk_image_extractor"] = chk_image_extractor
CONFIG["upl_desc_resolver"] = None
CONFIG["upl_category_resolver"] = upl_category_resolver

# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    config=CONFIG,
    collector=collect_from_vinted,
    checker=check_on_vinted,
    uploader=upload_to_vinted
)