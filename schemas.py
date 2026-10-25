from enum import Enum

from pydantic import BaseModel


class AccountType(str, Enum):
    Savings = "Savings"
    Current = "Current"


class AccountCreate(BaseModel):
    customer_id: int
    branch_id: int
    account_type: AccountType


