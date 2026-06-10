import re
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Table, Column, Integer, String, Numeric, DateTime, MetaData, func, Index
from sqlalchemy import inspect
from pydantic_settings import BaseSettings
import os


def escape_like(s: str, escape_char: str = "/") -> str:
    """转义 LIKE 模式中的特殊通配符 _ 和 %，防止科目编码含这些字符时匹配错误。
    用法: column.like(f"{escape_like(prefix)}%", escape="/")
    """
    result = s.replace(escape_char, escape_char + escape_char)
    result = result.replace("%", escape_char + "%")
    result = result.replace("_", escape_char + "_")
    return result


class Settings(BaseSettings):
    db_type: str = "sqlite"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root"
    db_name: str = "accounting_system"

    @property
    def database_url(self) -> str:
        if self.db_type == "mysql":
            return f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "backend", "data")
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "accounting.db")
        return f"sqlite+aiosqlite:///{db_path}"

    model_config = {"env_prefix": "ACCT_", "env_file": ".env"}


settings = Settings()

_engine_kwargs = {"echo": False}
if settings.db_type == "mysql":
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── 动态分表管理（按账套创建独立序时账表） ──

_journal_metadata = MetaData()


def sanitize_table_name(name: str) -> str:
    """将账套名称转为安全的表名"""
    name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '_', name)
    if not name or name[0].isdigit():
        name = f"book_{name}"
    return name


def get_journal_table_name(book_name: str) -> str:
    """获取账套对应的序时账表名"""
    safe = sanitize_table_name(book_name)
    return f"journal_{safe}"


def _build_journal_table(table_name: str) -> Table:
    """构建序时账表定义"""
    return Table(
        table_name, _journal_metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('book_name', String(200), nullable=False),
        Column('org', String(100), default=''),
        Column('period', String(50), default=''),
        Column('voucher_no', String(50), nullable=False, index=True),
        Column('summary', String(500), default=''),
        Column('subject_code', String(50), nullable=False, index=True),
        Column('subject_name', String(200), default=''),
        Column('debit', Numeric(18, 2), default=0.0),
        Column('credit', Numeric(18, 2), default=0.0),
        Column('dimension', String(500), default=''),
        Column('created_at', DateTime, server_default=func.now()),
        Index(f'ix_{table_name}_debit', 'book_name', 'debit'),
        Index(f'ix_{table_name}_credit', 'book_name', 'credit'),
        extend_existing=True,
    )


def get_journal_table(book_name: str) -> Table:
    """获取账套对应的序时账 Table 对象"""
    table_name = get_journal_table_name(book_name)
    if table_name in _journal_metadata.tables:
        return _journal_metadata.tables[table_name]
    return _build_journal_table(table_name)


async def ensure_journal_table(book_name: str):
    """确保账套的序时账表已创建"""
    table = get_journal_table(book_name)
    async with engine.begin() as conn:
        await conn.run_sync(table.create, checkfirst=True)


async def get_existing_journal_table_name(book_name: str) -> str:
    """获取账套当前使用的序时账表名（分表优先，其次回退到共享表）"""
    per_book = get_journal_table_name(book_name)
    async with engine.connect() as conn:
        exists = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(per_book)
        )
    if exists:
        return per_book
    return "journal_entries"


async def drop_journal_table(book_name: str):
    """删除账套的独立序时账表"""
    table_name = get_journal_table_name(book_name)
    async with engine.connect() as conn:
        exists = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(table_name)
        )
        if exists:
            table = get_journal_table(book_name)
            await conn.run_sync(table.drop)
    _journal_metadata.tables.pop(table_name, None)