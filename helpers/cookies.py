import os, time, pickle

from selenium.webdriver.common.by import By

from constants import SCRIPT_DIR
from helpers.abort import check_abort
from helpers.drivers import visible_driver, headless_driver, is_headless



def cookie_path(marketplace: str) -> str:
    """Return the path where cookies for a given marketplace are stored."""
    cookies_dir = os.path.join(SCRIPT_DIR, "cookies")
    os.makedirs(cookies_dir, exist_ok=True)
    return os.path.join(cookies_dir, f"{marketplace}_cookies.pkl")

def save_cookies(driver, marketplace: str):
    """Save cookies from a Selenium driver into a pickle file."""
    path = cookie_path(marketplace)
    cookies = driver.get_cookies() or []
    if not cookies:
        print(f"⚠️ No cookies found to save for {marketplace.capitalize()}.")
        return
    with open(path, "wb") as f:
        pickle.dump(cookies, f)
    print(f"🍪 Saved {len(cookies)} cookies for {marketplace.capitalize()}")

def load_cookies(driver, marketplace: str) -> list:
    """Load cookies from file, return them or empty list if not available."""
    path = cookie_path(marketplace)
    if not os.path.exists(path):
        print(f"⚠️ No cookie file found for {marketplace.capitalize()}.")
        return []

    try:
        with open(path, "rb") as f:
            cookies = pickle.load(f)
            print(f"🍪 Loaded {len(cookies)} cookies from file for {marketplace.capitalize()}")
            return cookies
    except (EOFError, pickle.UnpicklingError, Exception) as e:
        print(f"⚠️ Cookie file is empty or corrupted for {marketplace.capitalize()}: {e}")
        return []

def apply_cookies(driver, cookies: list, homepage_url: str, marketplace: str):
    """Apply cookies to driver and reload homepage."""
    if not cookies:
        print(f"⚠️ No cookies to apply for {marketplace.capitalize()}.")
        return False

    if check_abort(driver): 
        return None

    try:
        driver.get(homepage_url)
        time.sleep(0.5)
    except Exception as e:
        print(f"⚠️ Could not open homepage before adding cookies: {e}")

    added, failed = 0, 0
    failed_details = []

    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            added += 1
        except Exception as e1:
            try:
                c = dict(cookie)
                for k in ("sameSite", "same_site", "hostOnly"):
                    c.pop(k, None)
                driver.add_cookie(c)
                added += 1
            except Exception as e2:
                failed += 1
                failed_details.append({
                    "name": cookie.get("name"),
                    "domain": cookie.get("domain"),
                    "reason1": str(e1),
                    "reason2": str(e2),
                })
                continue
    print(f"✅ Cookies applied: {added}, failed: {failed}")

    # if failed:
    #     print(f"⚠️ Failed cookies for {marketplace.capitalize()}:")
    #     for f in failed_details:
    #         print(f"   - {f['name']} ({f['domain']}) | reason1={f['reason1']} | reason2={f['reason2']}")

    if check_abort(driver): 
        return None

    driver.get(homepage_url)
    time.sleep(2)
    return added > 0

def is_logged_in(driver, login_check_selector: str) -> bool:
    """Check if logged in by looking for an element that only exists when logged in."""
    try:
        driver.find_element(By.CSS_SELECTOR, login_check_selector)
        return True
    except:
        return False

def ensure_logged_in(driver, login_check_selector: str, homepage_url: str, marketplace: str, force_visible_if_needed=True):
    """
    Ensure user is logged in:
    - Always opens homepage
    - If already logged in, just save cookies and continue
    - Otherwise tries cookies, then manual login
    - Keeps cookie file fresh on every successful login
    Always returns:
        - webdriver instance (headless or visible)
        - None if login failed
    """
    print(f"🌍 Confirming if logged in on {marketplace.capitalize()}...")
    driver.get(homepage_url)
    time.sleep(2)

    if check_abort(driver): 
        return None

    # Step 0: Already logged in without cookies
    if is_logged_in(driver, login_check_selector):
        print(f"🟢 Already logged in on {marketplace.capitalize()} (no cookies needed).")
        save_cookies(driver, marketplace)
        return driver
    print(f"🔴 Not logged in on {marketplace.capitalize()}.")

    # Step 1: Try existing cookies
    cookies = load_cookies(driver, marketplace)
    if apply_cookies(driver, cookies, homepage_url, marketplace):
        if is_logged_in(driver, login_check_selector):
            print(f"✅ Using saved cookies for {marketplace.capitalize()}.")
            save_cookies(driver, marketplace)
            return driver

    # Step 2: Manual login if cookies fail
    if not force_visible_if_needed:
        print(f"🔴 Not logged in on {marketplace.capitalize()}. Run once in visible mode first.")
        return None

    if is_headless(driver):
        print(f"🌍 Headless browser detected. Launching visible browser for manual login on {marketplace.capitalize()}...")
        try:
            driver.quit()
        except Exception:
            pass

        visible = visible_driver()
        visible.get(homepage_url)
        time.sleep(2)

        input(f"❗ Please log in manually in the opened browser window for {marketplace.capitalize()}.\n👉 Press Enter here once you're logged in...")

        if is_logged_in(visible, login_check_selector):
            print(f"✅ Manual login successful. Saving cookies...")
            save_cookies(visible, marketplace)
            try:
                visible.quit()
            except Exception:
                pass

            # Re-launch headless driver
            print(f"🌍 Back to headless mode with logged-in session.")
            driver = headless_driver()
            if check_abort():
                return None
            driver.get(homepage_url)
            apply_cookies(driver, load_cookies(driver, marketplace), homepage_url, marketplace)
            time.sleep(2)
            return driver 

        else:
            print(f"❌ Manual login failed.")
            return None

    else:
        print(f"🌍 Using already visible browser for manual login on {marketplace.capitalize()}...")
        input(f"❗ Please log in manually in the opened browser window on {marketplace.capitalize()}.\n👉 Press Enter here once you're logged in...")
        
        if check_abort(driver): 
            return None

        if is_logged_in(driver, login_check_selector):
            print(f"✅ Manual login successful on {marketplace.capitalize()}. Saving cookies...")
            save_cookies(driver, marketplace)
            return driver

        print(f"❌ Login still not detected on {marketplace.capitalize()}.")
        return None

