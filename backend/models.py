from sqlalchemy import Column, Integer, String, Numeric, DateTime, func
from backend.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, comment="账套名称")
    description = Column(String(500), default="", comment="账套描述")
    subject_count = Column(Integer, default=0, comment="科目数")
    voucher_count = Column(Integer, default=0, comment="凭证数")
    is_active = Column(Integer, default=0, comment="是否为当前激活账套 1=是")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class BalanceSubject(Base):
    __tablename__ = "balance_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_name = Column(String(200), default="default", nullable=False, index=True, comment="所属账套")
    code = Column(String(50), nullable=False, index=True, comment="科目编码")
    name = Column(String(200), nullable=False, comment="科目名称")
    year_start_debit = Column(Numeric(18, 2), default=0.0, comment="年初余额-借方")
    year_start_credit = Column(Numeric(18, 2), default=0.0, comment="年初余额-贷方")
    period_debit = Column(Numeric(18, 2), default=0.0, comment="本期发生额-借方")
    period_credit = Column(Numeric(18, 2), default=0.0, comment="本期发生额-贷方")
    year_total_debit = Column(Numeric(18, 2), default=0.0, comment="本年累计-借方")
    year_total_credit = Column(Numeric(18, 2), default=0.0, comment="本年累计-贷方")
    end_debit = Column(Numeric(18, 2), default=0.0, comment="期末余额-借方")
    end_credit = Column(Numeric(18, 2), default=0.0, comment="期末余额-贷方")
    dimension = Column(String(500), default="", comment="核算维度")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_name = Column(String(200), default="default", nullable=False, index=True, comment="所属账套")
    org = Column(String(100), default="", comment="核算组织")
    date = Column(String(20), default="", comment="记账日期")
    period = Column(String(50), default="", index=True, comment="期间")
    voucher_no = Column(String(50), nullable=False, index=True, comment="凭证号")
    summary = Column(String(500), default="", comment="摘要")
    subject_code = Column(String(50), nullable=False, index=True, comment="科目编码")
    subject_name = Column(String(200), default="", comment="科目名称")
    debit = Column(Numeric(18, 2), default=0.0, comment="借方金额")
    credit = Column(Numeric(18, 2), default=0.0, comment="贷方金额")
    dimension = Column(String(500), default="", comment="核算维度")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )