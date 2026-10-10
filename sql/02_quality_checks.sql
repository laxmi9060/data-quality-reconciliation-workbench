-- These queries expect the orders and payments tables to contain the CSV data.

-- 1. Find duplicate transaction IDs in either source.
SELECT 'orders' AS source, transaction_id, COUNT(*) AS row_count
FROM orders
WHERE NULLIF(TRIM(transaction_id), '') IS NOT NULL
GROUP BY transaction_id
HAVING COUNT(*) > 1
UNION ALL
SELECT 'payments' AS source, transaction_id, COUNT(*) AS row_count
FROM payments
WHERE NULLIF(TRIM(transaction_id), '') IS NOT NULL
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY source, transaction_id;

-- 2. Find orders that do not have a matching payment.
SELECT o.transaction_id, o.customer_id, o.amount, o.currency
FROM orders AS o
WHERE NOT EXISTS (
    SELECT 1
    FROM payments AS p
    WHERE p.transaction_id = o.transaction_id
);

-- 3. Find payments that do not have a matching order.
SELECT p.transaction_id, p.customer_id, p.amount, p.currency
FROM payments AS p
WHERE NOT EXISTS (
    SELECT 1
    FROM orders AS o
    WHERE o.transaction_id = p.transaction_id
);

-- 4. Compare amounts only when the transaction ID occurs once in each source.
WITH unique_orders AS (
    SELECT transaction_id, MAX(amount) AS order_amount
    FROM orders
    GROUP BY transaction_id
    HAVING COUNT(*) = 1
),
unique_payments AS (
    SELECT transaction_id, MAX(amount) AS payment_amount
    FROM payments
    GROUP BY transaction_id
    HAVING COUNT(*) = 1
)
SELECT o.transaction_id,
       o.order_amount,
       p.payment_amount,
       o.order_amount - p.payment_amount AS difference
FROM unique_orders AS o
JOIN unique_payments AS p USING (transaction_id)
WHERE o.order_amount IS DISTINCT FROM p.payment_amount
  AND o.order_amount IS NOT NULL
  AND p.payment_amount IS NOT NULL
ORDER BY o.transaction_id;

-- 5. Find blank or missing required fields.
SELECT 'orders' AS source, transaction_id, 'transaction_id' AS missing_field
FROM orders WHERE NULLIF(TRIM(transaction_id), '') IS NULL
UNION ALL
SELECT 'orders', transaction_id, 'customer_id'
FROM orders WHERE NULLIF(TRIM(customer_id), '') IS NULL
UNION ALL
SELECT 'orders', transaction_id, 'amount'
FROM orders WHERE amount IS NULL
UNION ALL
SELECT 'orders', transaction_id, 'currency'
FROM orders WHERE NULLIF(TRIM(currency), '') IS NULL
UNION ALL
SELECT 'payments', transaction_id, 'transaction_id'
FROM payments WHERE NULLIF(TRIM(transaction_id), '') IS NULL
UNION ALL
SELECT 'payments', transaction_id, 'customer_id'
FROM payments WHERE NULLIF(TRIM(customer_id), '') IS NULL
UNION ALL
SELECT 'payments', transaction_id, 'amount'
FROM payments WHERE amount IS NULL
UNION ALL
SELECT 'payments', transaction_id, 'currency'
FROM payments WHERE NULLIF(TRIM(currency), '') IS NULL
ORDER BY source, transaction_id, missing_field;
