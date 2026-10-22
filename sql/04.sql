
CREATE TABLE loan_account (
    loan_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    customer_id INTEGER NOT NULL
        REFERENCES customer(id),

    disbursement_account BIGINT NOT NULL
        REFERENCES account(account_no),

    disbursement_transaction_id BIGINT NOT NULL
        REFERENCES bank_transaction(transaction_id),

    loan_type_id INTEGER NOT NULL
        REFERENCES loan_type(id),

    principal_amount NUMERIC(15, 2) NOT NULL
        CHECK (principal_amount > 0),

    principal_outstanding NUMERIC(15, 2) NOT NULL
        CHECK (principal_outstanding >= 0),

    first_payment_date DATE NOT NULL,

    tenure_months INTEGER NOT NULL
        CHECK (tenure_months > 0),

    interest_rate_monthly NUMERIC(7, 4) NOT NULL
        CHECK (interest_rate_monthly >= 0),

    CHECK (principal_outstanding <= principal_amount)
);
CREATE TABLE loan_repayment (
    repayment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id BIGINT NOT NULL UNIQUE
        REFERENCES bank_transaction(transaction_id),

    loan_id BIGINT NOT NULL
        REFERENCES loan_account(loan_id),

    interest_period_number INTEGER NOT NULL
        CHECK (interest_period_number > 0),

    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,

    payment_due DATE NOT NULL,

    interest_paid NUMERIC(14, 2) NOT NULL DEFAULT 0
        CHECK (interest_paid >= 0),

    principal_paid NUMERIC(14, 2) NOT NULL
        CHECK (principal_paid > 0),

    UNIQUE (loan_id, interest_period_number)
);


ALTER TABLE loan_type
ALTER COLUMN category TYPE VARCHAR(30)
USING category::VARCHAR;

DROP TYPE loan_category;