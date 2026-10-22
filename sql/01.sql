
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
