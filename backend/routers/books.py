from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi.responses import StreamingResponse
from io import BytesIO
import json
from urllib.parse import quote
from backend.database import get_db, get_journal_table, ensure_journal_table, get_existing_journal_table_name, get_journal_table_name, drop_journal_table, async_session_factory
from backend.models import Book, BalanceSubject, JournalEntry, AdjustmentEntry
from backend.schemas import BookCreate, BookResponse, BookListResponse, MessageResponse

router = APIRouter(prefix="/api/books", tags=["账套管理"])


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


@router.get("/{name}/backup")
async def backup_book(name: str):
    async with async_session_factory() as session:
        book_result = await session.execute(select(Book).where(Book.name == name))
        book = book_result.scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=404, detail=f"账套 '{name}' 不存在")

        subjects_result = await session.execute(
            select(BalanceSubject).where(BalanceSubject.book_name == name)
        )
        subjects = subjects_result.scalars().all()

        journal_table_name = await get_existing_journal_table_name(name)
        journal_table = get_journal_table(name) if journal_table_name != "journal_entries" else JournalEntry.__table__
        journals_result = await session.execute(
            select(journal_table).where(journal_table.c.book_name == name)
        )
        journal_rows = journals_result.all()

        journal_data = []
        for r in journal_rows:
            journal_data.append({
                'org': r.org or '',
                'period': r.period or '',
                'voucher_no': r.voucher_no,
                'summary': r.summary or '',
                'subject_code': r.subject_code,
                'subject_name': r.subject_name or '',
                'debit': float(r.debit or 0),
                'credit': float(r.credit or 0),
                'dimension': r.dimension or '',
            })

        backup_data = {
            'version': 1,
            'book': {
                'name': book.name,
                'description': book.description or '',
            },
            'subjects': [
                {
                    'code': s.code, 'name': s.name,
                    'year_start_debit': float(s.year_start_debit or 0),
                    'year_start_credit': float(s.year_start_credit or 0),
                    'period_debit': float(s.period_debit or 0),
                    'period_credit': float(s.period_credit or 0),
                    'year_total_debit': float(s.year_total_debit or 0),
                    'year_total_credit': float(s.year_total_credit or 0),
                    'end_debit': float(s.end_debit or 0),
                    'end_credit': float(s.end_credit or 0),
                    'dimension': s.dimension or '',
                }
                for s in subjects
            ],
            'journals': journal_data,
        }

        json_bytes = json.dumps(backup_data, ensure_ascii=False, indent=2).encode('utf-8')
        stream = BytesIO(json_bytes)
        encoded_name = quote(f"{name}_backup.json")

        return StreamingResponse(
            stream,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            }
        )


@router.post("/restore", response_model=BookResponse)
async def restore_book(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename or not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="请上传 .json 格式的备份文件")

    try:
        content = await file.read()
        backup_data = json.loads(content.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"备份文件格式错误：{str(e)}")

    if 'book' not in backup_data or 'version' not in backup_data:
        raise HTTPException(status_code=400, detail="无效的备份文件格式")

    book_info = backup_data['book']
    book_name = book_info['name']

    existing = await db.execute(select(Book).where(Book.name == book_name))
    old_book = existing.scalar_one_or_none()
    if old_book:
        await db.execute(BalanceSubject.__table__.delete().where(BalanceSubject.book_name == book_name))
        await db.execute(JournalEntry.__table__.delete().where(JournalEntry.book_name == book_name))
        await db.execute(AdjustmentEntry.__table__.delete().where(AdjustmentEntry.book_name == book_name))
        # 也删除分账套动态表中的数据
        existing_table_name = await get_existing_journal_table_name(book_name)
        if existing_table_name:
            journal_table = get_journal_table(book_name)
            await db.execute(journal_table.delete().where(journal_table.c.book_name == book_name))
        await db.execute(Book.__table__.delete().where(Book.name == book_name))
        await db.flush()

    for s in backup_data.get('subjects', []):
        db.add(BalanceSubject(
            book_name=book_name, code=s['code'], name=s['name'],
            year_start_debit=s.get('year_start_debit', 0),
            year_start_credit=s.get('year_start_credit', 0),
            period_debit=s.get('period_debit', 0),
            period_credit=s.get('period_credit', 0),
            year_total_debit=s.get('year_total_debit', 0),
            year_total_credit=s.get('year_total_credit', 0),
            end_debit=s.get('end_debit', 0),
            end_credit=s.get('end_credit', 0),
            dimension=s.get('dimension', ''),
        ))

    journals = backup_data.get('journals', [])
    if journals:
        await ensure_journal_table(book_name)
        journal_table = get_journal_table(book_name)
        batch = []
        for j in journals:
            batch.append({
                'book_name': book_name,
                'org': j.get('org', ''),
                'period': j.get('period', ''),
                'voucher_no': j['voucher_no'],
                'summary': j.get('summary', ''),
                'subject_code': j['subject_code'],
                'subject_name': j.get('subject_name', ''),
                'debit': j.get('debit', 0),
                'credit': j.get('credit', 0),
                'dimension': j.get('dimension', ''),
            })
        await db.execute(journal_table.insert(), batch)

    await db.flush()

    book = Book(
        name=book_name,
        description=book_info.get('description', ''),
        subject_count=len(backup_data.get('subjects', [])),
        voucher_count=len(set(j['voucher_no'] for j in journals if j.get('voucher_no'))),
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

    await db.execute(BalanceSubject.__table__.delete().where(BalanceSubject.book_name == name))
    await db.execute(AdjustmentEntry.__table__.delete().where(AdjustmentEntry.book_name == name))
    await db.execute(Book.__table__.delete().where(Book.name == name))

    # 尝试删除独立序时账分表
    table_name = get_journal_table_name(name)
    try:
        await drop_journal_table(name)
    except Exception:
        pass

    # 同时也清理共享表中的数据
    try:
        await db.execute(JournalEntry.__table__.delete().where(JournalEntry.book_name == name))
    except Exception:
        pass

    await db.flush()
    return {"message": f"账套 '{name}' 及其数据已删除"}


@router.post("/save-as", response_model=BookResponse)
async def save_current_as(data: BookCreate, db: AsyncSession = Depends(get_db)):
    active_result = await db.execute(select(Book).where(Book.is_active == 1))
    active_book = active_result.scalar_one_or_none()
    source_name = active_book.name if active_book else "default"

    from_src = await db.execute(select(Book).where(Book.name == data.name))
    old_book = from_src.scalar_one_or_none()
    if old_book:
        await db.execute(BalanceSubject.__table__.delete().where(BalanceSubject.book_name == data.name))
        await db.execute(JournalEntry.__table__.delete().where(JournalEntry.book_name == data.name))
        await db.execute(Book.__table__.delete().where(Book.name == data.name))
        await db.flush()

    src_subjects = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == source_name)
    )
    src_subjects = src_subjects.scalars().all()

    for s in src_subjects:
        db.add(BalanceSubject(
            book_name=data.name, code=s.code, name=s.name,
            year_start_debit=s.year_start_debit, year_start_credit=s.year_start_credit,
            period_debit=s.period_debit, period_credit=s.period_credit,
            year_total_debit=s.year_total_debit, year_total_credit=s.year_total_credit,
            end_debit=s.end_debit, end_credit=s.end_credit, dimension=s.dimension,
        ))

    src_table_name = await get_existing_journal_table_name(source_name)
    src_voucher_count = 0
    if src_table_name == "journal_entries":
        src_journals = await db.execute(
            select(JournalEntry).where(JournalEntry.book_name == source_name)
        )
        src_journals = src_journals.scalars().all()

        for j in src_journals:
            db.add(JournalEntry(
                book_name=data.name, org=j.org, period=j.period,
                voucher_no=j.voucher_no, summary=j.summary,
                subject_code=j.subject_code, subject_name=j.subject_name,
                debit=j.debit, credit=j.credit, dimension=j.dimension,
            ))
        src_voucher_count = len(set(j.voucher_no for j in src_journals))
    else:
        await ensure_journal_table(data.name)
        dst_table = get_journal_table(data.name)
        src_table = get_journal_table(source_name)
        src_rows = await db.execute(
            select(src_table).where(src_table.c.book_name == source_name)
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
        src_voucher_count = len(set(r.voucher_no for r in rows)) if rows else 0

    await db.flush()

    book = Book(
        name=data.name, description=data.description,
        subject_count=len(src_subjects),
        voucher_count=src_voucher_count,
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

    await db.execute(Book.__table__.update().values(is_active=0))
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
        select(func.count(BalanceSubject.id)).where(BalanceSubject.book_name == book_name)
    )
    book.subject_count = subject_count_result.scalar() or 0

    journal_table_name = await get_existing_journal_table_name(book_name)
    journal_table = get_journal_table(book_name) if journal_table_name != "journal_entries" else JournalEntry.__table__
    voucher_count_result = await db.execute(
        select(func.count(journal_table.c.voucher_no.distinct())).where(journal_table.c.book_name == book_name)
    )
    book.voucher_count = voucher_count_result.scalar() or 0

    from datetime import datetime, timezone
    book.updated_at = datetime.now(timezone.utc)
    db.add(book)
    await db.flush()
    await db.refresh(book)

    return book