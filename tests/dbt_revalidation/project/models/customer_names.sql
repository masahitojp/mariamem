select distinct customer from {{ ref('orders') }}
