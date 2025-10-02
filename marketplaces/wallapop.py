import time, re

from selenium.webdriver.common.by import By

from helpers.scraping import collect_listing_generic, check_listing_existence, find_listing_in_profile
from helpers.uploader import upload_listing_common
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

SEL_PROFILE_ITEMS = "tsl-catalog-item a.item-details"
SEL_PROFILE_TITLE = ".info-title"
SEL_PROFILE_IMG = ["./ancestor::div[contains(@class, 'row')]", "div.ItemAvatar"]

SEL_UPLOAD_TITLE = "summary"
SEL_UPLOAD_DESCRIPTION = "description"
SEL_UPLOAD_PRICE = "sale_price"
SEL_UPLOAD_CONTINUE_BTN = "walla-button[data-testid='continue-button']"
SEL_UPLOAD_CATEGORY = 'div.walla-dropdown__inner-input[aria-label="Categoría y subcategoría"]'
SEL_UPLOAD_CATEGORY_OPTION = 'div.sc-walla-dropdown-item'
SEL_UPLOAD_FILE = 'input[type="file"]'

# ---------------------------
# Register this marketplace
# ---------------------------
register_marketplace(
    MARKETPLACE,
    collector=collect_from_wallapop,
    checker=check_on_wallapop,
    uploader=upload_to_wallapop
)




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
        SEL_PROFILE_ITEMS,
        SEL_PROFILE_TITLE,
        SEL_PROFILE_IMG,
        wallapop_title_extractor,
        wallapop_image_extractor
    )

def wallapop_profile_resolver(driver):
    return PROFILE_URL

def wallapop_title_extractor(item, sel_title):
    """Extracts the title string for Wallapop items."""
    try:
        return item.find_element(By.CSS_SELECTOR, sel_title).text.strip()
    except:
        return None

def wallapop_image_extractor(item, sel_img):
    """Extracts the main image URL for Wallapop items."""
    try:
        parent = item.find_element(By.XPATH, sel_img[0])
        avatar_divs = parent.find_elements(By.CSS_SELECTOR, sel_img[1])
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
    driver = visible_driver()
    ensure_logged_in(driver, LOGIN_SELECTOR, HOME_URL, MARKETPLACE)
    driver.get(UPLOAD_URL)
    time.sleep(5)

    selectors = {
        "title": SEL_UPLOAD_TITLE,
        "description": SEL_UPLOAD_DESCRIPTION,
        "price": SEL_UPLOAD_PRICE,
        "category": SEL_UPLOAD_CATEGORY,
        "category_option": SEL_UPLOAD_CATEGORY_OPTION,
        "file_input": SEL_UPLOAD_FILE,
        "continue_btn": SEL_UPLOAD_CONTINUE_BTN
    }

    upload_listing_common(driver, listing, selectors)
    return driver
