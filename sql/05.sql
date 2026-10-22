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