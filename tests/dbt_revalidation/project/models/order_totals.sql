{{ config(materialized='view') }}
select customer, sum(amount) as total
from {{ ref('orders') }}
group by customer
