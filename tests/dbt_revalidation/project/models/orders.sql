select
  order_id,
  customer,
  amount,
  amount * 2 as doubled
from {{ ref('orders_seed') }}
