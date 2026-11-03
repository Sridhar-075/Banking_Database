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