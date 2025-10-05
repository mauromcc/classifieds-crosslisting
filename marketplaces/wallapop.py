import time, re

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from constants import register_marketplace
from helpers.scraping import collect_listing_generic, check_listing_existence, find_listing_in_profile
from helpers.uploader import upload_listing_generic
from helpers.drivers import headless_driver, visible_driver
from helpers.cookies import ensure_logged_in
from helpers.abort import check_abort


MARKETPLACE = "wallapop"

# ---------------------------
# URLs & Selectors
# ---------------------------
HOME_URL = "https://es.wallapop.com"
PROFILE_URL = "https://es.wallapop.com/app/catalog/published"
UPLOAD_URL = "https://es.wallapop.com/app/catalog/upload/consumer-goods"
LOGIN_SELECTOR = "img[data-testid='user-avatar']"

COL_ITEM_HTML_TITLE = "h1"
COL_ITEM_HTML_PRICE = ["span", "class", "Price"]
COL_ITEM_PRICE_FILTER = lambda x: x and COL_ITEM_HTML_PRICE[2] in x
COL_ITEM_HTML_DESCRIPTION = ["meta", "name", "og:description"]

CHK_PROFILE_ITEMS = "tsl-catalog-item a.item-details"
CHK_PROFILE_TITLE = ".info-title"
CHK_PROFILE_IMG = ["./ancestor::div[contains(@class, 'row')]", "div.ItemAvatar"]

UPL_ITEM_TITLE = (By.ID, "summary")
UPL_ITEM_DESCRIPTION = (By.ID, "description")
UPL_ITEM_PRICE = (By.ID, "sale_price")
UPL_ITEM_CONTINUE_BTN = (By.CSS_SELECTOR, "walla-button[data-testid='continue-button']")
UPL_ITEM_CATEGORY = (By.CSS_SELECTOR, 'div.walla-dropdown__inner-input[aria-label="Categoría y subcategoría"]')
UPL_ITEM_CATEGORY_FIRST = (By.CSS_SELECTOR, 'div.sc-walla-dropdown-item')
UPL_ITEM_IMG_INPUT = (By.CSS_SELECTOR, 'input[type="file"]')
UPL_ITEM_IMG_PREVIEW = (By.CSS_SELECTOR, "img[src^='data:']")
UPLOAD_SEQUENCE = [
    "title",
    "continue_btn",
    "images",
    "continue_btn",
    "category",
    "description",
    "price"
]





# ---------------------------
# Collector
# ---------------------------
def collect_from_wallapop(url: str) -> dict:
    col_selectors = {
        "col_title": COL_ITEM_HTML_TITLE,
        "col_price": COL_ITEM_HTML_PRICE,
        "col_price_filter": COL_ITEM_PRICE_FILTER,
        "col_description": COL_ITEM_HTML_DESCRIPTION,
        "col_img_extractor": wallapop_collect_img_extractor,
    }
    return collect_listing_generic(
        url=url,
        marketplace=MARKETPLACE,
        col_selectors=col_selectors
    )

def wallapop_collect_img_extractor(driver):
    images = []
    elems = driver.find_elements(By.CSS_SELECTOR, "img")
    seen = set()
    for i in range(len(elems)):
        try:
            img = elems[i]
            src = img.get_attribute("src")
            if src and src not in seen and "cdn.wallapop.com" in src and "W640" in src:
                images.append(src)
                seen.add(src)
        except StaleElementReferenceException as e:
            print(f"⚠️ Error retrieving {MARKETPLACE.capitalize()} listing's images: {e}")
            continue

    return images


# ---------------------------
# Checker
# ---------------------------
def check_on_wallapop(listing) -> str | None:
    chk_selectors = {
        "home_url": HOME_URL,
        "login_selector": LOGIN_SELECTOR,
        "profile_url_resolver": wallapop_profile_resolver,
        "chk_items": CHK_PROFILE_ITEMS,
        "chk_title": CHK_PROFILE_TITLE,
        "chk_img": CHK_PROFILE_IMG,
        "chk_title_extractor": wallapop_check_title_extractor,
        "chk_href_extractor": wallapop_check_href_extractor,
        "chk_image_extractor": wallapop_check_img_extractor,
    }
    return check_listing_existence(
        listing=listing,
        marketplace=MARKETPLACE,
        chk_selectors=chk_selectors
    )

def wallapop_profile_resolver(driver):
    return PROFILE_URL

def wallapop_check_title_extractor(item, chk_title):
    """Extracts the title string for Wallapop items."""
    try:
        return item.find_element(By.CSS_SELECTOR, chk_title).text.strip()
    except:
        return None

def wallapop_check_href_extractor(item, chk_title=None):
    return item.get_attribute("href")

def wallapop_check_img_extractor(item, chk_img):
    """Extracts the main image URL for Wallapop items."""
    try:
        parent = item.find_element(By.XPATH, chk_img[0])
        avatar_divs = parent.find_elements(By.CSS_SELECTOR, chk_img[1])
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
    print(f"🌍 Opening {MARKETPLACE.capitalize()} upload page...")
    driver = visible_driver()
    ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
    driver.get(UPLOAD_URL)

    upl_selectors = {
        "upl_title": UPL_ITEM_TITLE,
        "upl_description": UPL_ITEM_DESCRIPTION,
        "upl_desc_resolver": wallapop_upload_desc_resolver,
        "upl_price": UPL_ITEM_PRICE,
        "upl_category": UPL_ITEM_CATEGORY,
        "upl_category_first": UPL_ITEM_CATEGORY_FIRST,
        "upl_category_resolver": wallapop_upload_category_resolver,
        "upl_image_input": UPL_ITEM_IMG_INPUT,
        "upl_image_preview": UPL_ITEM_IMG_PREVIEW,
        "upl_continue_btn": UPL_ITEM_CONTINUE_BTN
    }

    upload_listing_generic(
        driver=driver, 
        listing=listing,
        marketplace=MARKETPLACE, 
        upl_selectors=upl_selectors,
        upl_sequence=UPLOAD_SEQUENCE, 
    )

    return driver

def wallapop_upload_desc_resolver(driver, desc_input, scraped_desc):
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
    else:
        print("✅ Kept AI description")
        return True

    return False

def wallapop_upload_category_resolver(driver, category_dropdown):
    try:
        return category_dropdown.get_attribute("aria-expanded") == "true"
    except Exception:
        return False
    

# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    collector=collect_from_wallapop,
    checker=check_on_wallapop,
    uploader=upload_to_wallapop
)