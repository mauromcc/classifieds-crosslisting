import os, sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def chrome_headless_options():
    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--window-size=1920,1080")
    o.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/127.0.0.0 Safari/537.36") #new
    o.add_argument(r"--user-data-dir=C:\\SeleniumProfile") # Erase this if chrome/vinted/wallapop detects bot
    o.add_argument("--disable-blink-features=AutomationControlled")
    o.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    o.add_experimental_option("useAutomationExtension", False)
    o.add_argument("--disable-gpu")
    o.add_argument("--log-level=3")
    o.add_argument("--silent")
    o.add_argument("--disable-logging")
    o.add_argument("--v=0")
    return o

def headless_driver():
    opts = chrome_headless_options()
    sys.stderr = open(os.devnull, "w")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    sys.stderr.close()
    sys.stderr = sys.__stderr__
    # Stealth
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    }) # new
    size = driver.get_window_size()
    print(f"🖥️ Current window size: width={size['width']}, height={size['height']}")
    driver._is_headless = True
    return driver

def is_headless(driver):
    return getattr(driver, "_is_headless", False)


def chrome_visible_options():
    o = Options()
    o.add_argument("--window-size=1920,1080")
    o.add_argument(r"--user-data-dir=C:\\SeleniumProfile")
    o.add_argument("--disable-blink-features=AutomationControlled")
    o.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    o.add_experimental_option("useAutomationExtension", False)
    o.add_argument("--disable-gpu")
    o.add_argument("--log-level=3")
    o.add_argument("--silent")
    o.add_argument("--disable-logging")
    o.add_argument("--v=0")
    return o

def visible_driver():  # full Chrome (non-headless) with stealth profile for uploading
    opts = chrome_visible_options()
    sys.stderr = open(os.devnull, "w") # Suppress chromedriver noise
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    sys.stderr.close()
    sys.stderr = sys.__stderr__
    # Stealth
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    driver.maximize_window()
    size = driver.get_window_size()
    print(f"🖥️ Current window size: width={size['width']}, height={size['height']}")
    driver._is_headless = False
    return driver




