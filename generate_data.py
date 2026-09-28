"""
Day 2 - Generate synthetic order data with realistic defects baked in.

112 clean orders + 14 deliberately dirty rows (seeded, so the same data
comes out every run). The defect mix mirrors what real source systems
produce: missing values, duplicates, out-of-range numbers, malformed
emails, bad categories, future timestamps, invalid country codes.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)  # fixed seed = reproducible data

CATEGORIES = ["electronics", "clothing", "books", "home", "sports"]
COUNTRIES = ["US", "CA", "UK", "IN", "AU", "DE"]

rows = []

# ---- 112 clean orders ----
base = datetime(2026, 8, 1)
for i in range(1, 113):
    order_id = f"ORD-{i:04d}"
    email = f"cust_{random.randint(1, 40)}@example.com"
    category = random.choice(CATEGORIES)
    price = round(random.uniform(5, 2000), 2)
    quantity = random.randint(1, 20)
    order_date = (base + timedelta(days=random.randint(0, 55))).strftime("%Y-%m-%d")
    country = random.choice(COUNTRIES)
    rows.append([order_id, email, category, price, quantity, order_date, country])

# ---- 14 dirty rows (the ones our checks must catch) ----
dirty = [
    # duplicate order_ids
    ["ORD-0007", "cust_3@example.com", "books", 49.99, 2, "2026-09-10", "US"],
    ["ORD-0033", "cust_9@example.com", "sports", 89.50, 1, "2026-09-11", "UK"],
    # missing identifiers
    ["", "cust_9@example.com", "home", 19.99, 1, "2026-09-12", "US"],          # blank order_id
    ["ORD-0116", "", "electronics", 299.00, 1, "2026-09-12", "CA"],             # blank email
    ["ORD-0117", "not-an-email", "clothing", 59.99, 3, "2026-09-13", "US"],     # malformed email
    ["ORD-0118", "cust_5example.com", "books", 12.99, 1, "2026-09-13", "IN"],   # malformed email
    # bad numbers
    ["ORD-0119", "cust_7@example.com", "home", -49.99, 2, "2026-09-14", "US"],  # negative price
    ["ORD-0120", "cust_8@example.com", "sports", 75.00, -2, "2026-09-14", "AU"],# negative qty
    ["ORD-0121", "cust_2@example.com", "electronics", 899.00, 0, "2026-09-15", "DE"],  # zero qty
    ["ORD-0122", "cust_4@example.com", "clothing", 2500000.00, 1, "2026-09-15", "US"], # absurd price
    # bad categories / codes
    ["ORD-0123", "cust_6@example.com", "hoverboards", 199.99, 1, "2026-09-16", "US"],   # bad category
    ["ORD-0124", "cust_1@example.com", "", 39.99, 2, "2026-09-16", "CA"],              # blank category
    ["ORD-0125", "cust_3@example.com", "books", 24.99, 1, "2027-01-15", "UK"],         # future date
    ["ORD-0126", "cust_9@example.com", "home", 149.00, 1, "2026-09-17", "XX"],        # bad country
]
rows.extend(dirty)

with open("orders.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["order_id", "customer_email", "product_category",
                     "price", "quantity", "order_date", "country"])
    writer.writerows(rows)

print(f"orders.csv created: {len(rows)} rows (112 clean + 14 dirty)")
