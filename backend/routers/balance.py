from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
import tempfile
import os
from backend.database import get_db, get_existing_journal_table_name, get_journal_table, escape_like
from backend.models import BalanceSubject, Book, JournalEntry
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


def _parse_dimensions(dim_str):
    """解析维度字符串，返回 [(type, value), ...] 列表"""
    if not dim_str or not str(dim_str).strip():
        return []
    items = []
    parts = str(dim_str).split(';')
    for part in parts:
        part = part.strip()
        if ':' in part:
            dtype, dvalue = part.split(':', 1)
            items.append((dtype.strip(), dvalue.strip()))
    return items


class _MergedSubject:
    """轻量数据容器，避免修改 SQLAlchemy ORM 对象"""
    __slots__ = ('code', 'name', 'year_start_debit', 'year_start_credit',
                 'period_debit', 'period_credit', 'year_total_debit',
                 'year_total_credit', 'end_debit', 'end_credit', 'dimension',
                 'dim_rows')

    def __init__(self, code, name, dimension=""):
        self.code = code
        self.name = name
        self.year_start_debit = 0.0
        self.year_start_credit = 0.0
        self.period_debit = 0.0
        self.period_credit = 0.0
        self.year_total_debit = 0.0
        self.year_total_credit = 0.0
        self.end_debit = 0.0
        self.end_credit = 0.0
        self.dimension = dimension
        self.dim_rows = []  # 维度明细行列表

    @classmethod
    def from_orm(cls, s):
        obj = cls(s.code, s.name, s.dimension or "")
        obj.year_start_debit = s.year_start_debit or 0.0
        obj.year_start_credit = s.year_start_credit or 0.0
        obj.period_debit = s.period_debit or 0.0
        obj.period_credit = s.period_credit or 0.0
        obj.year_total_debit = s.year_total_debit or 0.0
        obj.year_total_credit = s.year_total_credit or 0.0
        obj.end_debit = s.end_debit or 0.0
        obj.end_credit = s.end_credit or 0.0
        return obj


def _merge_subjects(subjects):
    """将同一编码的多条科目记录分组：无维度的汇总行作为主记录，有维度的作为 dim_rows"""
    from collections import OrderedDict
    groups = OrderedDict()
    for s in subjects:
        if s.code not in groups:
            groups[s.code] = _MergedSubject.from_orm(s)
        else:
            existing = groups[s.code]
            if s.dimension:
                # 有维度的行放入 dim_rows
                existing.dim_rows.append(_MergedSubject.from_orm(s))
            else:
                # 无维度的汇总行，更新主记录金额
                existing.year_start_debit += s.year_start_debit or 0.0
                existing.year_start_credit += s.year_start_credit or 0.0
                existing.period_debit += s.period_debit or 0.0
                existing.period_credit += s.period_credit or 0.0
                existing.year_total_debit += s.year_total_debit or 0.0
                existing.year_total_credit += s.year_total_credit or 0.0
                existing.end_debit += s.end_debit or 0.0
                existing.end_credit += s.end_credit or 0.0
    # 注意：如果第一条记录本身有维度（无汇总行），金额已在主记录中无需额外处理
    return list(groups.values())


def _build_tree(subject, children_map):
    segments = subject.code.split('.')
    has_sub_subjects = subject.code in children_map
    has_dims = not has_sub_subjects and len(subject.dim_rows) > 0

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
        has_children=has_sub_subjects or has_dims,
        dimension=subject.dimension or "",
    )

    if has_sub_subjects:
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
    elif has_dims:
        # 末级科目有维度明细行，直接作为子节点
        for dim_row in subject.dim_rows:
            dim_label = dim_row.dimension or ""
            dim_type = ""
            dim_node = SubjectTreeNode(
                code=f"{subject.code}:{dim_row.dimension}",
                name=dim_label,
                level=len(segments) + 1,
                year_start_debit=dim_row.year_start_debit,
                year_start_credit=dim_row.year_start_credit,
                period_debit=dim_row.period_debit,
                period_credit=dim_row.period_credit,
                year_total_debit=dim_row.year_total_debit,
                year_total_credit=dim_row.year_total_credit,
                end_debit=dim_row.end_debit,
                end_credit=dim_row.end_credit,
                is_dimension=True,
                dimension=dim_row.dimension,
            )
            node.children.append(dim_node)

    return node


@router.get("/subjects/tree", response_model=list[SubjectTreeNode])
async def get_subject_tree(
    book_name: str = Query("default"),
    parent_code: str = Query("", description="父级科目编码，空则返回一级科目"),
    db: AsyncSession = Depends(get_db)
):
    if parent_code:
        prefix = parent_code + '.'
        result = await db.execute(
            select(BalanceSubject)
            .where(
                BalanceSubject.book_name == book_name,
                BalanceSubject.code.like(f"{escape_like(prefix)}%", escape="/")
            )
            .order_by(BalanceSubject.code)
        )
        all_subjects = result.scalars().all()

        # 合并同一编码的多条记录
        merged = _merge_subjects(all_subjects)

        children = []
        for s in merged:
            rest = s.code[len(prefix):]
            if '.' not in rest:
                has_sub = any(cs.code.startswith(s.code + '.') for cs in merged)
                has_dims = not has_sub and len(s.dim_rows) > 0
                dim_children = []
                if has_dims:
                    for dim_row in s.dim_rows:
                        dim_label = dim_row.dimension or ""
                        dim_children.append(SubjectTreeNode(
                            code=f"{s.code}:{dim_row.dimension}",
                            name=dim_label,
                            level=s.code.count('.') + 2,
                            year_start_debit=dim_row.year_start_debit,
                            year_start_credit=dim_row.year_start_credit,
                            period_debit=dim_row.period_debit,
                            period_credit=dim_row.period_credit,
                            year_total_debit=dim_row.year_total_debit,
                            year_total_credit=dim_row.year_total_credit,
                            end_debit=dim_row.end_debit,
                            end_credit=dim_row.end_credit,
                            is_dimension=True,
                            dimension=dim_row.dimension,
                        ))
                children.append(SubjectTreeNode(
                    code=s.code, name=s.name,
                    level=s.code.count('.') + 1,
                    year_start_debit=s.year_start_debit,
                    year_start_credit=s.year_start_credit,
                    period_debit=s.period_debit,
                    period_credit=s.period_credit,
                    year_total_debit=s.year_total_debit,
                    year_total_credit=s.year_total_credit,
                    end_debit=s.end_debit,
                    end_credit=s.end_credit,
                    children=dim_children,
                    has_children=has_sub or has_dims,
                    dimension=s.dimension or "",
                ))
        return children

    result = await db.execute(
        select(BalanceSubject)
        .where(BalanceSubject.book_name == book_name)
        .order_by(BalanceSubject.code)
    )
    subjects = result.scalars().all()

    # 先合并同一编码的多条记录（不同维度）
    merged = _merge_subjects(subjects)

    # 构建 children_map：父编码 -> [子科目列表]
    children_map = {}
    for s in merged:
        parts = s.code.split('.')
        if len(parts) > 1:
            parent_code = '.'.join(parts[:-1])
            if parent_code not in children_map:
                children_map[parent_code] = []
            children_map[parent_code].append(s)

    # 找出一级科目，用 _build_tree 递归构建完整嵌套树
    root_subjects = [s for s in merged if '.' not in s.code]

    return [_build_tree(s, children_map) for s in root_subjects]


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


@router.get("/subjects/search", response_model=BalanceListResponse)
async def search_subjects(
    keyword: str = Query(""),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    if not keyword or len(keyword) < 1:
        return BalanceListResponse(subjects=[], total=0)
    result = await db.execute(
        select(BalanceSubject)
        .where(
            BalanceSubject.book_name == book_name,
            or_(
                BalanceSubject.code.like(f"%{escape_like(keyword)}%", escape="/"),
                BalanceSubject.name.like(f"%{escape_like(keyword)}%", escape="/"),
            )
        )
        .order_by(BalanceSubject.code)
        .limit(30)
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
    book_result = await db.execute(select(Book).where(Book.name == book_name))
    book = book_result.scalar_one_or_none()

    if book and book.subject_count > 0:
        period_range = ''
        journal_table_name = await get_existing_journal_table_name(book_name)
        journal_table = get_journal_table(book_name) if journal_table_name != "journal_entries" else JournalEntry.__table__
        tc = journal_table.c
        periods_result = await db.execute(
            select(tc.period).where(tc.book_name == book_name, tc.period != '').distinct().order_by(tc.period)
        )
        period_list = [p[0] for p in periods_result if p[0]]
        if len(period_list) == 1:
            period_range = period_list[0]
        elif len(period_list) > 1:
            period_range = f"{period_list[0]} ~ {period_list[-1]}"

        return Statistics(
            subject_count=book.subject_count,
            voucher_count=book.voucher_count,
            period_range=period_range,
        )

    subject_count_result = await db.execute(
        select(func.count(BalanceSubject.id)).where(BalanceSubject.book_name == book_name)
    )
    subject_count = subject_count_result.scalar() or 0

    journal_table_name = await get_existing_journal_table_name(book_name)
    journal_table = get_journal_table(book_name) if journal_table_name != "journal_entries" else JournalEntry.__table__
    tc = journal_table.c

    voucher_count_result = await db.execute(
        select(func.count(tc.voucher_no.distinct())).where(tc.book_name == book_name)
    )
    voucher_count = voucher_count_result.scalar() or 0

    periods_result = await db.execute(
        select(tc.period).where(tc.book_name == book_name, tc.period != '').distinct().order_by(tc.period)
    )
    period_list = [p[0] for p in periods_result if p[0]]
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
        BalanceSubject.__table__.delete().where(BalanceSubject.book_name == book_name)
    )

    journal_table_name = await get_existing_journal_table_name(book_name)
    journal_table = get_journal_table(book_name) if journal_table_name != "journal_entries" else JournalEntry.__table__
    await db.execute(
        journal_table.delete().where(journal_table.c.book_name == book_name)
    )
    await db.flush()
    return {"message": f"账套 '{book_name}' 数据已清除"}