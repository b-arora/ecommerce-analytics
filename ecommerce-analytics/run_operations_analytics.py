import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import sqlite3
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DB_PATH = "data/processed/olist.db"
FIG_PATH = "reports/figures"
os.makedirs(FIG_PATH, exist_ok=True)
os.makedirs("reports/tables", exist_ok=True)

sns.set_theme(style="whitegrid")
conn = sqlite3.connect(DB_PATH)

# --- 1. Delay SLA Impact on Satisfaction ---
print("Running Operations Query 1: SLA Impact...")
q_sla = """
SELECT 
    CASE WHEN is_late = 1 THEN 'Late Delivery' ELSE 'On-Time Delivery' END AS sla_status,
    COUNT(order_id) AS total_orders,
    ROUND(COUNT(order_id) * 100.0 / (SELECT COUNT(*) FROM mart_orders_operational WHERE order_status = 'delivered'), 2) AS pct_orders,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    ROUND(SUM(CASE WHEN avg_review_score <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(order_id), 2) AS pct_bad_reviews
FROM mart_orders_operational
WHERE order_status = 'delivered'
GROUP BY is_late;
"""
df_sla = pd.read_sql(q_sla, conn)
print("\n--- SLA Status vs Customer Reviews ---")
print(df_sla.to_string(index=False))

# --- 2. Delivery Delay Buckets ---
print("\nRunning Operations Query 2: Delay Buckets...")
q_buckets = """
SELECT 
    CASE 
        WHEN delay_vs_estimate_days <= -7 THEN '1. >7d Early'
        WHEN delay_vs_estimate_days <= 0 THEN '2. 0-7d Early'
        WHEN delay_vs_estimate_days <= 3 THEN '3. 1-3d Late'
        WHEN delay_vs_estimate_days <= 7 THEN '4. 4-7d Late'
        ELSE '5. >7d Late'
    END AS delivery_bucket,
    COUNT(order_id) AS total_orders,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    ROUND(SUM(CASE WHEN avg_review_score = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(order_id), 2) AS pct_1_star
FROM mart_orders_operational
WHERE order_status = 'delivered' AND delay_vs_estimate_days IS NOT NULL
GROUP BY 1
ORDER BY delivery_bucket;
"""
df_buckets = pd.read_sql(q_buckets, conn)
print("\n--- Review Degradation Across Delay Buckets ---")
print(df_buckets.to_string(index=False))

# Chart: Review Score Drop-Off by Delay Bucket
fig, ax1 = plt.subplots(figsize=(9, 4.5))
sns.barplot(data=df_buckets, x='delivery_bucket', y='avg_review_score', color='royalblue', alpha=0.85, ax=ax1)
ax1.set_title("Customer Rating Degradation by Delivery Performance", fontsize=13, fontweight='bold')
ax1.set_xlabel("Delivery SLA Window")
ax1.set_ylabel("Average Review Score (1-5)", color='navy')
ax1.set_ylim(0, 5)

for p in ax1.patches:
    ax1.annotate(f"{p.get_height():.2f} ★", 
                 (p.get_x() + p.get_width() / 2., p.get_height() - 0.5), 
                 ha='center', va='center', color='white', fontweight='bold', fontsize=11)

plt.tight_layout()
plt.savefig(f"{FIG_PATH}/03_delivery_delay_vs_rating.png", dpi=300)
plt.close()

# --- 3. Top 10 States with Worst Delivery Delays ---
print("\nRunning Operations Query 3: State Inefficiencies...")
q_states = """
SELECT 
    customer_state,
    COUNT(order_id) AS total_orders,
    ROUND(AVG(delivery_lead_time_days), 1) AS avg_delivery_days,
    ROUND(SUM(is_late) * 100.0 / COUNT(order_id), 2) AS late_rate_pct,
    ROUND(AVG(total_freight), 2) AS avg_freight
FROM mart_orders_operational
WHERE order_status = 'delivered'
GROUP BY customer_state
HAVING total_orders >= 200
ORDER BY late_rate_pct DESC
LIMIT 10;
"""
df_states = pd.read_sql(q_states, conn)
df_states.to_csv("reports/tables/top_late_states.csv", index=False)
df_buckets.to_csv("reports/tables/delay_buckets.csv", index=False)
print("\n--- Top 10 States with Highest Late Delivery Rate ---")
print(df_states.to_string(index=False))

# Chart: Top 10 Late Delivery States
plt.figure(figsize=(10, 4.5))
sns.barplot(data=df_states, x='late_rate_pct', y='customer_state', hue='customer_state', palette='Reds_r', legend=False)
plt.title("Top 10 Brazilian States by Late Delivery Rate (%)", fontsize=13, fontweight='bold')
plt.xlabel("Late Delivery Rate (%)")
plt.ylabel("Customer State")
plt.tight_layout()
plt.savefig(f"{FIG_PATH}/04_top_late_states.png", dpi=300)
plt.close()

conn.close()
print(f"\n[DONE] Figures generated in {FIG_PATH}/")