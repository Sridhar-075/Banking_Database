CREATE TABLE Customer (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dob DATE,
    phone VARCHAR(15),
    address VARCHAR(255)
);

CREATE TABLE Branch (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TYPE loan_category AS ENUM (
    'HOME',
    'PERSONAL',
    'EDUCATION',
    'VEHICLE',
    'BUSINESS'
);

CREATE TABLE Loan_type (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category loan_category NOT NULL,
    interest_rate NUMERIC(5,2) NOT NULL
        CHECK (interest_rate >= 0 AND interest_rate <= 100)
);

CREATE TABLE account (
    account_no INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

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


INSERT INTO customer (name, dob, phone, address)
VALUES
    ('Arun Kumar', '1990-05-14', '9876543210', 'Chennai'),
    ('Priya Sharma', '1985-11-22', '9876543211', 'Bengaluru'),
    ('Rahul Menon', '1998-02-10', '9876543212', 'Kochi'),
    ('Sneha Reddy', '1992-07-18', '9876543213', 'Hyderabad'),
    ('Vikram Singh', '1988-09-05', '9876543214', 'Mumbai'),
    ('Ananya Iyer', '1995-12-30', '9876543215', 'Coimbatore'),
    ('Karthik Nair', '2000-03-25', '9876543216', 'Thiruvananthapuram'),
    ('Meera Das', '1993-06-08', '9876543217', 'Kolkata');



INSERT INTO loan_type (category, interest_rate)
VALUES
    ('HOME', 8.50),
    ('PERSONAL', 12.50),
    ('EDUCATION', 7.25),
    ('VEHICLE', 9.00),
    ('BUSINESS', 10.50);

INSERT INTO branch (name)
VALUES
    ('Chennai Main Branch'),
    ('Bengaluru Branch'),
    ('Kochi Branch');



CREATE TYPE account_type_enum AS ENUM (
    'Savings',
    'Current'
);
ALTER TABLE account
ADD COLUMN account_type account_type_enum NOT NULL DEFAULT 'Savings';

ALTER TABLE bank_transaction
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'successful'
CHECK (status IN ('successful', 'failed'));

alter table loan_account 
ADD COLUMN emi_amount NUMERIC(14,2),
ADD COLUMN next_installment_number INTEGER,
ADD COLUMN next_payment_due DATE,
ADD COLUMN status VARCHAR(10);

alter table loan_repayment 
add column installment_due numeric(14,2);
drop column payment_date;

ALTER TABLE loan_repayment
RENAME COLUMN interest_period_number TO installment_number;

ALTER TABLE loan_repayment
ADD CONSTRAINT uq_loan_installment
UNIQUE (loan_id, installment_number);

ALTER TABLE loan_repayment
ADD CONSTRAINT uq_repayment_transaction
UNIQUE (transaction_id);