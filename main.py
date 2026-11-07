from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from decimal import Decimal
from datetime import date
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg import errors
from fastapi import FastAPI, HTTPException, Request,status
from schemas import AccountCreate,LoanCreate,LoanRepaymentCreate, LoanRepaymentResponse, LoanTypes, LoginRequest, MyAccount
from tools import calculate_emi,add_months, money



@asynccontextmanager
async def lifespan(app: FastAPI):
    

    pool = ConnectionPool(
        conninfo="postgresql://postgres:postgres@localhost:5432/banking_db",
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )

    pool.open()
    app.state.pool = pool

    try:
        yield
    finally:
        pool.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],        
    allow_headers=["*"],
)

@app.post("/auth/login",tags=["Authentication"])
def login(data: LoginRequest, request: Request):

    pool = request.app.state.pool

    with pool.connection() as conn:

        customer = conn.execute(
            """
            SELECT id, name
            FROM customer
            WHERE id = %s
            """,
            (data.customer_id,)
        ).fetchone()

        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

    return {
        "message": "Login successful",
        "customer": {
            "id": customer["id"],
            "name": customer["name"]
        }
    }

@app.get("/customers")
def get_customers(request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM customer")
                rows = cur.fetchall()

        return rows

    except psycopg.Error:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch customers",
        )

@app.get("/accounts/{id}",response_model=list[MyAccount])
def get_accounts(id:int,request:Request):
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT account_no, account_type,balance,branch_id,opened_on,status from account where customer_id=%s",(id,))
                rows=cur.fetchall()
        return rows
    except psycopg.Error:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch accounts",
            )


@app.post("/account/create", status_code=status.HTTP_201_CREATED)
def create_account(account: AccountCreate,request:Request):
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                past_account = cur.execute(
                        """
        select * from account where customer_id=%s and account_type=%s;
            """,
            (account.customer_id,account.account_type.value)

                )
                if past_account:
                    raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Customer already has a {account.account_type.value} account.",
                            )

                cur.execute(
                    """
                    INSERT INTO account (customer_id, branch_id, account_type)
                    VALUES (%s, %s, %s)
                    RETURNING *;
                    """,
                    (
                        account.customer_id,
                        account.branch_id,
                        account.account_type.value,
                    ),
                )

                new_account = cur.fetchone()

            return new_account

    except errors.ForeignKeyViolation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer or branch does not exist",
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account",
        )

from fastapi import HTTPException, status
from psycopg import errors

from schemas import TransferRequest, DepositRequest, WithdrawRequest


@app.post("/account/transfer", status_code=status.HTTP_201_CREATED)
def transfer_money(transfer: TransferRequest, request:Request):     
    source = transfer.source_account
    destination = transfer.destination_account
    amount = transfer.amount

    if source == destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination accounts must be different",
        )

    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
            # Lock both accounts in a consistent order.
                cur.execute(
                    """
                    SELECT account_no, balance, status
                    FROM account
                    WHERE account_no IN (%s, %s)
                    ORDER BY account_no
                    FOR UPDATE
                    """,
                    (source, destination),
                )

                accounts = {
                    row["account_no"]: row
                    for row in cur.fetchall()
                }

                if source not in accounts or destination not in accounts:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Source or destination account not found",
                    )

                source_account = accounts[source]
                destination_account = accounts[destination]

                if (
                    source_account["status"] != "active"
                    or destination_account["status"] != "active"
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Both accounts must be active",
                    )

                if source_account["balance"] < amount:
                    cur.execute(
                        """
                        INSERT INTO bank_transaction
                            (transaction_type, amount, description, status)
                        VALUES (%s, %s, %s, %s)
                        RETURNING transaction_id, transaction_time
                        """,
                        (
                            "transfer",
                            amount,
                            f"Failed transfer from account {source} to account {destination}: insufficient balance",
                            "failed",
                        ),
                    )

                    failed_transaction = cur.fetchone()

                    return {
                        "message": "Transfer failed",
                        "transaction_id": failed_transaction["transaction_id"],
                        "status": "failed",
                        "reason": "Insufficient balance",
                        "source_account": source,
                        "destination_account": destination,
                        "amount": amount,
                        "transaction_time": failed_transaction["transaction_time"],
                    }
                    

                # Debit the source account.
                cur.execute(
                    """
                    UPDATE account
                    SET balance = balance - %s
                    WHERE account_no = %s
                    """,
                    (amount, source),
                )

                # Credit the destination account.
                cur.execute(
                    """
                    UPDATE account
                    SET balance = balance + %s
                    WHERE account_no = %s
                    """,
                    (amount, destination),
                )

                # Create the parent transaction record.
                cur.execute(
                    """
                    INSERT INTO bank_transaction
                        (transaction_type, amount, description)
                    VALUES (%s, %s, %s)
                    RETURNING transaction_id, transaction_time
                    """,
                    (
                        "transfer",
                        amount,
                        f"Transfer from account {source} to account {destination}",
                    ),
                )

                transaction = cur.fetchone()
                transaction_id = transaction["transaction_id"]

                # Record the debit entry.
                cur.execute(
                    """
                    INSERT INTO transaction_entry
                        (transaction_id, account_no, entry_type, amount)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (transaction_id, source, "debit", amount),
                )

                # Record the credit entry.
                cur.execute(
                    """
                    INSERT INTO transaction_entry
                        (transaction_id, account_no, entry_type, amount)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (transaction_id, destination, "credit", amount),
                )

            return {
                "message": "Transfer successful",
                "transaction_id": transaction_id,
                "source_account": source,
                "destination_account": destination,
                "amount": amount,
                "transaction_time": transaction["transaction_time"],
            }

    except HTTPException:
        raise

    except errors.DeadlockDetected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer conflicted with another transaction. Please retry.",
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transfer failed",
        )

@app.get("/loan/types",response_model=list[LoanTypes])
def get_loan_types(request:Request):
    pool = request.app.state.pool
    with pool.connection() as conn:
        with conn.transaction():
            types=conn.execute("""
            select * from loan_type;
            """).fetchall()
            return types
    


@app.post("/loan/create", status_code=status.HTTP_201_CREATED)
def create_loan(data: LoanCreate, request: Request):
    pool = request.app.state.pool

    with pool.connection() as conn:
        with conn.transaction():

            # 1. Lock and fetch the disbursement account
            account = conn.execute(
                """
                SELECT account_no, customer_id, balance, status
                FROM account
                WHERE account_no = %s
                FOR UPDATE
                """,
                (data.disbursement_account,)
            ).fetchone()

            if not account:
                raise HTTPException(
                    status_code=404,
                    detail="Disbursement account not found"
                )

            if account["customer_id"] != data.customer_id:
                raise HTTPException(
                    status_code=403,
                    detail="Account does not belong to this customer"
                )

            if str(account["status"]).lower() != "active":
                raise HTTPException(
                    status_code=400,
                    detail="Account is not active"
                )

            # 2. Fetch loan type and interest rate
            loan_type = conn.execute(
                """
                SELECT id, category, interest_rate
                FROM loan_type
                WHERE id = %s
                """,
                (data.loan_type_id,)
            ).fetchone()

            if not loan_type:
                raise HTTPException(
                    status_code=404,
                    detail="Loan type not found"
                )

            # 3. Convert annual percentage to monthly decimal rate
            annual_rate = Decimal(str(loan_type["interest_rate"]))

            monthly_rate = annual_rate / Decimal("1200")

            # 4. Calculate EMI
            emi = calculate_emi(
                data.principal_amount,
                monthly_rate,
                data.tenure_months
            )

            # 5. Create disbursement transaction
            transaction = conn.execute(
                """
                INSERT INTO bank_transaction
                    (amount, transaction_type, transaction_time, description)
                VALUES
                    (%s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING transaction_id
                """,
                (
                    data.principal_amount,
                    "loan_disbursement",
                    f"Loan disbursement - {loan_type['category']}"
                )
            ).fetchone()

            transaction_id = transaction["transaction_id"]

            # 6. Credit the customer's bank account
            conn.execute(
                """
                UPDATE account
                SET balance = balance + %s
                WHERE account_no = %s
                """,
                (
                    data.principal_amount,
                    data.disbursement_account
                )
            )

            # Record the credit entry
            conn.execute(
                """
                INSERT INTO transaction_entry
                    (transaction_id, account_no, entry_type, amount)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    data.disbursement_account,
                    "credit",
                    data.principal_amount
                )
            )

            # 7. Create the loan account
            loan = conn.execute(
                """
                INSERT INTO loan_account (
                    customer_id,
                    disbursement_account,
                    disbursement_transaction_id,
                    loan_type_id,
                    principal_amount,
                    principal_outstanding,
                    first_payment_date,
                    tenure_months,
                    interest_rate_monthly,
                    emi_amount,
                    next_installment_number,
                    next_payment_due,
                    status
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING loan_id
                """,
                (
                    data.customer_id,
                    data.disbursement_account,
                    transaction_id,
                    data.loan_type_id,
                    data.principal_amount,
                    data.principal_amount,
                    add_months(date.today(),1),
                    data.tenure_months,
                    monthly_rate,
                    emi,
                    1,
                    add_months(date.today(),1),
                    "ACTIVE"
                )
            ).fetchone()

            loan_id = loan["loan_id"]

    return {
        "message": "Loan created successfully",
        "loan_id": loan_id,
        "transaction_id": transaction_id,
        "principal_amount": data.principal_amount,
        "monthly_interest_rate": monthly_rate,
        "emi_amount": emi,
        "next_payment_due": add_months(date.today(),1)
    }

@app.post("/account/deposit", status_code=status.HTTP_201_CREATED)
def deposit_money(deposit: DepositRequest, request: Request):
    account_no = deposit.account_no
    amount = deposit.amount

    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                # Lock the account row for update
                cur.execute(
                    """
                    SELECT account_no, balance, status
                    FROM account
                    WHERE account_no = %s
                    FOR UPDATE
                    """,
                    (account_no,),
                )

                account = cur.fetchone()

                if not account:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Account not found",
                    )

                if account["status"] != "active":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Account is not active",
                    )

                # Update the account balance
                cur.execute(
                    """
                    UPDATE account
                    SET balance = balance + %s
                    WHERE account_no = %s
                    RETURNING balance
                    """,
                    (amount, account_no),
                )

                updated_account = cur.fetchone()
                new_balance = updated_account["balance"]

                # Record parent bank_transaction
                cur.execute(
                    """
                    INSERT INTO bank_transaction
                        (transaction_type, amount, description, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING transaction_id, transaction_time
                    """,
                    (
                        "deposit",
                        amount,
                        f"Deposit into account {account_no}",
                        "successful",
                    ),
                )

                transaction = cur.fetchone()
                transaction_id = transaction["transaction_id"]

                # Record credit entry in transaction_entry
                cur.execute(
                    """
                    INSERT INTO transaction_entry
                        (transaction_id, account_no, entry_type, amount)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (transaction_id, account_no, "credit", amount),
                )

            return {
                "message": "Deposit successful",
                "transaction_id": transaction_id,
                "account_no": account_no,
                "amount": amount,
                "balance": new_balance,
                "transaction_time": transaction["transaction_time"],
            }

    except HTTPException:
        raise

    except errors.DeadlockDetected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction conflicted with another operation. Please retry.",
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deposit failed",
        )


@app.post("/account/withdraw", status_code=status.HTTP_201_CREATED)
def withdraw_money(withdraw: WithdrawRequest, request: Request):
    account_no = withdraw.account_no
    amount = withdraw.amount

    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                # Lock the account row for update
                cur.execute(
                    """
                    SELECT account_no, balance, status
                    FROM account
                    WHERE account_no = %s
                    FOR UPDATE
                    """,
                    (account_no,),
                )

                account = cur.fetchone()

                if not account:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Account not found",
                    )

                if account["status"] != "active":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Account is not active",
                    )

                if account["balance"] < amount:
                    # Record failed transaction in transaction history
                    cur.execute(
                        """
                        INSERT INTO bank_transaction
                            (transaction_type, amount, description, status)
                        VALUES (%s, %s, %s, %s)
                        RETURNING transaction_id, transaction_time
                        """,
                        (
                            "withdrawal",
                            amount,
                            f"Failed withdrawal from account {account_no}: insufficient balance",
                            "failed",
                        ),
                    )

                    failed_transaction = cur.fetchone()

                    return {
                        "message": "Withdrawal failed",
                        "transaction_id": failed_transaction["transaction_id"],
                        "status": "failed",
                        "reason": "Insufficient balance",
                        "account_no": account_no,
                        "amount": amount,
                        "balance": account["balance"],
                        "transaction_time": failed_transaction["transaction_time"],
                    }

                # Debit the account balance
                cur.execute(
                    """
                    UPDATE account
                    SET balance = balance - %s
                    WHERE account_no = %s
                    RETURNING balance
                    """,
                    (amount, account_no),
                )

                updated_account = cur.fetchone()
                new_balance = updated_account["balance"]

                # Record parent bank_transaction
                cur.execute(
                    """
                    INSERT INTO bank_transaction
                        (transaction_type, amount, description, status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING transaction_id, transaction_time
                    """,
                    (
                        "withdrawal",
                        amount,
                        f"Withdrawal from account {account_no}",
                        "successful",
                    ),
                )

                transaction = cur.fetchone()
                transaction_id = transaction["transaction_id"]

                # Record debit entry in transaction_entry
                cur.execute(
                    """
                    INSERT INTO transaction_entry
                        (transaction_id, account_no, entry_type, amount)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (transaction_id, account_no, "debit", amount),
                )

            return {
                "message": "Withdrawal successful",
                "transaction_id": transaction_id,
                "account_no": account_no,
                "amount": amount,
                "balance": new_balance,
                "transaction_time": transaction["transaction_time"],
            }

    except HTTPException:
        raise

    except errors.DeadlockDetected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction conflicted with another operation. Please retry.",
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Withdrawal failed",
        )

@app.get("/loans/{id}")
def list_loans(id:int, request:Request):
    
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
                loans = cur.execute("""
                select customer_id,disbursement_account,principal_amount,principal_outstanding,interest_rate_monthly,tenure_months,emi_amount,status,first_payment_date,next_installment_number,next_payment_due,loan_id from loan_account where customer_id=%s
                """,(id,)).fetchall()
                return loans

    except psycopg.Error:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch loans",
            )

@app.get(
    "/loans/{customer_id}/{loan_id}/repayments",
    response_model=list[LoanRepaymentResponse]
)
def get_loan_repayments(
    customer_id: int,
    loan_id: int,
    request: Request
):
    with request.app.state.pool.connection() as conn:

        repayments = conn.execute(
            """
            SELECT
                lr.repayment_id,
                lr.transaction_id,
                lr.installment_number,
                lr.payment_date,
                lr.payment_due,
                lr.interest_paid,
                lr.principal_paid
            FROM loan_repayment lr
            JOIN loan_account la
                ON lr.loan_id = la.loan_id
            WHERE la.customer_id = %s
              AND la.loan_id = %s
            ORDER BY lr.installment_number DESC;
            """,
            (customer_id, loan_id)
        ).fetchall()

        return repayments
@app.post("/loan/repay/{loan_id}")
def repay_loan(
    loan_id: int,
    data: LoanRepaymentCreate,
    request: Request
):

    pool = request.app.state.pool

    with pool.connection() as conn:
        with conn.transaction():

            # 1. Lock and fetch the loan
            loan = conn.execute(
                """
                SELECT *
                FROM loan_account
                WHERE loan_id = %s
                FOR UPDATE
                """,
                (loan_id,)
            ).fetchone()
            
            if not loan:
                raise HTTPException(
                    status_code=404,
                    detail="Loan not found"
                )

            if loan["status"] != "ACTIVE":
                raise HTTPException(
                    status_code=400,
                    detail="Loan is not active"
                )
            today = conn.execute(
                "SELECT CURRENT_DATE AS today"
            ).fetchone()["today"]

            if today < loan["next_payment_due"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Next installment is due on {loan['next_payment_due']}. Early repayment is not allowed."
                )
            # # 2. Fetch and lock the repayment account
            account = conn.execute(
                """
                SELECT account_no, customer_id, balance, status
                FROM account
                WHERE account_no = %s
                FOR UPDATE
                """,
                (loan['disbursement_account'],)
            ).fetchone()

            # if not account:
            #     raise HTTPException(
            #         status_code=404,
            #         detail="Repayment account not found"
            #     )

            # if account["customer_id"] != loan["customer_id"]:
            #     raise HTTPException(
            #         status_code=403,
            #         detail="Repayment account does not belong to loan customer"
            #     )

            # if str(account["status"]).lower() != "active":
            #     raise HTTPException(
            #         status_code=400,
            #         detail="Repayment account is not active"
            #     )

            # 3. Get current loan information
            outstanding = Decimal(
                str(loan["principal_outstanding"])
            )

            monthly_rate = Decimal(
                str(loan["interest_rate_monthly"])
            )

            emi = Decimal(str(loan["emi_amount"]))

            installment_number = loan["next_installment_number"]
            payment_due = loan["next_payment_due"]

            if installment_number > loan["tenure_months"]:
                raise HTTPException(
                    status_code=400,
                    detail="Loan has exhausted its repayment tenure"
                )

            # 4. Calculate the current installment's interest
            interest_due = money(outstanding * monthly_rate)

            # Total amount needed to close the loan today
            payoff_amount = money(outstanding + interest_due)

            # The final scheduled installment clears the entire balance.
            if installment_number == loan["tenure_months"]:
                installment_due = payoff_amount
            else:
                installment_due = min(emi, payoff_amount)

            payment_amount = money(data.amount)

            # 5. Validate repayment amount
            if payment_amount < installment_due:
                raise HTTPException(
                    status_code=400,
                    detail=f"Minimum payment required is {installment_due}"
                )
            refund_needed=False
            refund=0
            if payment_amount > payoff_amount:
                refund_needed=True
                refund = payment_amount-payoff_amount

            # 6. Check account balance
            balance = Decimal(str(account["balance"]))

            if balance < payment_amount:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient account balance"
                )

            # 7. Calculate interest and principal components
            interest_paid = interest_due

            # Includes scheduled principal + extra principal
            if refund_needed:
                principal_paid=outstanding
                new_outstanding=0
            else:  
                principal_paid = money(
                    payment_amount - interest_paid
                )

                new_outstanding = money(
                    outstanding - principal_paid
                )

            # 8. Determine loan status
            is_closed = new_outstanding == Decimal("0.00")

            next_installment_number = installment_number + 1

            if is_closed:
                new_status = "CLOSED"
                next_payment_due = None
            else:
                new_status = "ACTIVE"

                next_payment_due = add_months(
                    loan["first_payment_date"],
                    next_installment_number - 1
                )

            # 9. Create bank transaction
            transaction = conn.execute(
                """
                INSERT INTO bank_transaction
                    (amount, transaction_type, transaction_time, description)
                VALUES
                    (%s, %s, CURRENT_TIMESTAMP, %s)
                RETURNING transaction_id
                """,
                (
                    payment_amount,
                    "loan_repayment",
                    f"Repayment for loan {loan_id}, installment {installment_number}"
                )
            ).fetchone()

            transaction_id = transaction["transaction_id"]

            # 10. Deduct amount from customer's bank account
            conn.execute(
                """
                UPDATE account
                SET balance = balance - %s
                WHERE account_no = %s
                """,
                (
                    payment_amount,
                    loan['disbursement_account']
                )
            )

            # Record debit entry
            conn.execute(
                """
                INSERT INTO transaction_entry
                    (transaction_id, account_no, entry_type, amount)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    transaction_id,
                   loan['disbursement_account'],
                    "debit",
                    payment_amount
                )
            )
            if refund_needed:
                refund_transaction = conn.execute(
                    """
            INSERT INTO bank_transaction
                                (amount, transaction_type, transaction_time, description)
                            VALUES
                                (%s, %s, CURRENT_TIMESTAMP, %s)
                            RETURNING transaction_id

                """,
                (refund,"deposit",f"Bank Refund for loan {loan_id}")
                ).fetchone()
                conn.execute(
                        """
                        UPDATE account
                        SET balance = balance + %s
                        WHERE account_no = %s
                        """,
                        (
                            refund,
                            loan['disbursement_account']
                        )
                            )
                conn.execute(
                        """
                        INSERT INTO transaction_entry
                            (transaction_id, account_no, entry_type, amount)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            refund_transaction["transaction_id"],
                            loan['disbursement_account'],
                            "credit",
                            refund
                        )
                            )
            # 11. Insert loan repayment history
            repayment = conn.execute(
                """
                INSERT INTO loan_repayment (
                    transaction_id,
                    loan_id,
                    installment_number,
                    payment_date,
                    payment_due,
                    installment_due,
                    interest_paid,
                    principal_paid
                )
                VALUES (
                    %s, %s, %s, CURRENT_DATE, %s, %s, %s, %s
                )
                RETURNING repayment_id
                """,
                (
                    transaction_id,
                    loan_id,
                    installment_number,
                    payment_due,
                    installment_due,
                    interest_paid,
                    principal_paid
                )
            ).fetchone()

            # 12. Update outstanding principal and next installment
            conn.execute(
                """
                UPDATE loan_account
                SET principal_outstanding = %s,
                    next_installment_number = %s,
                    next_payment_due = %s,
                    status = %s
                WHERE loan_id = %s
                """,
                (
                    new_outstanding,
                    next_installment_number,
                    next_payment_due,
                    new_status,
                    loan_id
                )
            )

    return {
        "message": "Loan repayment successful",
        "transaction_id": transaction_id,
        "repayment_id": repayment["repayment_id"],
        "installment_number": installment_number,
        "installment_due": installment_due,
        "amount_paid": payment_amount,
        "interest_paid": interest_paid,
        "principal_paid": principal_paid,
        "previous_outstanding": outstanding,
        "new_outstanding": new_outstanding,
        "amount_refund":refund,
        "loan_status": new_status,
        "next_payment_due": next_payment_due
    }


@app.get("/transactions/{customer_id}")
def get_transactions(customer_id: int, request: Request):

    with request.app.state.pool.connection() as conn:

        transactions = conn.execute(
            """
            SELECT
                bt.transaction_id,
                bt.transaction_time,
                bt.transaction_type,
                bt.description,
                te.entry_type,
                te.amount,
                te.account_no AS account_number

            FROM bank_transaction bt

            JOIN transaction_entry te
                ON bt.transaction_id = te.transaction_id

            JOIN account a
                ON te.account_no = a.account_no

            WHERE a.customer_id = %s

            ORDER BY bt.transaction_time DESC;
            """,
            (customer_id,)
        ).fetchall()
    return transactions