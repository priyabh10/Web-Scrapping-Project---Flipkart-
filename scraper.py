from bs4 import BeautifulSoup
import requests
import pandas as pd
import ssl
import numpy as np
import time
import smtplib
import csv
import schedule
import json
from email.mime.text import MIMEText
from datetime import datetime
from pymongo import MongoClient
from flask import Flask, render_template, jsonify, request
from threading import Thread


client = MongoClient("mongodb://localhost:27017/")
db = client["flipkart"]
collection = db["products"]
alerts_collection = db["email_alert"]

# store only alerts created during current scraper run
new_alerts_cache = []


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
    "electronics": 1,
    "tv_and_appliances": 1,
    "men": 1,
    "women":1,
    "baby_and_kids": 1,
    "beauty_and_personal_care": 1,
    "home_and_furniture": 1,
    "sports": 1,
    "books": 1
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

# -------------------------
# Load config.json
# -------------------------
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

SENDER = CONFIG["email_sender"]
PASSWORD = CONFIG["email_password"]
RECEIVER = CONFIG["email_receiver"]
DROP_THRESHOLD = CONFIG["price_drop_threshold"]
RUN_INTERVAL = CONFIG["run_interval_hours"]

# -----------------------------------------------------------
# SEND EMAIL ALERT
# -----------------------------------------------------------
def send_email_alert(name, old_price, price,link):
    sender = "priyankaabc1004@gmail.com"
    receiver = "priyanka.bh104@gmail.com"
    password = "" 
    message = f"""\
Subject: Price Drop Alert!

The price of {name} has dropped:
Old Price: ₹{old_price}
New Price: ₹{price}

Hurry before it increases!
Buy Now: {link}
"""

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)  # FIXED
        server.login(sender, password)
        server.sendmail(sender, receiver, message.encode("utf-8"))
        server.quit()
        print(f"Email alert sent for {name}")

        alert_doc = {
            "product_name": name,
            "old_price": old_price,
            "new_price": price,
            "link": link,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # save alert to MongoDB
        alerts_collection.insert_one(alert_doc)

        # save alert to NEW ALERT CACHE
        new_alerts_cache.append(alert_doc)

    except Exception as e:
        print(f"[EMAIL ERROR] Could not send email: {e}")

# -----------------------
# SCRAPE FUNCTION
# -----------------------


def scrape_flipkart(category, pages=3):
    # soup = BeautifulSoup(html, 'html.parser')

    all_products = []


    for page in range(1, pages + 1):
            try:
                url = f"https://www.flipkart.com/search?q={category}&page={page}"
                print(f"\nScraping Page {page}: {url}")

                response = requests.get(url)
                soup = BeautifulSoup(response.text, "html.parser")

                # 1️⃣ Collect TAGS (not text)
                name_tags = []
                for selector in NAME_SELECTORS.get(category, []):
                    name_tags.extend(soup.select(selector))

                price_tags = []
                for selector in PRICE_SELECTORS.get(category, []):
                    price_tags.extend(soup.select(selector))

                # 2️⃣ Length check
                limit = min(len(name_tags), len(price_tags))

                for i in range(limit):
                    try:
                        # 3️⃣ Extract NAME from <a>
                        name = name_tags[i].get_text(strip=True)

                        # 4️⃣ Extract PRICE from <div>
                        price_raw = price_tags[i].get_text(strip=True)
                        price = int(price_raw.replace("₹", "").replace(",", ""))

                        # 5️⃣ Extract link (only <a> has href)
                        href = name_tags[i].get("href")
                        link = f"https://www.flipkart.com{href}" if href else ""
                        all_products.append([category, name, price, link])

                    except Exception as e:
                        print(f"[SKIP PRODUCT] {e}")
                        continue

            except Exception as e:
                print(f"[SKIP PAGE] Error scraping {category} page {page}: {e}")
                continue

    return all_products

def save_data(all_products):
    filename = "flipkart_prices.csv"
    old_data = {}

    # Load old price data
    try:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                old_data[row[1]] = int(row[2])
    except FileNotFoundError:
        pass

    # Remove duplicates by link
    unique = {}
    for cat, name, price, link in all_products:
        unique[name] = (cat, price, link)


    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "name", "price", "link"])

        mongo_docs = []  # will insert all at once

        for name, (cat, price, link) in unique.items():
            writer.writerow([cat, name, price, link])

            mongo_docs.append({
                "Category": cat,
                "name": name,
                "price": price,
                "link": link
            })

            # Check price drop and email
            drop_limit = 1
            if name in old_data:
                old_price = old_data[name]
                if price < old_price - drop_limit:
                    send_email_alert(name, old_price, price, link)

    # Save to MongoDB only if non-empty
    if mongo_docs:
        collection.delete_many({})   # wipe only once
        collection.insert_many(mongo_docs)
        print(f"Inserted {len(mongo_docs)} products to MongoDB")
    else:
        print("No products to save in MongoDB")

    print("CSV updated:", filename)
    return new_alerts_cache

def run_scraper():
    global new_alerts_cache
    new_alerts_cache = []  #reset each run
    all_products = []

    for cat_id, category in category_choice.items():
        print(f"\n=== Scraping category: {category} ===")
        data = scrape_flipkart(category)
        all_products.extend(data)

    save_data(all_products)
    return new_alerts_cache, all_products


# def main():
#     all_products = []

#     for cat_id, category in category_choice.items():
        
#         prod = scrape_flipkart(category)
#         all_products.extend(prod)

#     save_data(all_products)
#     return all_products   # <-- FIX (return results)

# if __name__ == "__main__":
#     run_scraper()  # your function that scrapes everything
       
        
