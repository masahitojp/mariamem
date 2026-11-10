CREATE TABLE categories (
    id serial PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE products (
    id bigserial PRIMARY KEY,
    category_id int NOT NULL REFERENCES categories(id),
    sku text NOT NULL UNIQUE,
    name text NOT NULL,
    price_cents bigint NOT NULL CHECK (price_cents >= 0),
    stock int NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE INDEX products_category_id ON products(category_id);
CREATE INDEX products_name_lower ON products(lower(name) text_pattern_ops);
