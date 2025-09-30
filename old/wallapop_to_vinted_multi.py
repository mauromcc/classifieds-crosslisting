
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

wallapop_urls = input("Paste Wallapop URLs separated by commas or newlines:\n").replace(',', '\n').split('\n')
wallapop_urls = [url.strip() for url in wallapop_urls if url.strip()]


# Open new real chrome browser
chrome_options = Options()
chrome_options.add_argument(r"--user-data-dir=C:\\SeleniumProfile")

# Make Selenium look less like a bot
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

# Launch Chrome visibly (not headless)
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Stealth script to hide webdriver
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined
    })
    """
})

for url in wallapop_urls:
    print(f"\nProcessing: {url}")

    ### Load url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("Page loaded successfully.")
    else:
        print("Error loading page:", response.status_code)


    ### Retrieve text data
    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.find("h1")
    price_tag = soup.find("span", {"class": lambda x: x and "Price" in x})
    desc_meta = soup.find("meta", attrs={"name": "og:description"})

    title = title_tag.get_text(strip=True) if title_tag else "N/A"
    price = price_tag.get_text(strip=True) if price_tag else "N/A"
    description = desc_meta["content"].strip() if desc_meta else "N/A"

    print("Title:", title)
    print("Price:", price)
    print("Description:", description)


    ### Retrieve images
    # Function to download images
    def download_image(url, folder="temp_images"):
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename = url.split("/")[-1].split("?")[0]
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            response = requests.get(url)
            with open(path, "wb") as f:
                f.write(response.content)
        return path

    # Launch headless browser for scraping Wallapop pictures
    wallapop_options = Options()
    wallapop_options.add_argument("--headless=new")
    wallapop_options.add_argument("--disable-blink-features=AutomationControlled")

    wallapop_driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=wallapop_options)
    wallapop_driver.get(url)
    time.sleep(3)  # wait for page to load

    # Extract image URLs
    img_elements = wallapop_driver.find_elements(By.CSS_SELECTOR, "img")
    image_urls = []
    for img in img_elements:
        src = img.get_attribute("src")
        if src and "cdn.wallapop.com" in src and "W640" in src:
            if src not in image_urls:  # avoid duplicates
                image_urls.append(src)

    wallapop_driver.quit()

    # Images output
    image_urls = list(dict.fromkeys(image_urls))
    print(f"Downloaded {len(image_urls)} images:")
    for url in image_urls:
        print("-", url)
    local_images = [os.path.abspath(download_image(url)) for url in image_urls]
    folder_path = os.path.abspath("temp_images")
    print(f"📂 Downloaded images to: {folder_path.replace(os.sep, '/')}")


    
    ### Open Vinted upload new item page
    # Open a new tab for Vinted upload page
    driver.execute_script("window.open('https://www.vinted.es/items/new', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])  # Go to the new tab
    time.sleep(5)


    ### Upload details to new Vinted item
    # Images
    try:
        upload_input = driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
        files_string = "\n".join(local_images)  # Join image paths into a single newline-separated string
        upload_input.send_keys(files_string)  # Upload images
        time.sleep(5)
    except Exception as e:
        print("Error uploading images:", e)

    # Title field
    try:
        title_input = driver.find_element(By.ID, "title")
        title_input.clear()
        title_input.send_keys(title)
    except Exception as e:
        print("Error filling title:", e)

    # Description field
    try:
        description_input = driver.find_element(By.ID, "description")
        description_input.clear()
        description_input.send_keys(description)
    except Exception as e:
        print("Error filling description:", e)

    # Price field
    try:
        price_input = driver.find_element(By.ID, "price")
        price_input.clear()
        price_input.send_keys(price)
    except Exception as e:
        print("Error filling price:", e)

    # Category field
    try:
        # 1. Click the category input to open suggestions
        category_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "category")))
        category_input.click()

        # 2. Wait for the modal to appear with category list
        first_suggestion = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[id^='catalog-suggestion-']")))

        # 3. Click the first suggested category
        first_suggestion.click()
    except Exception as e:
        print("❌ Error selecting category:", e)


input("\nProcess finished. Press Enter to exit...")