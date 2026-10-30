import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import sqlite3
import pandas as pd

DB_PATH = "data/processed/olist.db"
SQL_PATH = "sql/02_analytical_base_table.sql"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Building mart_orders_operational in SQLite...")
with open(SQL_PATH, "r") as f:
    sql_script = f.read()

cursor.executescript(sql_script)
conn.commit()
print("Table created successfully.")

# Check 1: 1-to-1 Grain Match
total_orders = pd.read_sql("SELECT COUNT(*) AS count FROM olist_orders;", conn).iloc[0]["count"]
mart_rows = pd.read_sql("SELECT COUNT(*) AS count FROM mart_orders_operational;", conn).iloc[0]["count"]

print("\n--- Integrity Check 1: Grain Validation ---")
print(f"Original Orders Count: {total_orders:,}")
print(f"Mart Orders Count:     {mart_rows:,}")
assert total_orders == mart_rows, "[FAIL] Row count mismatch! Grain has expanded or contracted."
print("[PASS] Grain is verified at exactly 1 row per order.")

# Check 2: Financial Non-Duplication (Fan-Out Test)
raw_item_gmv = pd.read_sql("SELECT ROUND(SUM(price), 2) AS gmv FROM olist_order_items;", conn).iloc[0]["gmv"]
mart_gmv = pd.read_sql("SELECT ROUND(SUM(gmv), 2) AS gmv FROM mart_orders_operational;", conn).iloc[0]["gmv"]

print("\n--- Integrity Check 2: Fan-Out & Revenue Duplication ---")
print(f"Sum of Item Line Prices (Raw): R${raw_item_gmv:,.2f}")
print(f"Sum of Mart GMV:               ${mart_gmv:,.2f}")
assert abs(raw_item_gmv - mart_gmv) < 1.0, "[FAIL] Revenue fan-out detected! Values do not match."
print("[PASS] Zero revenue duplication detected.")

# Sample Inspection
print("\n--- Sample Output Preview ---")
sample_df = pd.read_sql("""
    SELECT 
        order_id, 
        customer_state, 
        gmv, 
        total_freight, 
        delivery_lead_time_days, 
        is_late, 
        avg_review_score 
    FROM mart_orders_operational 
    WHERE order_status = 'delivered'
    LIMIT 5;
""", conn)
print(sample_df.to_string(index=False))

conn.close()