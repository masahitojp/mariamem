CREATE TYPE order_status AS ENUM ('pending', 'paid', 'shipped', 'cancelled');

CREATE TABLE orders (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status order_status NOT NULL DEFAULT 'pending',
    total_cents bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX orders_user_id ON orders(user_id);
CREATE INDEX orders_status ON orders(status);

CREATE TABLE order_items (
    id bigserial PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id bigint NOT NULL REFERENCES products(id),
    quantity int NOT NULL CHECK (quantity > 0),
    unit_price_cents bigint NOT NULL
);

CREATE INDEX order_items_order_id ON order_items(order_id);
CREATE INDEX order_items_product_id ON order_items(product_id);
