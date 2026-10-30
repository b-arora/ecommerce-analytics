-- 1. Overall Delivery SLA Benchmark & Review Impact
SELECT 
    is_late,
    COUNT(order_id) AS total_orders,
    ROUND(COUNT(order_id) * 100.0 / (SELECT COUNT(*) FROM mart_orders_operational WHERE order_status = 'delivered'), 2) AS pct_of_total_orders,
    ROUND(AVG(delivery_lead_time_days), 1) AS avg_delivery_days,
    ROUND(AVG(dispatch_lead_time_days), 1) AS avg_dispatch_days,
    ROUND(AVG(avg_review_score), 2) AS avg_customer_rating,
    ROUND(SUM(CASE WHEN avg_review_score <= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(order_id), 2) AS pct_bad_reviews
FROM mart_orders_operational
WHERE order_status = 'delivered'
GROUP BY is_late;

-- 2. State-Level Regional Delivery & Freight Inefficiency
SELECT 
    customer_state,
    COUNT(order_id) AS total_orders,
    ROUND(AVG(delivery_lead_time_days), 1) AS avg_delivery_days,
    ROUND(AVG(delay_vs_estimate_days), 1) AS avg_delay_vs_estimate_days,
    ROUND(SUM(is_late) * 100.0 / COUNT(order_id), 2) AS late_delivery_rate_pct,
    ROUND(AVG(total_freight), 2) AS avg_freight_cost,
    ROUND(AVG(total_freight / NULLIF(gmv + total_freight, 0)) * 100, 2) AS freight_burden_pct,
    ROUND(AVG(avg_review_score), 2) AS avg_state_review
FROM mart_orders_operational
WHERE order_status = 'delivered'
GROUP BY customer_state
HAVING total_orders >= 100
ORDER BY late_delivery_rate_pct DESC;

-- 3. Review Score Breakdown by Exact Delivery Delay Buckets
SELECT 
    CASE 
        WHEN delay_vs_estimate_days <= -7 THEN 'A. >1 Week Early'
        WHEN delay_vs_estimate_days <= 0 THEN 'B. 0-7 Days Early (On-Time)'
        WHEN delay_vs_estimate_days <= 3 THEN 'C. 1-3 Days Late'
        WHEN delay_vs_estimate_days <= 7 THEN 'D. 4-7 Days Late'
        ELSE 'E. >1 Week Late'
    END AS delivery_performance_bucket,
    COUNT(order_id) AS total_orders,
    ROUND(AVG(avg_review_score), 2) AS avg_review_score,
    ROUND(SUM(CASE WHEN avg_review_score = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(order_id), 2) AS pct_1_star_reviews
FROM mart_orders_operational
WHERE order_status = 'delivered'
  AND delay_vs_estimate_days IS NOT NULL
GROUP BY 1
ORDER BY delivery_performance_bucket;