from flask import Flask, render_template, jsonify, request, redirect
from scraper import run_scraper, new_alerts_cache
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["flipkart"]
collection = db["products"]
alerts_collection = db["email_alert"]

# Home page – show all products from MongoDB
@app.route("/", methods=["GET"])
def index():
    search_query = request.args.get("search", "")

    if search_query:
        products = list(collection.find({"name": {"$regex": search_query, "$options": "i"}}))
    else:
        products = list(collection.find())

    total_records = collection.count_documents({})

    # show only NEW alerts generated during last run
    new_alerts = new_alerts_cache

    return render_template(
        "index.html",
        products=products,
        total_records=total_records,
        search_query=search_query,
        new_alerts=new_alerts
    )

# Run Scraper 
@app.route("/scrape", methods=["POST"])
def run_scraping():
    run_scraper()
    return redirect("/")

@app.route("/alert")
def alert_page():
    today = datetime.now().strftime("%Y-%m-%d")

    alerts = list(alerts_collection.find(
        {"time": {"$regex": today}}
    ))

    return render_template("alert.html", alerts=alerts)

if __name__ == "__main__":
    app.run(debug=True)
