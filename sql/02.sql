CREATE TABLE account (
    account_no BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    customer_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,

    balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00
        CHECK (balance >= 0),

    opened_on DATE NOT NULL DEFAULT CURRENT_DATE,

    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'frozen', 'closed')),

    CONSTRAINT fk_account_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer(id),

    CONSTRAINT fk_account_branch
        FOREIGN KEY (branch_id)
        REFERENCES branch(id)
);

