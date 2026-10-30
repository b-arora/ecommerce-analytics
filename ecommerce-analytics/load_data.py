import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import os
import sqlite3
import pandas as pd

# Define paths
RAW_DATA_PATH = os.path.join("data", "raw")
DB_PATH = os.path.join("data", "processed", "olist.db")

# Ensure processed directory exists
os.makedirs(os.path.join("data", "processed"), exist_ok=True)

# Define dataset files and their timestamp columns for proper parsing
DATASETS = {
    "olist_customers": ("olist_customers_dataset.csv", []),
    "olist_sellers": ("olist_sellers_dataset.csv", []),
    "olist_products": ("olist_products_dataset.csv", []),
    "olist_order_items": ("olist_order_items_dataset.csv", ["shipping_limit_date"]),
    "olist_order_payments": ("olist_order_payments_dataset.csv", []),
    "olist_order_reviews": ("olist_order_reviews_dataset.csv", [
        "review_creation_date", 
        "review_answer_timestamp"
    ]),
    "olist_orders": ("olist_orders_dataset.csv", [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]),
    "product_category_name_translation": ("product_category_name_translation.csv", []),
    # Geolocation has ~1M rows; load it directly
    "olist_geolocation": ("olist_geolocation_dataset.csv", [])
}

def ingest_data():
    conn = sqlite3.connect(DB_PATH)
    print(f"Connected to database at {DB_PATH}")

    for table_name, (file_name, date_cols) in DATASETS.items():
        file_path = os.path.join(RAW_DATA_PATH, file_name)
        
        if not os.path.exists(file_path):
            print(f"[WARNING] Missing file: {file_path}. Skipping...")
            continue
            
        print(f"Loading {file_name} into table '{table_name}'...")
        
        # Load CSV with date parsing where appropriate
        df = pd.read_csv(file_path, parse_dates=date_cols if date_cols else False)
        
        # Write to SQLite
        df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)
        print(f"Loaded '{table_name}' successfully ({len(df):,} rows).")

    # Create helpful indexes for fast SQL joins
    cursor = conn.cursor()
    print("\nCreating indexes for query optimization...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON olist_orders (order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_cust_id ON olist_orders (customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_order_id ON olist_order_items (order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_seller_id ON olist_order_items (seller_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_product_id ON olist_order_items (product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON olist_order_payments (order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_order_id ON olist_order_reviews (order_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_cust_id ON olist_customers (customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_unique_id ON olist_customers (customer_unique_id);")
    conn.commit()
    conn.close()
    print("Database build complete and indexed.")

if __name__ == "__main__":
    ingest_data()