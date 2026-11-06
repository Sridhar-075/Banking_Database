alter table account
add constraint uq_customer_accounttype
UNIQUE(customer_id,account_type);
