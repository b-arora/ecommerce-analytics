-- Drop table if already exists
DROP TABLE IF EXISTS mart_orders_operational;

-- Create Analytical Base Table at Order Grain
CREATE TABLE mart_orders_operational AS
WITH items_agg AS (
    SELECT 
        order_id,
        COUNT(order_item_id) AS total_items,
        COUNT(DISTINCT seller_id) AS unique_sellers_count,
        SUM(price) AS gross_merchandise_value,
        SUM(freight_value) AS total_freight
    FROM olist_order_items
    GROUP BY order_id
),
payments_agg AS (
    SELECT 
        order_id,
        SUM(payment_value) AS total_payment_value,
        MAX(payment_installments) AS max_installments,
        GROUP_CONCAT(DISTINCT payment_type) AS payment_methods
    FROM olist_order_payments
    GROUP BY order_id
),
reviews_agg AS (
    SELECT 
        order_id,
        AVG(review_score) AS avg_review_score,
        COUNT(review_id) AS review_count
    FROM olist_order_reviews
    GROUP BY order_id
)
SELECT 
    o.order_id,
    c.customer_id,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    COALESCE(i.total_items, 0) AS total_items,
    COALESCE(i.unique_sellers_count, 0) AS unique_sellers_count,
    COALESCE(i.gross_merchandise_value, 0.0) AS gmv,
    COALESCE(i.total_freight, 0.0) AS total_freight,
    COALESCE(p.total_payment_value, 0.0) AS total_payment_value,
    COALESCE(p.max_installments, 1) AS max_installments,
    p.payment_methods,
    r.avg_review_score,
    COALESCE(r.review_count, 0) AS review_count,
    
    -- Operational Lead Times (using julianday in SQLite)
    ROUND(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp), 2) AS delivery_lead_time_days,
    ROUND(julianday(o.order_delivered_customer_date) - julianday(o.order_estimated_delivery_date), 2) AS delay_vs_estimate_days,
    ROUND(julianday(o.order_delivered_carrier_date) - julianday(o.order_purchase_timestamp), 2) AS dispatch_lead_time_days,
    
    -- Binary Delivery SLA Flag
    CASE 
        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 
        ELSE 0 
    END AS is_late
FROM olist_orders o
JOIN olist_customers c ON o.customer_id = c.customer_id
LEFT JOIN items_agg i ON o.order_id = i.order_id
LEFT JOIN payments_agg p ON o.order_id = p.order_id
LEFT JOIN reviews_agg r ON o.order_id = r.order_id;