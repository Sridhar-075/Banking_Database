
CREATE TABLE bank_transaction (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_type VARCHAR(20) NOT NULL
        CHECK (transaction_type IN (
            'deposit',
            'withdrawal',
            'transfer',
            'loan_disbursement',
            'loan_repayment'
        )),

    amount NUMERIC(15, 2) NOT NULL
        CHECK (amount > 0),

    transaction_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    description TEXT
);

CREATE TYPE entry_type_enum AS ENUM (
    'credit',
    'debit'
);

CREATE TABLE transaction_entry (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL
        REFERENCES bank_transaction(transaction_id),

    account_no BIGINT NOT NULL
        REFERENCES account(account_no),

    entry_type entry_type_enum NOT NULL,

    amount NUMERIC(15, 2) NOT NULL
        CHECK (amount > 0)
);