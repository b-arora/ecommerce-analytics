import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configure paths & styling
DB_PATH = "data/processed/olist.db"
FIG_PATH = "reports/figures"
os.makedirs(FIG_PATH, exist_ok=True)
os.makedirs("reports/tables", exist_ok=True)

sns.set_theme(style="whitegrid")
conn = sqlite3.connect(DB_PATH)

# --- 1. Monthly Revenue & Growth ---
print("Running Query 1: Monthly Trends...")
q_monthly = """
WITH monthly_metrics AS (
    SELECT 
        strftime('%Y-%m', order_purchase_timestamp) AS order_month,
        COUNT(DISTINCT order_id) AS total_orders,
        ROUND(SUM(gmv), 2) AS total_gmv,
        ROUND(AVG(gmv), 2) AS aov
    FROM mart_orders_operational
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp >= '2017-01-01' 
      AND order_purchase_timestamp < '2018-09-01'
    GROUP BY 1
)
SELECT 
    order_month,
    total_orders,
    total_gmv,
    aov,
    ROUND((total_gmv - LAG(total_gmv, 1) OVER (ORDER BY order_month)) 
          / LAG(total_gmv, 1) OVER (ORDER BY order_month) * 100, 2) AS mom_gmv_growth_pct
FROM monthly_metrics
ORDER BY order_month;
"""
df_monthly = pd.read_sql(q_monthly, conn)
print("\n--- Monthly Revenue Performance (First 6 Rows) ---")
print(df_monthly.head())

# Chart 1: GMV Trend
fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()

sns.barplot(data=df_monthly, x='order_month', y='total_gmv', ax=ax1, color='steelblue', alpha=0.7)
sns.lineplot(data=df_monthly, x='order_month', y='aov', ax=ax2, color='crimson', marker='o', linewidth=2)

ax1.set_title("Olist Monthly GMV (R$) vs. Average Order Value (AOV), in BRL", fontsize=14, fontweight='bold')
ax1.set_xlabel("Month")
ax1.set_ylabel("Total GMV (R$)", color='steelblue')
ax2.set_ylabel("AOV (R$)", color='crimson')
ax1.tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig(f"{FIG_PATH}/01_monthly_gmv_aov.png", dpi=300)
plt.close()

# --- 2. Top Categories ---
print("\nRunning Query 2: Category Performance...")
q_categories = """
SELECT 
    COALESCE(t.product_category_name_english, p.product_category_name, 'Unknown') AS category_name,
    COUNT(DISTINCT i.order_id) AS orders_count,
    ROUND(SUM(i.price), 2) AS total_sales,
    ROUND(AVG(r.review_score), 2) AS avg_review_score
FROM olist_order_items i
JOIN olist_orders o ON i.order_id = o.order_id
LEFT JOIN olist_products p ON i.product_id = p.product_id
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
LEFT JOIN (SELECT order_id, AVG(review_score) AS review_score FROM olist_order_reviews GROUP BY order_id) r ON i.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY total_sales DESC
LIMIT 10;
"""
df_cats = pd.read_sql(q_categories, conn)
print("\n--- Top 10 Product Categories by Revenue ---")
df_cats.to_csv("reports/tables/top_categories.csv", index=False)
df_monthly.to_csv("reports/tables/monthly_kpis.csv", index=False)
print(df_cats[['category_name', 'total_sales', 'avg_review_score']])

# Chart 2: Top Categories
plt.figure(figsize=(10, 5))
bar = sns.barplot(data=df_cats, x='total_sales', y='category_name', hue='category_name', palette='Blues_r', legend=False)
plt.title("Top 10 Product Categories by Total GMV (R$)", fontsize=13, fontweight='bold')
plt.xlabel("Total GMV (R$)")
plt.ylabel("Category")
plt.tight_layout()
plt.savefig(f"{FIG_PATH}/02_top_categories_gmv.png", dpi=300)
plt.close()

conn.close()
print(f"\n[DONE] Figures generated in {FIG_PATH}/")