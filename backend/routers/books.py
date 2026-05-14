from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from backend.database import get_db, get_journal_table, ensure_journal_table, get_existing_journal_table_name, get_journal_table_name, drop_journal_table
from backend.models import Book, BalanceSubject, JournalEntry
from backend.schemas import BookCreate, BookResponse, BookListResponse, MessageResponse

router = APIRouter(prefix="/api/books", tags=["账套管理"])


def _count_subjects_and_vouchers(subjects_raw, journals_raw):
    subject_count = len(subjects_raw)
    code_set = set()
    for j in journals_raw:
        code_set.add(j['voucher_no'] if isinstance(j, dict) else j.voucher_no)
    voucher_count = len(code_set)
    return subject_count, voucher_count


@router.get("", response_model=BookListResponse)
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).order_by(Book.updated_at.desc()))
    books = result.scalars().all()

    active = await db.execute(select(Book).where(Book.is_active == 1))
    active_book = active.scalar_one_or_none()
    current = active_book.name if active_book else "default"

    if not books:
        default_book = Book(
            name="default",
            description="默认账套",
            subject_count=0,
            voucher_count=0,
            is_active=1,
        )
        db.add(default_book)
        await db.flush()
        await db.refresh(default_book)
        books = [default_book]
        current = "default"

    return BookListResponse(books=books, current=current)


@router.post("", response_model=BookResponse)
async def create_book(data: BookCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Book).where(Book.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"账套 '{data.name}' 已存在")

    book = Book(
        name=data.name,
        description=data.description,
        subject_count=0,
        voucher_count=0,
        is_active=0,
    )
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return book


@router.delete("/{name}", response_model=MessageResponse)
async def delete_book(name: str, db: AsyncSession = Depends(get_db)):
    if name == "default":
        raise HTTPException(status_code=400, detail="默认账套不可删除")

    book_result = await db.execute(select(Book).where(Book.name == name))
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"账套 '{name}' 不存在")

    await db.execute(text("DELETE FROM balance_subjects WHERE book_name = :bn"), {"bn": name})
    await db.execute(text("DELETE FROM books WHERE name = :bn"), {"bn": name})

    # 尝试删除独立序时账分表
    table_name = get_journal_table_name(name)
    try:
        await drop_journal_table(name)
    except Exception:
        pass

    # 同时也清理共享表中的数据
    try:
        await db.execute(text("DELETE FROM journal_entries WHERE book_name = :bn"), {"bn": name})
    except Exception:
        pass

    await db.flush()
    return {"message": f"账套 '{name}' 及其数据已删除"}


@router.post("/save-as", response_model=BookResponse)
async def save_current_as(data: BookCreate, db: AsyncSession = Depends(get_db)):
    from_src = await db.execute(select(Book).where(Book.name == data.name))
    old_book = from_src.scalar_one_or_none()
    if old_book:
        await db.execute(text("DELETE FROM balance_subjects WHERE book_name = :bn"), {"bn": data.name})
        await db.execute(text("DELETE FROM journal_entries WHERE book_name = :bn"), {"bn": data.name})
        await db.execute(text("DELETE FROM books WHERE name = :bn"), {"bn": data.name})
        await db.flush()

    src_subjects = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == "default")
    )
    src_subjects = src_subjects.scalars().all()

    src_journals = await db.execute(
        select(JournalEntry).where(JournalEntry.book_name == "default")
    )
    src_journals = src_journals.scalars().all()

    for s in src_subjects:
        db.add(BalanceSubject(
            book_name=data.name, code=s.code, name=s.name,
            year_start_debit=s.year_start_debit, year_start_credit=s.year_start_credit,
            period_debit=s.period_debit, period_credit=s.period_credit,
            year_total_debit=s.year_total_debit, year_total_credit=s.year_total_credit,
            end_debit=s.end_debit, end_credit=s.end_credit, dimension=s.dimension,
        ))

    # 从源账套的序时账表复制数据（优先分表，其次共享表）
    src_table_name = await get_existing_journal_table_name("default")
    if src_table_name == "journal_entries":
        src_journals = await db.execute(
            select(JournalEntry).where(JournalEntry.book_name == "default")
        )
        src_journals = src_journals.scalars().all()

        for j in src_journals:
            db.add(JournalEntry(
                book_name=data.name, org=j.org, period=j.period,
                voucher_no=j.voucher_no, summary=j.summary,
                subject_code=j.subject_code, subject_name=j.subject_name,
                debit=j.debit, credit=j.credit, dimension=j.dimension,
            ))
    else:
        await ensure_journal_table(data.name)
        dst_table = get_journal_table(data.name)
        src_table = get_journal_table("default")
        src_rows = await db.execute(
            select(src_table).where(src_table.c.book_name == "default")
        )
        rows = src_rows.all()
        if rows:
            batch = []
            for r in rows:
                batch.append({
                    'book_name': data.name,
                    'org': r.org or '',
                    'period': r.period or '',
                    'voucher_no': r.voucher_no,
                    'summary': r.summary or '',
                    'subject_code': r.subject_code,
                    'subject_name': r.subject_name or '',
                    'debit': r.debit or 0.0,
                    'credit': r.credit or 0.0,
                    'dimension': r.dimension or '',
                })
            await db.execute(dst_table.insert(), batch)

    await db.flush()

    book = Book(
        name=data.name, description=data.description,
        subject_count=len(src_subjects),
        voucher_count=len(set(j.voucher_no for j in src_journals)) if src_table_name == "journal_entries" else len(set(r.voucher_no for r in rows)),
    )
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return book


@router.post("/switch/{name}", response_model=MessageResponse)
async def switch_book(name: str, db: AsyncSession = Depends(get_db)):
    book_result = await db.execute(select(Book).where(Book.name == name))
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"账套 '{name}' 不存在")

    await db.execute(text("UPDATE books SET is_active = 0"))
    book.is_active = 1
    db.add(book)
    await db.flush()
    return {"message": f"已切换到账套 '{name}'"}


@router.get("/active")
async def get_active_book(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).where(Book.is_active == 1))
    book = result.scalar_one_or_none()
    if book:
        return {"name": book.name, "description": book.description}
    return {"name": "default", "description": "默认账套"}


@router.post("/save-current", response_model=BookResponse)
async def save_current_book(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    book_result = await db.execute(select(Book).where(Book.name == book_name))
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"账套 '{book_name}' 不存在")

    subject_count_result = await db.execute(
        text("SELECT COUNT(id) FROM balance_subjects WHERE book_name = :bn"),
        {"bn": book_name}
    )
    book.subject_count = subject_count_result.scalar() or 0

    journal_table_name = await get_existing_journal_table_name(book_name)
    voucher_count_result = await db.execute(
        text(f"SELECT COUNT(DISTINCT voucher_no) FROM {journal_table_name} WHERE book_name = :bn"),
        {"bn": book_name}
    )
    book.voucher_count = voucher_count_result.scalar() or 0

    from datetime import datetime
    book.updated_at = datetime.utcnow()
    db.add(book)
    await db.flush()
    await db.refresh(book)

    return book