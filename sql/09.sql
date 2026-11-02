alter table loan_account 
ADD COLUMN emi_amount NUMERIC(14,2),
ADD COLUMN next_installment_number INTEGER,
ADD COLUMN next_payment_due DATE,
ADD COLUMN status VARCHAR(10);

alter table loan_repayment 
add column installment_due numeric(14,2);
drop column payment_date;