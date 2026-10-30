import os as _os
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))
import sqlite3
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

DB_PATH = "data/processed/olist.db"
conn = sqlite3.connect(DB_PATH)

print("=" * 70)
print("PHASE 5: STATISTICAL INFERENCE & HYPOTHESIS TESTING")
print("=" * 70)

# ----------------------------------------------------------------------
# TEST 1: Mann-Whitney U Test (Delivery SLA vs. Review Scores)
# ----------------------------------------------------------------------
print("\n[TEST 1] Review Score Distribution: On-Time vs. Late Deliveries")
q_sla = """
SELECT is_late, avg_review_score 
FROM mart_orders_operational 
WHERE order_status = 'delivered' AND avg_review_score IS NOT NULL;
"""
df_sla = pd.read_sql(q_sla, conn)

on_time_scores = df_sla[df_sla['is_late'] == 0]['avg_review_score']
late_scores = df_sla[df_sla['is_late'] == 1]['avg_review_score']

u_stat, p_val_sla = stats.mannwhitneyu(on_time_scores, late_scores, alternative='two-sided')

# Rank-biserial correlation effect size: r = 1 - (2*U) / (n1*n2)
n1, n2 = len(on_time_scores), len(late_scores)
r_effect = (2 * u_stat) / (n1 * n2) - 1  # positive => on-time orders rate higher

print(f"Sample Size (On-Time): {n1:,} | Sample Size (Late): {n2:,}")
print(f"Median Rating (On-Time): {on_time_scores.median()} | Median Rating (Late): {late_scores.median()}")
print(f"Mann-Whitney U Statistic: {u_stat:,.1f}")
print(f"P-Value: {p_val_sla:.4e}")
print(f"Rank-Biserial Correlation (Effect Size): {r_effect:.4f}")
if p_val_sla < 0.05:
    print("CONCLUSION: Reject Null Hypothesis (H0). Late deliveries are associated with significantly lower ratings (observational data: association, not proven causation).")

# ----------------------------------------------------------------------
# TEST 2: One-Way ANOVA & Tukey HSD (Regional Freight Burden)
# ----------------------------------------------------------------------
print("\n" + "-" * 70)
print("[TEST 2] Regional Freight Cost Differences Across Macro-Regions")

# Mapping Brazilian states to official geographic regions
state_to_region = {
    'SP': 'Southeast', 'RJ': 'Southeast', 'MG': 'Southeast', 'ES': 'Southeast',
    'RS': 'South', 'SC': 'South', 'PR': 'South',
    'BA': 'Northeast', 'PE': 'Northeast', 'CE': 'Northeast', 'MA': 'Northeast', 
    'PB': 'Northeast', 'RN': 'Northeast', 'AL': 'Northeast', 'SE': 'Northeast', 'PI': 'Northeast',
    'MT': 'Central-West', 'MS': 'Central-West', 'GO': 'Central-West', 'DF': 'Central-West',
    'AM': 'North', 'PA': 'North', 'RO': 'North', 'TO': 'North', 'AC': 'North', 'AP': 'North', 'RR': 'North'
}

q_freight = """
SELECT customer_state, total_freight 
FROM mart_orders_operational 
WHERE order_status = 'delivered' AND total_freight > 0;
"""
df_freight = pd.read_sql(q_freight, conn)
df_freight['region'] = df_freight['customer_state'].map(state_to_region)
df_freight = df_freight.dropna(subset=['region'])

region_groups = [group['total_freight'].values for _, group in df_freight.groupby('region')]
f_stat, p_val_anova = stats.f_oneway(*region_groups)

print(f"One-Way ANOVA F-Statistic: {f_stat:,.2f}")
print(f"P-Value: {p_val_anova:.4e}")

if p_val_anova < 0.05:
    print("ANOVA Result: Significant differences exist across regions. Performing Tukey HSD Post-Hoc Test...")
    tukey = pairwise_tukeyhsd(endog=df_freight['total_freight'], groups=df_freight['region'], alpha=0.05)
    print("\nTukey HSD Summary:")
    print(tukey.summary())

# ----------------------------------------------------------------------
# TEST 3: Spearman Rank Correlation (Installments vs. Order Value)
# ----------------------------------------------------------------------
print("\n" + "-" * 70)
print("[TEST 3] Credit Card Installments vs. Basket Size (GMV)")
q_inst = """
SELECT max_installments, gmv 
FROM mart_orders_operational 
WHERE order_status = 'delivered' 
  AND payment_methods LIKE '%credit_card%'
  AND max_installments > 0;
"""
df_inst = pd.read_sql(q_inst, conn)

spearman_corr, p_val_spearman = stats.spearmanr(df_inst['max_installments'], df_inst['gmv'])

print(f"Observations (Credit Card Orders): {len(df_inst):,}")
print(f"Spearman Rank Correlation Coefficient: {spearman_corr:.4f}")
print(f"P-Value: {p_val_spearman:.4e}")

if p_val_spearman < 0.05:
    print(f"CONCLUSION: Statistically significant positive monotonic correlation (rho = {spearman_corr:.2f}).")
    print("Business Implication: Larger baskets are paid over more installments; interest-free installment offers are a lever worth A/B testing on high-ticket categories.")

print("=" * 70)
conn.close()