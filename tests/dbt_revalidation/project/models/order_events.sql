{{ config(materialized='incremental', unique_key='order_id') }}
select order_id, customer, amount
from {{ ref('orders') }}
{% if is_incremental() %}
where order_id > (select coalesce(max(order_id), 0) from {{ this }})
{% endif %}
