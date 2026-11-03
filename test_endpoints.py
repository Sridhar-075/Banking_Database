"""
Comprehensive Unit and Integration-style Tests for Deposit & Withdrawal Endpoints.
Uses Python's standard library `unittest` directly with FastAPI/Pydantic models and handler functions,
without requiring third-party testing clients like httpx/httpx2 or external live PostgreSQL.
"""

import unittest
from decimal import Decimal
from contextlib import contextmanager
from types import SimpleNamespace
from fastapi import HTTPException
from pydantic import ValidationError

from schemas import DepositRequest, WithdrawRequest
from main import deposit_money, withdraw_money


class MockCursor:
    def __init__(self, db_state):
        self.db = db_state
        self._last_result = None
        self._last_results = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, query, params: tuple = ()):
        q = " ".join(query.strip().split())

        # Account lookup with FOR UPDATE
        if "SELECT account_no, balance, status FROM account WHERE account_no = %s" in q:
            acc_id = params[0]
            if acc_id in self.db["accounts"]:
                acc = self.db["accounts"][acc_id]
                self._last_result = {
                    "account_no": acc_id,
                    "balance": acc["balance"],
                    "status": acc["status"],
                }
            else:
                self._last_result = None

        # Deposit balance update
        elif "UPDATE account SET balance = balance + %s WHERE account_no = %s" in q:
            amount, acc_id = params
            self.db["accounts"][acc_id]["balance"] += Decimal(str(amount))
            self._last_result = {"balance": self.db["accounts"][acc_id]["balance"]}

        # Withdrawal balance update
        elif "UPDATE account SET balance = balance - %s WHERE account_no = %s" in q:
            amount, acc_id = params
            self.db["accounts"][acc_id]["balance"] -= Decimal(str(amount))
            self._last_result = {"balance": self.db["accounts"][acc_id]["balance"]}

        # bank_transaction insert
        elif "INSERT INTO bank_transaction" in q:
            tx_type, amount, desc, tx_status = params
            self.db["tx_id_seq"] += 1
            tx_record = {
                "transaction_id": self.db["tx_id_seq"],
                "transaction_type": tx_type,
                "amount": Decimal(str(amount)),
                "description": desc,
                "status": tx_status,
                "transaction_time": "2026-11-03T18:30:00",
            }
            self.db["transactions"].append(tx_record)
            self._last_result = {
                "transaction_id": tx_record["transaction_id"],
                "transaction_time": tx_record["transaction_time"],
            }

        # transaction_entry insert
        elif "INSERT INTO transaction_entry" in q:
            tx_id, acc_no, entry_type, amount = params
            self.db["entry_id_seq"] += 1
            entry_record = {
                "entry_id": self.db["entry_id_seq"],
                "transaction_id": tx_id,
                "account_no": acc_no,
                "entry_type": entry_type,
                "amount": Decimal(str(amount)),
            }
            self.db["entries"].append(entry_record)
            self._last_result = None

    def fetchone(self):
        return self._last_result

    def fetchall(self):
        return self._last_results


class MockConnection:
    def __init__(self, db_state):
        self.db = db_state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def cursor(self):
        return MockCursor(self.db)


class MockPool:
    def __init__(self, db_state):
        self.db = db_state

    @contextmanager
    def connection(self):
        yield MockConnection(self.db)


class MockRequest:
    def __init__(self, pool):
        self.app = SimpleNamespace(state=SimpleNamespace(pool=pool))


class TestDepositAndWithdraw(unittest.TestCase):
    def setUp(self):
        self.db = {
            "accounts": {
                1: {"balance": Decimal("1000.00"), "status": "active"},
                2: {"balance": Decimal("50.00"), "status": "frozen"},
                3: {"balance": Decimal("0.00"), "status": "active"},
            },
            "transactions": [],
            "entries": [],
            "tx_id_seq": 100,
            "entry_id_seq": 500,
        }
        self.pool = MockPool(self.db)
        self.request = MockRequest(self.pool)

    # ==================== DEPOSIT TESTS ====================

    def test_deposit_valid_amount(self):
        """1. Deposit a valid amount into an existing active account."""
        req = DepositRequest(account_no=1, amount=Decimal("500.00"))
        res = deposit_money(req, self.request)

        self.assertEqual(res["message"], "Deposit successful")
        self.assertEqual(res["account_no"], 1)
        self.assertEqual(res["amount"], Decimal("500.00"))
        self.assertEqual(res["balance"], Decimal("1500.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1500.00"))

        # Check bank_transaction table
        self.assertEqual(len(self.db["transactions"]), 1)
        self.assertEqual(self.db["transactions"][0]["transaction_type"], "deposit")
        self.assertEqual(self.db["transactions"][0]["status"], "successful")

        # Check transaction_entry table
        self.assertEqual(len(self.db["entries"]), 1)
        self.assertEqual(self.db["entries"][0]["entry_type"], "credit")
        self.assertEqual(self.db["entries"][0]["account_no"], 1)
        self.assertEqual(self.db["entries"][0]["amount"], Decimal("500.00"))

    def test_deposit_decimal_amount(self):
        """2. Deposit a decimal amount (e.g. 123.45)."""
        req = DepositRequest(account_no=1, amount=Decimal("123.45"))
        res = deposit_money(req, self.request)

        self.assertEqual(res["balance"], Decimal("1123.45"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1123.45"))

    def test_deposit_zero_amount(self):
        """3. Attempt to deposit zero - rejected by schema validation."""
        with self.assertRaises(ValidationError):
            DepositRequest(account_no=1, amount=Decimal("0.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1000.00"))

    def test_deposit_negative_amount(self):
        """4. Attempt to deposit a negative amount - rejected by schema validation."""
        with self.assertRaises(ValidationError):
            DepositRequest(account_no=1, amount=Decimal("-100.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1000.00"))

    def test_deposit_nonexistent_account(self):
        """5. Attempt to deposit into a nonexistent account - raises 404."""
        req = DepositRequest(account_no=999, amount=Decimal("100.00"))
        with self.assertRaises(HTTPException) as cm:
            deposit_money(req, self.request)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.detail, "Account not found")

    def test_deposit_frozen_account(self):
        """6. Attempt to deposit into an inactive/frozen account - raises 400."""
        req = DepositRequest(account_no=2, amount=Decimal("100.00"))
        with self.assertRaises(HTTPException) as cm:
            deposit_money(req, self.request)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "Account is not active")

    def test_deposit_validation_missing_amount(self):
        """7. Deposit request missing amount - raises ValidationError."""
        with self.assertRaises(ValidationError):
            DepositRequest(account_no=1)

    def test_deposit_validation_extra_fields(self):
        """8. Extra fields are rejected due to extra='forbid'."""
        with self.assertRaises(ValidationError):
            DepositRequest.model_validate({"account_no": 1, "amount": Decimal("50.00"), "extra_note": "test"})

    # ==================== WITHDRAWAL TESTS ====================

    def test_withdraw_valid_amount(self):
        """1. Withdraw a valid amount from an active account."""
        req = WithdrawRequest(account_no=1, amount=Decimal("400.00"))
        res = withdraw_money(req, self.request)

        self.assertEqual(res["message"], "Withdrawal successful")
        self.assertEqual(res["account_no"], 1)
        self.assertEqual(res["amount"], Decimal("400.00"))
        self.assertEqual(res["balance"], Decimal("600.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("600.00"))

        # Check bank_transaction table
        self.assertEqual(len(self.db["transactions"]), 1)
        self.assertEqual(self.db["transactions"][0]["transaction_type"], "withdrawal")
        self.assertEqual(self.db["transactions"][0]["status"], "successful")

        # Check transaction_entry table
        self.assertEqual(len(self.db["entries"]), 1)
        self.assertEqual(self.db["entries"][0]["entry_type"], "debit")
        self.assertEqual(self.db["entries"][0]["account_no"], 1)
        self.assertEqual(self.db["entries"][0]["amount"], Decimal("400.00"))

    def test_withdraw_entire_balance(self):
        """2. Withdraw amount equal to entire balance - leaves 0.00."""
        req = WithdrawRequest(account_no=1, amount=Decimal("1000.00"))
        res = withdraw_money(req, self.request)

        self.assertEqual(res["balance"], Decimal("0.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("0.00"))

    def test_withdraw_insufficient_funds(self):
        """3. Attempt to withdraw more than available balance - records failed transaction without altering balance."""
        initial_balance = self.db["accounts"][1]["balance"]
        req = WithdrawRequest(account_no=1, amount=Decimal("1500.00"))
        res = withdraw_money(req, self.request)

        self.assertEqual(res["message"], "Withdrawal failed")
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["reason"], "Insufficient balance")
        self.assertEqual(res["balance"], initial_balance)
        self.assertEqual(self.db["accounts"][1]["balance"], initial_balance)

        # Audit history shows failed bank_transaction, but NO debit entry created
        self.assertEqual(len(self.db["transactions"]), 1)
        self.assertEqual(self.db["transactions"][0]["transaction_type"], "withdrawal")
        self.assertEqual(self.db["transactions"][0]["status"], "failed")
        self.assertEqual(len(self.db["entries"]), 0)

    def test_withdraw_zero_amount(self):
        """4. Attempt to withdraw zero - rejected by schema validation."""
        with self.assertRaises(ValidationError):
            WithdrawRequest(account_no=1, amount=Decimal("0.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1000.00"))

    def test_withdraw_negative_amount(self):
        """5. Attempt to withdraw negative amount - rejected by schema validation."""
        with self.assertRaises(ValidationError):
            WithdrawRequest(account_no=1, amount=Decimal("-50.00"))
        self.assertEqual(self.db["accounts"][1]["balance"], Decimal("1000.00"))

    def test_withdraw_nonexistent_account(self):
        """6. Attempt to withdraw from nonexistent account - raises 404."""
        req = WithdrawRequest(account_no=999, amount=Decimal("50.00"))
        with self.assertRaises(HTTPException) as cm:
            withdraw_money(req, self.request)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertEqual(cm.exception.detail, "Account not found")

    def test_withdraw_frozen_account(self):
        """7. Attempt to withdraw from frozen account - raises 400."""
        req = WithdrawRequest(account_no=2, amount=Decimal("20.00"))
        with self.assertRaises(HTTPException) as cm:
            withdraw_money(req, self.request)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertEqual(cm.exception.detail, "Account is not active")

    def test_withdraw_missing_amount(self):
        """8. Withdraw request missing amount - raises ValidationError."""
        with self.assertRaises(ValidationError):
            WithdrawRequest(account_no=1)


if __name__ == "__main__":
    unittest.main()
