import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from helpers.abort import check_abort


def upload_listing_common(driver, listing: dict, selectors: dict):
    """
    Fill in listing for any marketplace given a dictionary of selectors.
    Expected selectors keys: title, description, price, category, category_option, file_input, continue_btn (optional)
    """
    if check_abort(driver):
        return None

    # Images
    try:
        driver.find_element(By.CSS_SELECTOR, selectors["file_input"]).send_keys("\n".join(listing["images"]))
        print("✅ Images uploaded")
    except Exception as e:
        print(f"⚠️ Error uploading images: {e}")
        input("👉 Upload images manually, then press Enter to continue...")

    if check_abort(driver):
        return None

    # Title
    try:
        title_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, selectors["title"]))
        )
        title_input.clear()
        title_input.send_keys(listing["title"])
        print("✅ Title filled")
    except Exception as e:
        print("⚠️ Title not filled automatically:", e)
        input("👉 Fill title manually, then press Enter to continue...")

    if check_abort(driver):
        return None

    # Description
    try:
        desc_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, selectors["description"]))
        )
        desc_input.clear()
        desc_input.send_keys(listing["description"])
        print("✅ Description filled")
    except Exception as e:
        print("⚠️ Description not filled automatically:", e)
        input("👉 Fill description manually, then press Enter to continue...")

    if check_abort(driver):
        return None

    # Price
    try:
        price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
        price_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, selectors["price"]))
        )
        price_input.clear()
        price_input.send_keys(price_cleaned)
        print("✅ Price filled")
    except Exception as e:
        print("⚠️ Price not filled automatically:", e)
        input("👉 Fill price manually, then press Enter to continue...")

    if check_abort(driver):
        return None

    # Category
    try:
        category_dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selectors["category"]))
        )
        category_dropdown.click()
        time.sleep(0.5)
        first_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selectors["category_option"]))
        )
        first_option.click()
        print("✅ Category selected")
    except Exception as e:
        print("⚠️ Category not selected automatically:", e)
        input("👉 Select category manually, then press Enter to continue...")

    # Continue buttons if provided
    if "continue_btn" in selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, selectors["continue_btn"])
            for btn in btns:
                try:
                    btn.click()
                    print("✅ Clicked a 'Continue' button")
                    time.sleep(0.5)
                except:
                    continue
        except:
            pass

    print("🎉 Listing ready for review and publish.")
    return driver
