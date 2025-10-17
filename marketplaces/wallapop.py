import time, re

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from constants import register_marketplace
from helpers.scraping import collect_listing_generic, check_listing_existence
from helpers.images import extract_images_generic
from helpers.uploader import upload_listing_generic
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.abort import check_abort


MARKETPLACE = "wallapop"

# ---------------------------
# Wallapop-specific configuration
# ---------------------------
CONFIG = {
    # URLs
    "home_url": "https://es.wallapop.com",
    "profile_url": "https://es.wallapop.com/app/catalog/published",
    "upload_url": "https://es.wallapop.com/app/catalog/upload/consumer-goods",
    
    "login_selector": (By.CSS_SELECTOR,"img[data-testid='user-avatar']"),
    
    # Collection selectors
    "use_driver_for_details": False,
    "col_title": ["h1", "class", "item-detail_ItemDetailTwoColumns__title__VtWrR"],
    "col_price": ["span", "class", "Price"],
    "col_price_filter": lambda x: x and "Price" in x,
    "col_description": ["meta", "name", "og:description"],
    "col_first_img": None,
    "col_carousel_imgs": None,
    "col_image_css": (By.CSS_SELECTOR, "img[slot='carousel-content']"),
    "col_image_filter": lambda src: src and "cdn.wallapop.com" in src and "W640" in src,
    "col_image_pre_hook": None, 
    
    # Check selectors
    "chk_items": (By.CSS_SELECTOR, "tsl-catalog-item a.item-details"),
    "chk_title": (By.CSS_SELECTOR, ".info-title"),
    "chk_image": [(By.XPATH, "./ancestor::div[contains(@class, 'row')]"), (By.CSS_SELECTOR, "div.ItemAvatar")],
    
    # Upload selectors
    "upl_title": (By.ID, "summary"),
    "upl_description": (By.ID, "description"),
    "upl_price": (By.ID, "sale_price"),
    "upl_category": (By.CSS_SELECTOR, 'div.walla-dropdown__inner-input[aria-label="Categoría y subcategoría"]'),
    "upl_category_first": (By.CSS_SELECTOR, 'div.sc-walla-dropdown-item'),
    "upl_category_open": None,
    "upl_image_input": (By.CSS_SELECTOR, 'input[type="file"]'),
    "upl_image_preview": (By.CSS_SELECTOR, "img[src^='data:']"),
    "upl_continue_btn": (By.CSS_SELECTOR, "walla-button[data-testid='continue-button']"),
    "upl_sequence": ["title", "continue_btn", "images", "continue_btn", "category", "description", "price"],
}


# ---------------------------
# Collector
# ---------------------------
def collect_from_wallapop(url: str) -> dict:
    """Collect listing from Wallapop."""
    return collect_listing_generic(url, MARKETPLACE, CONFIG)

def col_image_extractor(driver):
    """Extract images from Wallapop listing page."""
    return extract_images_generic(
        driver=driver,
        css_selector=CONFIG["col_image_css"],
        filter_func=CONFIG["col_image_filter"],
        pre_extract_hook=CONFIG["col_image_pre_hook"],
        marketplace=MARKETPLACE
    )


# ---------------------------
# Checker
# ---------------------------
def check_on_wallapop(listing) -> str | None:
    """Check if listing exists on Wallapop."""
    return check_listing_existence(listing, MARKETPLACE, CONFIG)

def profile_url_resolver(driver):
    """Wallapop uses a fixed profile URL."""
    return CONFIG["profile_url"]

def chk_title_extractor(item):
    """Extracts the title string for Wallapop items."""
    try:
        return item.find_element(*CONFIG["chk_title"]).text.strip()
    except:
        return None

def chk_href_extractor(item):
    """Extract href from Wallapop item."""
    return item.get_attribute("href")

def chk_image_extractor(item):
    """Extracts the main image URL for Wallapop items."""
    try:
        parent = item.find_element(*CONFIG["chk_image"][0])
        avatar_divs = parent.find_elements(*CONFIG["chk_image"][1])
        for avatar in avatar_divs:
            style = avatar.get_attribute("style")
            if "url(" in style:
                match = re.search(r'url\([\"]?([^\")]+)', style)
                if match:
                    return match.group(1).split("?")[0]
    except:
        return None
    return None


# ---------------------------
# Uploader
# ---------------------------
def upload_to_wallapop(listing: dict):
    """Upload listing to Wallapop."""
    print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
    driver = visible_driver()
    ensure_logged_in(driver, CONFIG["login_selector"], CONFIG["home_url"], MARKETPLACE)
    driver.get(CONFIG["upload_url"])
    
    return upload_listing_generic(driver, listing, MARKETPLACE, CONFIG)

def upl_desc_resolver(driver, desc_input, scraped_desc):
    """Handle Wallapop AI description (keep or replace)."""
    current_ai = desc_input.get_attribute("value").strip()

    print(f"\n📝 {MARKETPLACE.capitalize()} AI-generated description:\n---\n" + current_ai + "\n---")
    print("\n📝 Scraped description:\n---\n" + scraped_desc + "\n---")

    choice = input("👉 Keep AI (k) or Replace with scraped (r)? (k/r): ").strip().lower()
    if choice == "r":
        desc_input.clear()
        driver.execute_script("""
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        """, desc_input, scraped_desc)
        print("✅ Scraped description used")
        return False
    else:
        print("✅ Kept AI description")
        return True

def upl_category_resolver(driver, category_dropdown):
    """Check if Wallapop category dropdown is open."""
    try:
        return category_dropdown.get_attribute("aria-expanded") == "true"
    except Exception:
        return False



# Add extractors to config
CONFIG["col_image_extractor"] = col_image_extractor
CONFIG["profile_url_resolver"] = profile_url_resolver
CONFIG["chk_title_extractor"] = chk_title_extractor
CONFIG["chk_href_extractor"] = chk_href_extractor
CONFIG["chk_image_extractor"] = chk_image_extractor
CONFIG["upl_desc_resolver"] = upl_desc_resolver
CONFIG["upl_category_resolver"] = upl_category_resolver

# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    config=CONFIG,
    collector=collect_from_wallapop,
    checker=check_on_wallapop,
    uploader=upload_to_wallapop
)