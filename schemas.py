from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

class LoginRequest(BaseModel):
    customer_id: int


class AccountType(str, Enum):
    Savings = "Savings"
    Current = "Current"


class AccountCreate(BaseModel):
    customer_id: int
    branch_id: int
    account_type: AccountType

class MyAccount(BaseModel):
    account_number: int = Field(validation_alias="account_no")
    account_type:str
    balance:float
    branch_id: int
    opened_on:date 
    status:str


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_account: int = Field(gt=0)
    destination_account: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)

class LoanCreate(BaseModel):
    customer_id: int = Field(gt=0)
    disbursement_account: int = Field(gt=0)
    loan_type_id: int = Field(gt=0)

    principal_amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2
    )

    tenure_months: int = Field(gt=0, le=600)
    # first_payment_date: date


class LoanRepaymentCreate(BaseModel):
    
 
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2
    )

class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_no: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)


class WithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_no: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
