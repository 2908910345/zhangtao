from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BalanceSubjectCreate(BaseModel):
    code: str
    name: str
    year_start_debit: float = 0.0
    year_start_credit: float = 0.0
    period_debit: float = 0.0
    period_credit: float = 0.0
    year_total_debit: float = 0.0
    year_total_credit: float = 0.0
    end_debit: float = 0.0
    end_credit: float = 0.0
    dimension: str = ""


class BalanceSubjectResponse(BalanceSubjectCreate):
    id: int
    book_name: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BalanceListResponse(BaseModel):
    subjects: list[BalanceSubjectResponse] = []
    total: int = 0


class JournalEntryCreate(BaseModel):
    org: str = ""
    period: str = ""
    voucher_no: str
    summary: str = ""
    subject_code: str
    subject_name: str = ""
    debit: float = 0.0
    credit: float = 0.0
    dimension: str = ""


class JournalEntryResponse(JournalEntryCreate):
    id: int
    book_name: str = ""
    created_at: Optional[datetime] = None
    counterpart: str = ""

    model_config = {"from_attributes": True}


class SubjectTreeNode(BaseModel):
    code: str
    name: str
    level: int = 1
    year_start_debit: float = 0.0
    year_start_credit: float = 0.0
    period_debit: float = 0.0
    period_credit: float = 0.0
    year_total_debit: float = 0.0
    year_total_credit: float = 0.0
    end_debit: float = 0.0
    end_credit: float = 0.0
    children: list["SubjectTreeNode"] = []


class BalanceDetailResponse(BaseModel):
    code: str
    name: str
    year_start_debit: float = 0.0
    year_start_credit: float = 0.0
    period_debit: float = 0.0
    period_credit: float = 0.0
    year_total_debit: float = 0.0
    year_total_credit: float = 0.0
    end_debit: float = 0.0
    end_credit: float = 0.0
    dimension: str = ""


class Statistics(BaseModel):
    subject_count: int = 0
    voucher_count: int = 0
    period_range: str = ""


class DimensionItem(BaseModel):
    type: str
    value: str


class DimensionResponse(BaseModel):
    code: str
    name: str
    dimensions: list[DimensionItem] = []


class MessageResponse(BaseModel):
    message: str


class UploadBalanceResponse(BaseModel):
    count: int
    message: str


class UploadJournalResponse(BaseModel):
    count: int
    voucher_count: int
    subject_count: int
    message: str


class BookCreate(BaseModel):
    name: str
    description: str = ""


class BookResponse(BaseModel):
    id: int
    name: str
    description: str = ""
    subject_count: int = 0
    voucher_count: int = 0
    is_active: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    books: list[BookResponse] = []
    current: str = "default"