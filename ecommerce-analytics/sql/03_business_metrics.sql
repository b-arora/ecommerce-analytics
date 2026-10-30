-- 1. Monthly Revenue, Order Volume, MoM Growth %, and Average Order Value (AOV)
WITH monthly_metrics AS (
    SELECT 
        strftime('%Y-%m', order_purchase_timestamp) AS order_month,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_unique_id) AS unique_buyers,
        ROUND(SUM(gmv), 2) AS total_gmv,
        ROUND(SUM(total_freight), 2) AS total_freight,
        ROUND(AVG(gmv), 2) AS aov
    FROM mart_orders_operational
    WHERE order_status = 'delivered'
      AND order_purchase_timestamp >= '2017-01-01' 
      AND order_purchase_timestamp < '2018-09-01' -- Exclude partial ramp-up & incomplete 2018 months
    GROUP BY strftime('%Y-%m', order_purchase_timestamp)
)
SELECT 
    order_month,
    total_orders,
    unique_buyers,
    total_gmv,
    total_freight,
    aov,
    ROUND(
        (total_gmv - LAG(total_gmv, 1) OVER (ORDER BY order_month)) 
        / LAG(total_gmv, 1) OVER (ORDER BY order_month) * 100, 
        2
    ) AS mom_gmv_growth_pct
FROM monthly_metrics
ORDER BY order_month;

-- NOTE: reviews are pre-aggregated per order to avoid revenue fan-out
-- (some orders have >1 review, which would double-count item prices).
-- 2. Top 10 Product Categories by GMV & Their Quality Footprint
SELECT 
    COALESCE(t.product_category_name_english, p.product_category_name, 'Unknown') AS category_name,
    COUNT(DISTINCT i.order_id) AS orders_count,
    COUNT(i.order_item_id) AS units_sold,
    ROUND(SUM(i.price), 2) AS total_sales,
    ROUND(AVG(i.price), 2) AS avg_unit_price,
    ROUND(AVG(r.review_score), 2) AS avg_category_review
FROM olist_order_items i
JOIN olist_orders o ON i.order_id = o.order_id
LEFT JOIN olist_products p ON i.product_id = p.product_id
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
LEFT JOIN (SELECT order_id, AVG(review_score) AS review_score FROM olist_order_reviews GROUP BY order_id) r ON i.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY total_sales DESC
LIMIT 10;

-- 3. Top 10 High-Volume Sellers & Dispatch Performance
SELECT 
    s.seller_id,
    s.seller_state,
    COUNT(DISTINCT i.order_id) AS total_orders_fulfilled,
    ROUND(SUM(i.price), 2) AS total_revenue,
    ROUND(AVG(julianday(o.order_delivered_carrier_date) - julianday(o.order_purchase_timestamp)), 2) AS avg_dispatch_days,
    ROUND(AVG(r.review_score), 2) AS avg_seller_review
FROM olist_order_items i
JOIN olist_orders o ON i.order_id = o.order_id
JOIN olist_sellers s ON i.seller_id = s.seller_id
LEFT JOIN (SELECT order_id, AVG(review_score) AS review_score FROM olist_order_reviews GROUP BY order_id) r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY s.seller_id, s.seller_state
HAVING total_orders_fulfilled >= 100
ORDER BY total_revenue DESC
LIMIT 10;