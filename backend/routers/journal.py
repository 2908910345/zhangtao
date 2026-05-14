from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from typing import Optional
import tempfile
import os
from backend.database import get_db, ensure_journal_table, get_existing_journal_table_name, get_journal_table, get_journal_table_name
from backend.models import JournalEntry, BalanceSubject, Book
from backend.schemas import (
    UploadJournalResponse,
    JournalEntryResponse,
    DimensionResponse,
    DimensionItem,
)
from backend.services.parser import parse_journal_streaming

router = APIRouter(prefix="/api", tags=["序时账"])

BATCH_SIZE = 2000


@router.post("/upload/journal", response_model=UploadJournalResponse)
async def upload_journal(
    file: UploadFile = File(...),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="请上传 .xlsx 或 .xls 格式的 Excel 文件")

    tmp_path = None
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # 确保账套的独立序时账表已创建
        await ensure_journal_table(book_name)
        table = get_journal_table(book_name)

        # 删除该账套已有的序时账数据（从对应分表或共享表）
        await db.execute(table.delete().where(table.c.book_name == book_name))
        await db.flush()

        # 流式解析 + 批量插入
        total_count = 0
        subject_map = {}
        voucher_set = set()
        batch = []

        for item in parse_journal_streaming(tmp_path):
            item["book_name"] = book_name
            batch.append(item)
            total_count += 1

            code = item["subject_code"]
            if code not in subject_map:
                subject_map[code] = item.get("subject_name", "")

            vno = item["voucher_no"]
            if vno:
                voucher_set.add(vno)

            if len(batch) >= BATCH_SIZE:
                await db.execute(table.insert(), batch)
                await db.flush()
                batch = []

        # 插入剩余的批次
        if batch:
            await db.execute(table.insert(), batch)
            await db.flush()

        if total_count == 0:
            raise HTTPException(status_code=400, detail="未解析到有效数据，请检查文件内容")

        # 同步科目信息（批量查询已有科目，避免 N+1）
        all_codes = list(subject_map.keys())
        existing_result = await db.execute(
            select(BalanceSubject.code).where(
                BalanceSubject.book_name == book_name,
                BalanceSubject.code.in_(all_codes)
            )
        )
        existing_codes = {row[0] for row in existing_result}

        new_subjects = [
            BalanceSubject(
                book_name=book_name, code=code, name=subject_map[code],
                year_start_debit=0.0, year_start_credit=0.0,
                period_debit=0.0, period_credit=0.0,
                year_total_debit=0.0, year_total_credit=0.0,
                end_debit=0.0, end_credit=0.0, dimension="",
            )
            for code in all_codes
            if code not in existing_codes
        ]
        if new_subjects:
            db.add_all(new_subjects)
            await db.flush()

        # 更新账套元数据
        book_result = await db.execute(select(Book).where(Book.name == book_name).limit(1))
        book = book_result.scalars().first()
        if book:
            book.voucher_count = len(voucher_set)
            subject_cnt = await db.execute(
                text("SELECT COUNT(id) FROM balance_subjects WHERE book_name = :bn"),
                {"bn": book_name}
            )
            book.subject_count = subject_cnt.scalar() or 0
            db.add(book)
            await db.flush()

        return {
            "count": total_count,
            "voucher_count": len(voucher_set),
            "subject_count": len(subject_map),
            "message": f"成功导入 {total_count} 行分录（{len(voucher_set)} 张凭证），同步 {len(subject_map)} 个科目"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def _get_journal_table_for_query(book_name: str):
    """获取用于查询的序时账 Table 对象（优先分表，回退到共享表）"""
    table_name = await get_existing_journal_table_name(book_name)
    if table_name == "journal_entries":
        return JournalEntry.__table__
    return get_journal_table(book_name)


@router.get("/subjects/{code}/journal", response_model=list[JournalEntryResponse])
async def get_subject_journal(
    code: str,
    period: Optional[str] = Query(None),
    voucher_no: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, description="模糊搜索：摘要、科目编码、科目名称"),
    include_children: bool = Query(False, description="都包含子科目的序时账"),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    table = await _get_journal_table_for_query(book_name)
    tc = table.c

    if include_children:
        children = await db.execute(
            select(BalanceSubject.code).distinct().where(
                BalanceSubject.book_name == book_name,
                BalanceSubject.code.like(f"{code}.%")
            )
        )
        child_codes = [row[0] for row in children]
        codes = [code] + child_codes
    else:
        codes = [code]

    conditions = [
        tc.subject_code.in_(codes),
        tc.book_name == book_name
    ]
    if period:
        conditions.append(tc.period == period)
    if voucher_no:
        conditions.append(tc.voucher_no.like(f"%{voucher_no}%"))
    if keyword:
        conditions.append(
            or_(
                tc.summary.like(f"%{keyword}%"),
                tc.subject_code.like(f"%{keyword}%"),
                tc.subject_name.like(f"%{keyword}%"),
            )
        )

    result = await db.execute(
        select(table)
        .where(and_(*conditions))
        .order_by(tc.period, tc.voucher_no)
    )
    entries = result.all()

    if not entries:
        return []

    voucher_pairs = {(e.period, e.voucher_no) for e in entries}

    voucher_conditions = [
        and_(
            tc.book_name == book_name,
            tc.period == p,
            tc.voucher_no == v
        )
        for p, v in voucher_pairs
    ]
    all_result = await db.execute(
        select(table)
        .where(or_(*voucher_conditions))
    )
    all_entries = all_result.all()

    groups = {}
    for e in all_entries:
        key = (e.period, e.voucher_no, e.summary or '')
        if key not in groups:
            groups[key] = []
        groups[key].append(e)

    counterpart_map = {}
    for key, group in groups.items():
        seen = {}
        for e in group:
            if e.subject_code not in seen:
                seen[e.subject_code] = e.subject_name or ''
        for e in group:
            others = []
            for sc, sn in seen.items():
                if sc != e.subject_code:
                    others.append(f"{sn}({sc})" if sc else sn)
            map_key = (e.period, e.voucher_no, e.subject_code, e.summary or '')
            counterpart_map[map_key] = '；'.join(dict.fromkeys(others))

    result_list = []
    for e in entries:
        map_key = (e.period, e.voucher_no, e.subject_code, e.summary or '')
        result_list.append({
            'id': e.id,
            'book_name': e.book_name,
            'created_at': e.created_at.isoformat() if e.created_at else None,
            'org': e.org or '',
            'period': e.period or '',
            'voucher_no': e.voucher_no,
            'summary': e.summary or '',
            'subject_code': e.subject_code,
            'subject_name': e.subject_name or '',
            'debit': e.debit or 0.0,
            'credit': e.credit or 0.0,
            'dimension': e.dimension or '',
            'counterpart': counterpart_map.get(map_key, ''),
        })

    return result_list


@router.get("/voucher/{voucher_no}", response_model=list[JournalEntryResponse])
async def get_voucher_detail(
    voucher_no: str,
    book_name: str = Query("default"),
    period: str = Query(""),
    db: AsyncSession = Depends(get_db)
):
    table = await _get_journal_table_for_query(book_name)
    tc = table.c

    conditions = [
        tc.book_name == book_name,
        tc.voucher_no == voucher_no
    ]
    if period:
        conditions.append(tc.period == period)
    result = await db.execute(
        select(table).where(*conditions).order_by(tc.id)
    )
    entries = result.all()
    return [
        {
            'id': e.id,
            'book_name': e.book_name,
            'created_at': e.created_at.isoformat() if e.created_at else None,
            'org': e.org or '',
            'period': e.period or '',
            'voucher_no': e.voucher_no,
            'summary': e.summary or '',
            'subject_code': e.subject_code,
            'subject_name': e.subject_name or '',
            'debit': e.debit or 0.0,
            'credit': e.credit or 0.0,
            'dimension': e.dimension or '',
            'counterpart': '',
        }
        for e in entries
    ]


def _parse_dimensions(dim_str):
    if not dim_str or not str(dim_str).strip():
        return []
    items = []
    parts = str(dim_str).split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            idx = part.index(':')
            dim_type = part[:idx].strip()
            dim_value = part[idx + 1:].strip()
        else:
            dim_type = part
            dim_value = ''
        if dim_type and dim_value:
            items.append({'type': dim_type, 'value': dim_value})
    return items


@router.get("/subjects/{code}/dimensions", response_model=DimensionResponse)
async def get_subject_dimensions(
    code: str,
    type_filter: Optional[str] = Query(None, alias="type"),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    subject_result = await db.execute(
        select(BalanceSubject).where(
            BalanceSubject.book_name == book_name,
            BalanceSubject.code == code
        ).limit(1)
    )
    subject = subject_result.scalars().first()

    table = await _get_journal_table_for_query(book_name)
    journal_result = await db.execute(
        select(table).where(
            table.c.book_name == book_name,
            table.c.subject_code == code
        )
    )
    journal_entries = journal_result.all()

    dim_set = set()
    dim_items = []
    for entry in journal_entries:
        parsed = _parse_dimensions(entry.dimension)
        for dim in parsed:
            if type_filter and dim['type'] != type_filter:
                continue
            key = (dim['type'], dim['value'])
            if key not in dim_set:
                dim_set.add(key)
                dim_items.append(DimensionItem(type=dim['type'], value=dim['value']))

    name = subject.name if subject else ''
    return DimensionResponse(code=code, name=name, dimensions=dim_items)


@router.get("/subjects/{code}/journal-by-dim", response_model=list[JournalEntryResponse])
async def get_journal_by_dimension(
    code: str,
    dim_type: str = Query(..., alias="type"),
    dim_value: str = Query(...),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    table = await _get_journal_table_for_query(book_name)
    tc = table.c

    result = await db.execute(
        select(table).where(
            and_(
                tc.book_name == book_name,
                tc.subject_code == code,
                tc.dimension.like(f"%{dim_type}%:%{dim_value}%")
            )
        ).order_by(tc.period, tc.voucher_no)
    )
    entries = result.all()
    return [
        {
            'id': e.id,
            'book_name': e.book_name,
            'created_at': e.created_at.isoformat() if e.created_at else None,
            'org': e.org or '',
            'period': e.period or '',
            'voucher_no': e.voucher_no,
            'summary': e.summary or '',
            'subject_code': e.subject_code,
            'subject_name': e.subject_name or '',
            'debit': e.debit or 0.0,
            'credit': e.credit or 0.0,
            'dimension': e.dimension or '',
            'counterpart': '',
        }
        for e in entries
    ]