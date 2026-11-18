
from pymongo import MongoClient, ASCENDING
import pandas as pd
import random


# ==================================================
# 1. MONGODB FROM PYTHON
# ==================================================

client = MongoClient("mongodb://localhost:27017")
orders = client.shop.orders

# Insert one document
orders.insert_one({
    "_id": 1004,
    "customer": {
        "name": "Hung",
        "city": "Hue"
    },
    "status": "paid",
    "items": []
})

# Find paid orders
print("\nPaid orders:")

for doc in orders.find(
    {"status": "paid"},
    {"customer.name": 1, "status": 1}
):
    print(doc)

# Aggregation using Pandas
pipeline = [
    {"$unwind": "$items"},
    {
        "$group": {
            "_id": "$items.sku",
            "units": {"$sum": "$items.qty"}
        }
    }
]

df = pd.DataFrame(list(orders.aggregate(pipeline)))

print("\nAggregation result:")
print(df)


# ==================================================
# EXERCISE 1
# Insert five orders with different shapes,
# then find all orders containing a given SKU.
# ==================================================

def exercise_1():
    exercise_orders = [
        {
            "_id": 2001,
            "customer": {"name": "Minh", "city": "Hanoi"},
            "status": "paid",
            "items": [
                {"sku": "BK-10", "qty": 2, "price": 15}
            ]
        },
        {
            "_id": 2002,
            "customer": {"name": "Lan", "city": "Hue"},
            "status": "shipped",
            "items": [
                {"sku": "BK-11", "qty": 1, "price": 20}
            ],
            "coupon": "SALE10"
        },
        {
            "_id": 2003,
            "customer": {"name": "Tuan", "city": "Da Nang"},
            "status": "paid",
            "items": [
                {"sku": "BK-10", "qty": 1, "price": 15},
                {"sku": "BK-12", "qty": 3, "price": 10}
            ]
        },
        {
            "_id": 2004,
            "customer": {"name": "Hoa", "city": "Hanoi"},
            "status": "pending",
            "items": [],
            "tags": ["new-customer"]
        },
        {
            "_id": 2005,
            "customer": {"name": "Phuc", "city": "HCMC"},
            "status": "paid",
            "items": [
                {"sku": "BK-13", "qty": 2, "price": 25}
            ]
        }
    ]

    collection = client.shop.exercise_orders
    collection.delete_many({})
    collection.insert_many(exercise_orders)

    print("\nExercise 1: Orders containing BK-10")

    for doc in collection.find({"items.sku": "BK-10"}):
        print(doc)


# ==================================================
# EXERCISE 2
# Write an aggregation that returns revenue per city.
# ==================================================

def exercise_2():
    pipeline = [
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$customer.city",
                "revenue": {
                    "$sum": {
                        "$multiply": [
                            "$items.qty",
                            "$items.price"
                        ]
                    }
                }
            }
        },
        {"$sort": {"revenue": -1}}
    ]

    print("\nExercise 2: Revenue per city")

    for doc in orders.aggregate(pipeline):
        print(doc)


# ==================================================
# EXERCISE 3
# Create an index and compare explain()
# before and after on 10,000 generated documents.
# ==================================================

def exercise_3():
    collection = client.shop.test_orders

    collection.delete_many({})

    cities = ["Hanoi", "Hue", "Da Nang", "HCMC"]
    statuses = ["paid", "shipped", "pending"]

    documents = []

    for i in range(10000):
        documents.append({
            "order_id": i,
            "customer": {
                "name": f"Customer_{i}",
                "city": random.choice(cities)
            },
            "status": random.choice(statuses),
            "amount": random.randint(10, 500)
        })

    collection.insert_many(documents)

    query = {
        "customer.city": "Hanoi",
        "status": "paid"
    }

    # Explain before index
    before = collection.find(query).explain()

    print("\nExercise 3: Before index")
    print(before["queryPlanner"]["winningPlan"])
    print("Execution statistics:")
    print(before["executionStats"])

    # Create index
    collection.create_index([
        ("customer.city", ASCENDING),
        ("status", ASCENDING)
    ])

    # Explain after index
    after = collection.find(query).explain()

    print("\nExercise 3: After index")
    print(after["queryPlanner"]["winningPlan"])
    print("Execution statistics:")
    print(after["executionStats"])


# ==================================================
# RUN ALL EXERCISES
# ==================================================

if __name__ == "__main__":
    exercise_1()
    exercise_2()
    exercise_3()

    print("\nAll exercises completed!")

    client.close()
