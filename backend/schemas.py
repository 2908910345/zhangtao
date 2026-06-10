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
    has_children: bool = False
    dimension: str = ""
    is_dimension: bool = False  # 标记是否为维度节点


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


class DetailHierarchyRow(BaseModel):
    """底稿明细表层级行"""
    unit_name: str = ""        # 单位名称
    nature: str = ""           # 款项性质（科目名称）
    opening: float = 0.0       # 期初金额（年初借+年初贷）
    debit: float = 0.0         # 借方发生额
    credit: float = 0.0        # 贷方发生额
    is_total: bool = False     # 是否为合计/小计行
    level: int = 1             # 层级缩进
    subject_code: str = ""     # 科目编码


class DetailHierarchyResponse(BaseModel):
    template_name: str = ""
    template_code: str = ""
    category: str = ""
    opening_sign: str = "debit"
    rows: list[DetailHierarchyRow] = []
    total_row: DetailHierarchyRow | None = None  # 总计行


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


class VoucherSummary(BaseModel):
    voucher_no: str
    period: str = ""
    entry_count: int = 0
    total_debit: float = 0.0
    total_credit: float = 0.0
    first_summary: str = ""


class VoucherListResponse(BaseModel):
    vouchers: list[VoucherSummary] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


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