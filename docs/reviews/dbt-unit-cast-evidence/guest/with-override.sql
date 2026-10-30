with __dbt__cte__orders as (

-- Fixture for orders
select 
  
  
    cast(1 as signed)
  
 as order_id, 
  
  
    cast(10 as signed)
  
 as amount
union all
select 
  
  
    cast(2 as signed)
  
 as order_id, 
  
  
    cast(7 as signed)
  
 as amount
) select order_id, amount * 2 as doubled from __dbt__cte__orders