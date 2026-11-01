from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg import errors
from fastapi import FastAPI, HTTPException, Request,status
from schemas import AccountCreate



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

@app.post("/account/create", status_code=status.HTTP_201_CREATED)
def create_account(account: AccountCreate,request:Request):
    try:
        with request.app.state.pool.connection() as conn:
            with conn.cursor() as cur:
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

from schemas import TransferRequest


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