import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from helpers.abort import check_abort


def upload_listing_generic(driver, listing: dict, selectors: dict, marketplace: str, sequence: list):
    """
    Fill in listing for any marketplace given a dictionary of selectors.
    Expected selectors keys: title, description, price, category, category_option, file_input, continue_btn (optional)
    """
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img")))
    except Exception:
        pass

    for step in sequence:
        if check_abort(driver):
            return None

        if step == "images":
            print("⏳ Uploading images...")
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located(selectors["file_input"]))
                driver.find_element(*selectors["file_input"]).send_keys("\n".join(listing["images"]))
                time.sleep(1)  # wait for previews to appear
            except Exception as e:
                print(f"⚠️ Error uploading images: {e}")
                input("👉 Upload images manually, then press Enter to continue...")
            # Keep asking until previews exist
            while True:
                previews = driver.find_elements(By.CSS_SELECTOR, "img[src^='data:']") # turn it into a selector
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
                    title_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(selectors["title"])
                    )
                    title_input.clear()
                    title_input.send_keys(listing["title"])
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
                    desc_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located(selectors["description"]))
                    if marketplace == "wallapop":
                        current_ai = desc_input.get_attribute("value").strip()

                        print(f"\n📝 {marketplace.capitalize()} AI-generated description:\n---\n" + current_ai + "\n---")
                        print("\n📝 Scraped description:\n---\n" + listing["description"] + "\n---")
                        choice = input("👉 Keep AI (k) or Replace with scraped (r)? (k/r): ").strip().lower()
                        if choice == "r":
                            desc_input.clear()
                            desc_input.send_keys(listing["description"])
                            print("✅ Scraped description used")
                        else:
                            print("✅ Kept AI description")  
                    else:
                        desc_input.clear()
                        desc_input.send_keys(listing["description"])
                except Exception as e:
                    print("⚠️ Description not filled:", e)
                # verify
                try:
                    val = desc_input.get_attribute("value") or desc_input.get_attribute("textContent") or desc_input.text or ""
                except Exception:
                    val = ""
                if listing["description"] in val:
                    print("✅ Description filled")
                    break

                input("👉 Fill description manually, then press Enter to continue...")

        elif step == "price":
            while True:
                try:
                    price_cleaned = listing["price"].replace("€", "").replace(",", ".").strip()
                    price_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(selectors["price"])
                    )
                    price_input.clear()
                    price_input.send_keys(price_cleaned)
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
            while True:
                try:
                    try:
                        category_dropdown = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(selectors["category"]))
                        category_dropdown.click()
                        print("✅ Category dropdown opened")
                    except Exception as e:
                        print("⚠️ Could not click category dropdown:", e)
                        input("👉 Open category dropdown manually, then press Enter to continue...")
                        continue

                    try:
                        first_option = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(selectors["category_option"]))
                        first_option.click()
                        print("✅ First recommended category selected")
                        break
                    except Exception as e:
                        print("⚠️ Could not select first category option:", e)
                        input("👉 Select category manually, then press Enter to continue...")

                except Exception as e:
                    print("⚠️ Category could not be selected:", e)
                    input("👉 Select category manually, then press Enter to continue...")

        elif step == "continue_btn":
            try:
                btns = driver.find_elements(*selectors["continue_btn"])
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
