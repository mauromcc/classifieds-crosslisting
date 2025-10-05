import re, time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from helpers.abort import check_abort


def upload_listing_generic(driver, listing: dict, marketplace: str, upl_selectors: dict, upl_sequence: list):
    """
    Fill in listing for any marketplace given a dictionary of selectors.
    Expected selectors keys: title, description, price, category, category_option, file_input, continue_btn (optional)
    """
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img")))
    except Exception:
        pass

    for step in upl_sequence:
        if check_abort(driver):
            return None

        if step == "images":
            print("⏳ Uploading images...")
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located(upl_selectors["upl_image_input"]))
                driver.find_element(*upl_selectors["upl_image_input"]).send_keys("\n".join(listing["images"]))
            except Exception as e:
                print(f"⚠️ Error uploading images: {e}")
                input("👉 Upload images manually, then press Enter to continue...")

            while True:
                try:
                    previews = WebDriverWait(driver, 10).until(EC.presence_of_element_located(upl_selectors["upl_image_preview"]))
                except Exception:
                    pass
                if previews:
                    print("✅ Images uploaded")
                    break
                else:
                    if check_abort(driver):
                        return None
                    print("⚠️ No images were uploaded (maybe wrong format like SVG?)")
                    input("👉 Upload images manually, then press Enter to continue...")
            
        elif step == "title":
            while True:
                try:
                    title_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(upl_selectors["upl_title"]))
                    title_input.clear()
                    driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].blur();
                    """, title_input, listing["title"])
                except Exception as e:
                    print("⚠️ Title not filled automatically:", e)
                # verify
                try:
                    val = title_input.get_attribute("value") or title_input.get_attribute("textContent") or title_input.text or ""
                except Exception:
                    val = ""
                if listing["title"] == val:
                    print("✅ Title filled")
                    break
                input("👉 Fill title manually, then press Enter to continue...")

        elif step == "description":
            while True:
                try:
                    desc_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(upl_selectors["upl_description"]))
                    keep_ai = False
                    if upl_selectors["upl_desc_resolver"]:
                        keep_ai = upl_selectors["upl_desc_resolver"](driver=driver, desc_input=desc_input, scraped_desc=listing["description"])
                    else:
                        desc_input.clear()
                        driver.execute_script("""
                        arguments[0].focus();
                        arguments[0].value = arguments[1];
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        arguments[0].blur();
                        """, desc_input, listing["description"])
                except Exception as e:
                    print("⚠️ Description not filled:", e)
                # verify
                try:
                    val = desc_input.get_attribute("value") or desc_input.get_attribute("textContent") or desc_input.text or ""
                except Exception:
                    val = ""
                if keep_ai or listing["description"] in val:
                    print("✅ Description filled")
                    break

                input("👉 Fill description manually, then press Enter to continue...")

        elif step == "price":
            while True:
                try:
                    price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
                    price_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(upl_selectors["upl_price"]))
                    price_input.clear()
                    driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].blur();
                    """, price_input, price_cleaned)
                except Exception as e:
                    print("⚠️ Price not filled automatically:", e)
                # verify
                try:
                    val = price_input.get_attribute("value") or price_input.get_attribute("textContent") or price_input.text or ""
                except Exception:
                    val = ""
                if price_cleaned and price_cleaned in val:
                    print("✅ Price filled")
                    break

                input("👉 Fill price manually, then press Enter to continue...")

        elif step == "category":
            try:
                category_dropdown = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(upl_selectors["upl_category"]))
                category_dropdown.click()
                time.sleep(0.5)
                print("✅ Category dropdown opened")
            except Exception as e:
                print("⚠️ Could not click category dropdown:", e)
                input("👉 Open category dropdown manually, then press Enter to continue...")
                continue   

            max_attempts = 5
            attempts = 0
            while True:
                attempts += 1
                if attempts > max_attempts:
                    print("⚠️ Could not select category after multiple attempts.")
                    input("👉 Select category manually, then press Enter to continue...")
                    break
                try:
                    dropdown_is_open = upl_selectors["upl_category_resolver"](driver, category_dropdown)
                    if dropdown_is_open:
                        time.sleep(0.5)
                        first_option = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(upl_selectors["upl_category_first"]))
                        first_option.click()
                        print("✅ First recommended category selected")
                    else:
                        time.sleep(1)
                        print("✅ Category dropdown closed")
                        break 
                except Exception as e:
                    print("⚠️ Could not select first category option:", e)
                    input("👉 Select category manually, then press Enter to continue...")

        elif step == "continue_btn":
            try:
                btns = driver.find_elements(*upl_selectors["upl_continue_btn"])
                for btn in reversed(btns):
                    try:
                        WebDriverWait(driver, 10).until(lambda d: 
                            btn.get_attribute("disabled") in [None, "false"] or
                            btn.get_attribute("aria-disabled") == "false"
                        )
                    except:
                        print("⚠️ Continue button did not become enabled in time")
                        input("👉 Please make sure required fields are filled, then press Enter to continue...")
                    try:
                        btn.click()
                        print("✅ Clicked on the 'Continue' button")
                        time.sleep(0.5)
                        break
                    except Exception as e:
                        print(f"⚠️ Could not click Continue button: {e}")
                        continue
            except Exception as e:
                print(f"⚠️ Could not find Continue button: {e}")
                input("👉 Check manually, then press Enter to continue...")

    print(f"🎉 Listing ready on {marketplace.capitalize()} for review and publish.")
    return driver
