{% snapshot orders_snapshot %}
{{ config(target_schema=var('target_schema', 'test'), unique_key='order_id', strategy='check', check_cols=['customer','amount']) }}
select * from {{ ref('orders') }}
{% endsnapshot %}
