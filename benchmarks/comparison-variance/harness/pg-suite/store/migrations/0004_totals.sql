-- orders.total_cents is maintained by a trigger, the way many applications
-- keep a denormalized sum in step with its detail rows.
CREATE FUNCTION refresh_order_total() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    oid bigint := COALESCE(NEW.order_id, OLD.order_id);
BEGIN
    UPDATE orders
       SET total_cents = COALESCE((SELECT sum(quantity * unit_price_cents) FROM order_items WHERE order_id = oid), 0),
           updated_at = now()
     WHERE id = oid;
    RETURN NULL;
END
$$;

CREATE TRIGGER order_items_total
    AFTER INSERT OR UPDATE OR DELETE ON order_items
    FOR EACH ROW EXECUTE FUNCTION refresh_order_total();

CREATE VIEW user_order_totals AS
    SELECT u.id AS user_id,
           u.name,
           count(o.id) AS orders,
           COALESCE(sum(o.total_cents), 0) AS total_cents
      FROM users u
      LEFT JOIN orders o ON o.user_id = u.id AND o.status <> 'cancelled'
     GROUP BY u.id;
