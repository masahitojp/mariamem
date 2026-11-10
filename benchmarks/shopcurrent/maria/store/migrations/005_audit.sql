CREATE TABLE audit_log(id BIGINT PRIMARY KEY AUTO_INCREMENT,order_id BIGINT NOT NULL,old_status ENUM('pending','paid','shipped','cancelled'),new_status ENUM('pending','paid','shipped','cancelled') NOT NULL,at TIMESTAMP NOT NULL DEFAULT now(),INDEX audit_log_order_id(order_id)) ENGINE=InnoDB
-- NEXT
CREATE TRIGGER orders_audit_insert AFTER INSERT ON orders FOR EACH ROW INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,NULL,NEW.status)
-- NEXT
CREATE TRIGGER orders_audit_update AFTER UPDATE ON orders FOR EACH ROW BEGIN IF NOT(NEW.status <=> OLD.status) THEN INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,OLD.status,NEW.status); END IF; END
