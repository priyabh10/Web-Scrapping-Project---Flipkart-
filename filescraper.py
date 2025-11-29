from bs4 import BeautifulSoup
import requests
import pandas as pd
import ssl
import numpy as np
import time
import smtplib
import csv
from email.mime.text import MIMEText
from datetime import datetime

url = "https://www.flipkart.com/"
headers = ({"user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"})

res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")

category_choice = {
    1: "electronics",
    2: "tv_and_appliances",
    3: "men",
    4: "women",
    5: "baby_and_kids",
    6: "beauty_and_personal_care",
    7: "home_and_furniture",
    8: "sports",
    9: "books"
}

thresholds = {
    "electronics": 5000,
    "tv_and_appliances": 30000,
    "men": 2000,
    "women": 2500,
    "baby_and_kids": 1500,
    "beauty_and_personal_care": 800,
    "home_and_furniture": 10000,
    "sports": 3000,
    "books": 500
}

NAME_SELECTORS = {
    "electronics": ["a.pIpigb"],
    "tv_and_appliances": ["a.pIpigb"],
    "men": ["a.atJtCj Qum9aC","a.atJtCj"],
    "women": ["a.atJtCj","a.atJtCj Qum9aC"],
    "baby_and_kids": ["a.pIpigb"],
    "beauty_and_personal_care": ["a.pIpigb"],
    "home_and_furniture": ["a.pIpigb"],
    "sports": ["a.pIpigb"],
    "books": ["a.pIpigb"]
}

PRICE_SELECTORS = {
    "electronics": ["div.hZ3P6w"],
    "tv_and_appliances": ["div.hZ3P6w"],
    "men": ["div.hZ3P6w"],
    "women": ["div.hZ3P6w"],
    "baby_and_kids": ["div.hZ3P6w"],
    "beauty_and_personal_care": ["div.hZ3P6w"],
    "home_and_furniture": ["div.hZ3P6w"],
    "sports": ["div.hZ3P6w"],
    "books": ["div.hZ3P6w"]

}

# -----------------------------------------------------------
# SEND EMAIL ALERT
# -----------------------------------------------------------
def send_email_alert(product_name, old_price, new_price):
    sender = "priyankaabc1004@gmail.com"
    receiver = "priyanka.bh104@gmail.com"
    password = "**** **** **** ****" 
    message = f"""\
Subject: Price Drop Alert!

The price of {product_name} has dropped:
Old Price: ₹{old_price}
New Price: ₹{new_price}

Hurry before it increases!
"""

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)  # FIXED
        server.login(sender, password)
        server.sendmail(sender, receiver, message.encode("utf-8"))
        server.quit()
        print(f"Email alert sent for {product_name}")

    except Exception as e:
        print(f"[EMAIL ERROR] Could not send email: {e}")



def scrape_category(category):
    products = []

    for page in range(1, 4):   # scrape 3 pages
        try:
            url = f"https://www.flipkart.com/search?q={category}&page={page}"
            print("Scraping:", url)

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to get product name selectors safely
            name_tags = []
            try:
                for selector in NAME_SELECTORS.get(category, []):
                    name_tags.extend(soup.select(selector))
            except Exception as e:
                print(f"[WARNING] Name selector failed for {category} page {page}: {e}")
                continue  # skip page
            
            # Try to get price selectors safely
            price_tags = []
            try:
                for selector in PRICE_SELECTORS.get(category, []):
                    price_tags.extend(soup.select(selector))
            except Exception as e:
                print(f"[WARNING] Price selector failed for {category} page {page}: {e}")
                continue  # skip page

            # Loop through products safely
            for name_tag, price_tag in zip(name_tags, price_tags):
                try:
                    name = name_tag.get_text(strip=True)
                    price_raw = price_tag.get_text(strip=True)
                    price = price_raw.replace("₹", "").replace(",", "")

                    if price.isdigit():
                        products.append([category, name, int(price)])
                except Exception as e:
                    print(f"[SKIP PRODUCT] Error parsing product on {category}: {e}")
                    continue  # skip this product

        except Exception as e:
            print(f"[SKIP PAGE] Error scraping {category} page {page}: {e}")
            continue

    return products

# -----------------------------------------------------------
# SAVE CSV + CHECK PRICE DROP
# -----------------------------------------------------------
def save_data(products):
    filename = "flipkart_prices.csv"

    old_data = {}

    # Load previous data
    try:
        with open(filename, "r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                old_data[row[1]] = int(row[2])
    except FileNotFoundError:
        pass

    # Write new CSV (overwrite)
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Category", "Product Name", "Price"])

        for category, name, price in products:
            writer.writerow([category, name, price])

            # Compare prices
            if name in old_data:
                old_price = old_data[name]
                if price < old_price:
                    send_email_alert(name, old_price, price)

    print("CSV updated:", filename)


# -----------------------------------------------------------
# RUN EVERY 12 HOURS
# -----------------------------------------------------------
def main():
    while True:
        print("\n================================================")
        print("⌛ Running Flipkart Scraper:", datetime.now())
        print("================================================")

        all_products = []

        for cat_id, category in category_choice.items():
            cat_products = scrape_category(category)
            all_products.extend(cat_products)


        save_data(all_products)

        print("Sleeping for 12 hours...")
        time.sleep(12 * 60 * 60)  # 12 hours


if __name__ == "__main__":
    
    while True:
        try:
            print("\n------------------------------")
            print(" Running Flipkart Scraper...")
            print("------------------------------\n")

            main()  # your function that scrapes everything

            print("\nWaiting 12 hours before next run...\n")
            time.sleep(12 * 60 * 60)  # 12 hours

        except Exception as e:
            print(f"[CRITICAL ERROR] Script crashed: {e}")
            print("Retrying in 1 minute...")
            time.sleep(60)  # retry after 60 seconds

