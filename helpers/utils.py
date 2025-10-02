import time
from difflib import SequenceMatcher
from contextlib import contextmanager
from selenium.webdriver.remote.webdriver import WebDriver

from herlper.drivers import headless_driver, visible_driver



def is_match(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Return True if two titles are similar enough (default ≥85%)."""
    if not title1 or not title2:
        return False
    ratio = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    return ratio >= threshold  # Title matching

def vinted_title_shorten(raw_title: str) -> str:
    """Return substring up to the comma immediately before the first ':' if present,
       otherwise return the whole raw_title trimmed."""
    if not raw_title:
        return raw_title
    colon_idx = raw_title.find(":")
    if colon_idx == -1:
        return raw_title.strip()
    # find last comma before the colon
    comma_before = raw_title.rfind(",", 0, colon_idx)
    if comma_before != -1:
        return raw_title[:comma_before].strip()
    # fallback to up-to-colon (if no comma)
    return raw_title[:colon_idx].strip()



def scroll_to_load_all_items(driver: WebDriver, item_selector: str) -> list:
    wait = 0.5
    rounds_no_new = 0
    max_no_change_rounds = 10

    last_height = driver.execute_script("return document.body.scrollHeight")
    rounds_no_change = 0

    while rounds_no_change < max_no_change_rounds:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height > last_height:
            last_height = new_height
            rounds_no_change = 0
        else:
            rounds_no_change += 1

    items = driver.find_elements("css selector", item_selector)
        

    return items


@contextmanager
def managed_driver(headless: bool = True):
    """
    Context manager for Selenium driver.
    Always quits driver at the end, even on exceptions.
    """
    driver = None
    try:
        driver = headless_driver() if headless else visible_driver()
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
