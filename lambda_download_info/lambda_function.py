from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
from os import environ

URL: str = environ.get("URL", "https://www.tradingview.com/markets/stocks-usa/earnings")
logger = Logger()

def get_tradingview_earnings_today(url: str) -> list:
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    service = Service("/usr/bin/chromium-driver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'tv-data-table')]"))
        )

        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        rows = driver.find_elements(By.XPATH, "//table[contains(@class, 'tv-data-table')]//tr")
        earnings_list = []

        for row in rows[1:]:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 4:
                    continue

                symbol = cells[0].text.split()[0]
                company = " ".join(cells[0].text.split()[1:]).strip()
                eps = cells[2].text.strip()

                earnings_list.append({
                    "symbol": symbol,
                    "company": company,
                    "eps": eps
                })
            except:
                continue

        return earnings_list

    finally:
        driver.quit()

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: dict, context: LambdaContext) -> dict:

    logger.info("Starting earnings data retrieval from TradingView.")
    earnings_data = get_tradingview_earnings_today(URL)
    logger.info(f"Retrieved {len(earnings_data)} earnings entries.")

    if len(earnings_data) > 0:
        return {
            "statusCode": 200,
            "body": earnings_data
        }
    else:
        return {
            "statusCode": 500,
            "body": "No earnings data found for today."
        }
