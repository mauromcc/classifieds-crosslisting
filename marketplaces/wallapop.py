import time, re

from selenium.webdriver.common.by import By

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
COL_ITEM_HTML_DESCRIPTION = ["meta", "name", "og:description"]

CHK_PROFILE_ITEMS = "tsl-catalog-item a.item-details"
CHK_PROFILE_TITLE = ".info-title"
CHK_PROFILE_IMG = ["./ancestor::div[contains(@class, 'row')]", "div.ItemAvatar"]

UPL_ITEM_TITLE = (By.ID, "summary")
UPL_ITEM_DESCRIPTION = (By.ID, "description")
UPL_ITEM_PRICE = (By.ID, "sale_price")
UPL_ITEM_CONTINUE_BTN = (By.CSS_SELECTOR, "walla-button[data-testid='continue-button']")
UPL_ITEM_CATEGORY = (By.CSS_SELECTOR, 'div.walla-dropdown__inner-input[aria-label="Categoría y subcategoría"]')
UPL_ITEM_CATEGORY_OPTION = (By.CSS_SELECTOR, 'div.sc-walla-dropdown-item')
UPL_ITEM_FILE = (By.CSS_SELECTOR, 'input[type="file"]')
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
    return collect_listing_generic(
        url,
        MARKETPLACE,
        COL_ITEM_HTML_TITLE,
        COL_ITEM_HTML_PRICE,
        COL_ITEM_HTML_DESCRIPTION,
        price_filter=lambda x: x and COL_ITEM_HTML_PRICE[2] in x
    )


# ---------------------------
# Checker
# ---------------------------
def check_on_wallapop(listing) -> str | None:
    return check_listing_existence(
        listing,
        MARKETPLACE,
        LOGIN_SELECTOR,
        HOME_URL,
        wallapop_profile_resolver,
        CHK_PROFILE_ITEMS,
        CHK_PROFILE_TITLE,
        CHK_PROFILE_IMG,
        wallapop_title_extractor,
        wallapop_image_extractor
    )

def wallapop_profile_resolver(driver):
    return PROFILE_URL

def wallapop_title_extractor(item, chk_title):
    """Extracts the title string for Wallapop items."""
    try:
        return item.find_element(By.CSS_SELECTOR, chk_title).text.strip()
    except:
        return None

def wallapop_image_extractor(item, chk_img):
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

    selectors = {
        "title": UPL_ITEM_TITLE,
        "description": UPL_ITEM_DESCRIPTION,
        "price": UPL_ITEM_PRICE,
        "category": UPL_ITEM_CATEGORY,
        "category_option": UPL_ITEM_CATEGORY_OPTION,
        "file_input": UPL_ITEM_FILE,
        "continue_btn": UPL_ITEM_CONTINUE_BTN
    }

    upload_listing_generic(driver, listing, selectors, marketplace=MARKETPLACE, sequence=UPLOAD_SEQUENCE)
    return driver



# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    collector=collect_from_wallapop,
    checker=check_on_wallapop,
    uploader=upload_to_wallapop
)