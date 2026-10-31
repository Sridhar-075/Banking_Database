ALTER TABLE bank_transaction
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'successful'
CHECK (status IN ('successful', 'failed'));
