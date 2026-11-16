CREATE TABLE audit_log (
    id bigserial PRIMARY KEY,
    order_id bigint NOT NULL,
    old_status order_status,
    new_status order_status NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_order_id ON audit_log(order_id);

CREATE FUNCTION log_order_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO audit_log(order_id, old_status, new_status)
        VALUES (NEW.id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status);
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER orders_audit
    AFTER INSERT OR UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION log_order_status();
