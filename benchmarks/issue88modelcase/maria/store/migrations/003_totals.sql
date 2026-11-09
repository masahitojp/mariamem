CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=COALESCE((SELECT sum(quantity*unit_price_cents) FROM order_items WHERE order_id=NEW.order_id),0),updated_at=now() WHERE id=NEW.order_id
-- NEXT
CREATE TRIGGER order_items_total_update AFTER UPDATE ON order_items FOR EACH ROW UPDATE orders SET total_cents=COALESCE((SELECT sum(quantity*unit_price_cents) FROM order_items WHERE order_id=NEW.order_id),0),updated_at=now() WHERE id=NEW.order_id
-- NEXT
CREATE TRIGGER order_items_total_delete AFTER DELETE ON order_items FOR EACH ROW UPDATE orders SET total_cents=COALESCE((SELECT sum(quantity*unit_price_cents) FROM order_items WHERE order_id=OLD.order_id),0),updated_at=now() WHERE id=OLD.order_id
