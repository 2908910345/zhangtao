from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import tempfile
import os
from backend.database import get_db, get_existing_journal_table_name
from backend.models import BalanceSubject, Book
from backend.schemas import (
    UploadBalanceResponse,
    SubjectTreeNode,
    BalanceDetailResponse,
    BalanceListResponse,
    BalanceSubjectResponse,
    Statistics,
)
from backend.services.parser import parse_balance_sheet

router = APIRouter(prefix="/api", tags=["科目余额表"])


@router.post("/upload/balance", response_model=UploadBalanceResponse)
async def upload_balance(
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

        items = parse_balance_sheet(tmp_path)

        if not items:
            raise HTTPException(status_code=400, detail="未解析到有效数据，请检查文件内容")

        db_items = []
        for item in items:
            item["book_name"] = book_name
            db_items.append(BalanceSubject(**item))

        await db.execute(
            BalanceSubject.__table__.delete().where(BalanceSubject.book_name == book_name)
        )
        await db.flush()

        db.add_all(db_items)
        await db.flush()

        book_result = await db.execute(select(Book).where(Book.name == book_name))
        book = book_result.scalar_one_or_none()
        if book:
            book.subject_count = len(db_items)
            db.add(book)
            await db.flush()

        return {"count": len(db_items), "message": f"成功导入 {len(db_items)} 条科目"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败：{str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _make_virtual(code, name):
    return BalanceSubject(
        book_name="", code=code, name=name,
        year_start_debit=0, year_start_credit=0,
        period_debit=0, period_credit=0,
        year_total_debit=0, year_total_credit=0,
        end_debit=0, end_credit=0, dimension="",
    )


def _build_tree(subject, children_map):
    segments = subject.code.split('.')
    node = SubjectTreeNode(
        code=subject.code,
        name=subject.name,
        level=len(segments),
        year_start_debit=subject.year_start_debit,
        year_start_credit=subject.year_start_credit,
        period_debit=subject.period_debit,
        period_credit=subject.period_credit,
        year_total_debit=subject.year_total_debit,
        year_total_credit=subject.year_total_credit,
        end_debit=subject.end_debit,
        end_credit=subject.end_credit,
        children=[],
    )

    if subject.code in children_map:
        for child in children_map[subject.code]:
            child_node = _build_tree(child, children_map)
            node.year_start_debit += child_node.year_start_debit
            node.year_start_credit += child_node.year_start_credit
            node.period_debit += child_node.period_debit
            node.period_credit += child_node.period_credit
            node.year_total_debit += child_node.year_total_debit
            node.year_total_credit += child_node.year_total_credit
            node.end_debit += child_node.end_debit
            node.end_credit += child_node.end_credit
            node.children.append(child_node)

    return node


@router.get("/subjects/tree", response_model=list[SubjectTreeNode])
async def get_subject_tree(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BalanceSubject)
        .where(BalanceSubject.book_name == book_name)
        .order_by(BalanceSubject.code)
    )
    subjects = result.scalars().all()

    code_set = {s.code for s in subjects}
    children_map = {}
    root_subjects = []

    for s in subjects:
        segments = s.code.split('.')
        if len(segments) == 1:
            root_subjects.append(s)
        else:
            parent_code = '.'.join(segments[:-1])
            children_map.setdefault(parent_code, []).append(s)

    orphan_children = {}
    for parent_code, children in children_map.items():
        if parent_code not in code_set:
            orphan_children[parent_code] = children

    for parent_code, children in orphan_children.items():
        first_segment = parent_code.split('.')[0]
        if first_segment in code_set:
            parent_idx = {'parent': parent_code, 'first': first_segment}
            if parent_idx['first'] in {r.code for r in root_subjects}:
                continue
            found = False
            for r in root_subjects:
                if r.code == first_segment:
                    found = True
                    break
            if not found:
                vs = _make_virtual(parent_code, parent_code)
                root_subjects.append(vs)

    return [_build_tree(root, children_map) for root in root_subjects]


@router.get("/subjects/{code}/balance", response_model=BalanceDetailResponse)
async def get_subject_balance(
    code: str,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BalanceSubject).where(
            BalanceSubject.book_name == book_name,
            BalanceSubject.code == code
        )
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail=f"科目 '{code}' 不存在")
    return BalanceDetailResponse(
        code=subject.code,
        name=subject.name,
        year_start_debit=subject.year_start_debit,
        year_start_credit=subject.year_start_credit,
        period_debit=subject.period_debit,
        period_credit=subject.period_credit,
        year_total_debit=subject.year_total_debit,
        year_total_credit=subject.year_total_credit,
        end_debit=subject.end_debit,
        end_credit=subject.end_credit,
        dimension=subject.dimension,
    )


@router.get("/subjects/all", response_model=BalanceListResponse)
async def get_all_subjects(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(BalanceSubject)
        .where(BalanceSubject.book_name == book_name)
        .order_by(BalanceSubject.code)
    )
    subjects = result.scalars().all()
    return BalanceListResponse(
        subjects=subjects,
        total=len(subjects)
    )


@router.get("/statistics", response_model=Statistics)
async def get_statistics(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    subject_count = await db.execute(
        text("SELECT COUNT(id) FROM balance_subjects WHERE book_name = :bn"),
        {"bn": book_name}
    )
    subject_count = subject_count.scalar() or 0

    journal_table_name = await get_existing_journal_table_name(book_name)

    voucher_count = await db.execute(
        text(f"SELECT COUNT(DISTINCT voucher_no) FROM {journal_table_name} WHERE book_name = :bn"),
        {"bn": book_name}
    )
    voucher_count = voucher_count.scalar() or 0

    periods = await db.execute(
        text(f"SELECT DISTINCT period FROM {journal_table_name} WHERE book_name = :bn ORDER BY period"),
        {"bn": book_name}
    )
    period_list = [p[0] for p in periods if p[0]]
    period_range = ''
    if len(period_list) == 1:
        period_range = period_list[0]
    elif len(period_list) > 1:
        period_range = f"{period_list[0]} ~ {period_list[-1]}"

    return Statistics(
        subject_count=subject_count,
        voucher_count=voucher_count,
        period_range=period_range,
    )


@router.delete("/data/clear", response_model=dict)
async def clear_all_data(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        text("DELETE FROM balance_subjects WHERE book_name = :bn"), {"bn": book_name}
    )

    journal_table_name = await get_existing_journal_table_name(book_name)
    await db.execute(
        text(f"DELETE FROM {journal_table_name} WHERE book_name = :bn"), {"bn": book_name}
    )
    await db.flush()
    return {"message": f"账套 '{book_name}' 数据已清除"}