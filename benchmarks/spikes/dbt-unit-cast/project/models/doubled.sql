select order_id, amount * 2 as doubled from {{ ref('orders') }}
