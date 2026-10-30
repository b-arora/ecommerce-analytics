import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import sqlite3
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

DB_PATH = "data/processed/olist.db"
FIG_PATH = "reports/figures"
os.makedirs(FIG_PATH, exist_ok=True)
os.makedirs("reports/tables", exist_ok=True)

sns.set_theme(style="whitegrid")
conn = sqlite3.connect(DB_PATH)

print("=" * 70)
print("PHASE 6: CUSTOMER RETENTION, RFM & COHORT ANALYSIS")
print("=" * 70)

# ----------------------------------------------------------------------
# 1. One-Time vs. Repeat Customers
# ----------------------------------------------------------------------
q_cust_counts = """
WITH cust_orders AS (
    SELECT 
        customer_unique_id,
        COUNT(order_id) AS total_orders,
        SUM(gmv) AS total_spend
    FROM mart_orders_operational
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT 
    CASE WHEN total_orders = 1 THEN '1. One-Time Customer' ELSE '2. Repeat Customer' END AS customer_type,
    COUNT(customer_unique_id) AS total_customers,
    ROUND(COUNT(customer_unique_id) * 100.0 / (SELECT COUNT(DISTINCT customer_unique_id) FROM mart_orders_operational WHERE order_status = 'delivered'), 2) AS pct_customers,
    ROUND(SUM(total_spend), 2) AS total_revenue,
    ROUND(SUM(total_spend) * 100.0 / (SELECT SUM(gmv) FROM mart_orders_operational WHERE order_status = 'delivered'), 2) AS pct_revenue,
    ROUND(AVG(total_spend), 2) AS avg_spend_per_customer
FROM cust_orders
GROUP BY 1;
"""
df_cust_counts = pd.read_sql(q_cust_counts, conn)
print("\n--- 1. Customer Repeat Purchase Overview ---")
print(df_cust_counts.to_string(index=False))

# ----------------------------------------------------------------------
# 2. RFM Segmentation
# ----------------------------------------------------------------------
print("\n--- 2. Computing RFM Metrics ---")
q_rfm = """
SELECT 
    customer_unique_id,
    MAX(order_purchase_timestamp) AS last_purchase_date,
    COUNT(order_id) AS frequency,
    SUM(gmv) AS monetary
FROM mart_orders_operational
WHERE order_status = 'delivered'
GROUP BY customer_unique_id;
"""
df_rfm = pd.read_sql(q_rfm, conn)
df_rfm['last_purchase_date'] = pd.to_datetime(df_rfm['last_purchase_date'])

# Reference date: 1 day after the most recent order in the dataset
snapshot_date = df_rfm['last_purchase_date'].max() + pd.Timedelta(days=1)
df_rfm['recency'] = (snapshot_date - df_rfm['last_purchase_date']).dt.days

# Score Recency (higher score = more recent)
df_rfm['R_score'] = pd.qcut(df_rfm['recency'], q=5, labels=[5, 4, 3, 2, 1]).astype(int)

# Score Frequency: because ~97% of users have frequency=1, qcut fails; use explicit bins
df_rfm['F_score'] = np.where(df_rfm['frequency'] == 1, 1,
                             np.where(df_rfm['frequency'] == 2, 3, 5))

# Score Monetary (higher score = higher spend)
df_rfm['M_score'] = pd.qcut(df_rfm['monetary'], q=5, labels=[1, 2, 3, 4, 5]).astype(int)

# Create Composite RFM Segment
def assign_segment(row):
    r, f, m = row['R_score'], row['F_score'], row['M_score']
    if r >= 4 and f >= 3:
        return 'Champions & Loyal'
    elif r >= 3 and f == 1 and m >= 4:
        return 'Promising High-Spenders'
    elif r >= 3 and f == 1:
        return 'Recent One-Timers'
    elif r <= 2 and f >= 3:
        return 'At Risk (Former Repeat)'
    elif r <= 2 and m >= 4:
        return 'Hibernating Big Spenders'
    else:
        return 'Lost Low-Value'

df_rfm['segment'] = df_rfm.apply(assign_segment, axis=1)

df_seg_summary = df_rfm.groupby('segment').agg(
    total_customers=('customer_unique_id', 'count'),
    avg_recency=('recency', 'mean'),
    avg_frequency=('frequency', 'mean'),
    avg_monetary=('monetary', 'mean'),
    total_gmv=('monetary', 'sum')
).reset_index()

df_seg_summary['pct_customers'] = round(df_seg_summary['total_customers'] * 100 / len(df_rfm), 2)
df_seg_summary['pct_gmv'] = round(df_seg_summary['total_gmv'] * 100 / df_rfm['monetary'].sum(), 2)
df_seg_summary = df_seg_summary.sort_values(by='total_gmv', ascending=False)

df_seg_summary.to_csv("reports/tables/rfm_segments.csv", index=False)
print("\n--- RFM Segment Summary ---")
print(df_seg_summary[['segment', 'total_customers', 'pct_customers', 'pct_gmv', 'avg_monetary']].to_string(index=False))

# Chart: RFM Customer Share vs. Revenue Contribution
fig, ax = plt.subplots(figsize=(10, 5))
df_melt = df_seg_summary.melt(id_vars='segment', value_vars=['pct_customers', 'pct_gmv'], 
                              var_name='Metric', value_name='Percentage')
df_melt['Metric'] = df_melt['Metric'].map({'pct_customers': '% of Total Customers', 'pct_gmv': '% of Total GMV'})

sns.barplot(data=df_melt, x='Percentage', y='segment', hue='Metric', palette='Blues_r', ax=ax)
ax.set_title("RFM Customer Segments: Customer Count % vs. GMV Contribution %", fontsize=13, fontweight='bold')
ax.set_xlabel("Percentage (%)")
ax.set_ylabel("Segment")
plt.tight_layout()
plt.savefig(f"{FIG_PATH}/05_rfm_segments.png", dpi=300)
plt.close()

# ----------------------------------------------------------------------
# 3. Monthly Cohort Retention Matrix
# ----------------------------------------------------------------------
print("\n--- 3. Building Cohort Retention Matrix ---")
q_cohort = """
SELECT 
    customer_unique_id,
    order_id,
    strftime('%Y-%m', order_purchase_timestamp) AS order_month
FROM mart_orders_operational
WHERE order_status = 'delivered'
  AND order_purchase_timestamp >= '2017-01-01' 
  AND order_purchase_timestamp < '2018-09-01';
"""
df_orders = pd.read_sql(q_cohort, conn)
df_orders['order_month_dt'] = pd.to_datetime(df_orders['order_month'] + '-01')

# Determine cohort (first purchase month)
df_orders['cohort'] = df_orders.groupby('customer_unique_id')['order_month_dt'].transform('min')
df_orders['cohort_str'] = df_orders['cohort'].dt.strftime('%Y-%m')

# Calculate cohort index (months since first purchase)
year_diff = df_orders['order_month_dt'].dt.year - df_orders['cohort'].dt.year
month_diff = df_orders['order_month_dt'].dt.month - df_orders['cohort'].dt.month
df_orders['cohort_index'] = year_diff * 12 + month_diff

cohort_data = df_orders.groupby(['cohort_str', 'cohort_index'])['customer_unique_id'].nunique().reset_index()
cohort_pivot = cohort_data.pivot(index='cohort_str', columns='cohort_index', values='customer_unique_id')

cohort_sizes = cohort_pivot.iloc[:, 0]
retention_matrix = cohort_pivot.divide(cohort_sizes, axis=0) * 100

print("\nCohort Retention (First 5 Cohorts, Month 0 to Month 4 %):")
print(round(retention_matrix.iloc[:5, :5], 2).to_string())

# Chart: Retention Heatmap
plt.figure(figsize=(14, 8))
sns.heatmap(retention_matrix.iloc[:, 1:13], annot=True, fmt=".1f", cmap="YlGnBu", vmin=0, vmax=2.5, cbar_kws={'label': 'Retention Rate (%)'})
plt.title("Olist Monthly Cohort Retention Rates (Month 1 to Month 12)", fontsize=14, fontweight='bold')
plt.xlabel("Months After Acquisition")
plt.ylabel("Acquisition Cohort")
plt.tight_layout()
plt.savefig(f"{FIG_PATH}/06_cohort_retention_heatmap.png", dpi=300)
plt.close()

conn.close()
print(f"\n[DONE] Figures 05 and 06 generated in {FIG_PATH}/")