from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AccountType(str, Enum):
    Savings = "Savings"
    Current = "Current"


class AccountCreate(BaseModel):
    customer_id: int
    branch_id: int
    account_type: AccountType


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_account: int = Field(gt=0)
    destination_account: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)


class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_no: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_no: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
