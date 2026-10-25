
CREATE TYPE account_type_enum AS ENUM (
    'Savings',
    'Current'
);
ALTER TABLE account
ADD COLUMN account_type account_type_enum NOT NULL DEFAULT 'Savings';