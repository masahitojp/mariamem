with __dbt__cte__orders as (

-- Fixture for orders
select 
    
    cast(1 as int(1))
 as order_id, 
    
    cast(10 as int(2))
 as amount
union all
select 
    
    cast(2 as int(1))
 as order_id, 
    
    cast(7 as int(2))
 as amount
) select order_id, amount * 2 as doubled from __dbt__cte__orders