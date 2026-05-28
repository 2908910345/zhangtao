from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.database import get_db
from backend.models import AdjustmentEntry, BalanceSubject
from backend.schemas import (
    AdjustmentEntryCreate,
    AdjustmentEntryResponse,
    AdjustmentListResponse,
    TrialBalanceRow,
    TrialBalanceResponse,
    DeleteResponse,
)

router = APIRouter(prefix="/api", tags=["审计调整分录"])


@router.get("/adjustments", response_model=AdjustmentListResponse)
async def list_adjustments(
    book_name: str = Query("default"),
    voucher_no: str = Query("", description="按凭证号筛选"),
    db: AsyncSession = Depends(get_db)
):
    query = select(AdjustmentEntry).where(AdjustmentEntry.book_name == book_name)
    if voucher_no:
        query = query.where(AdjustmentEntry.voucher_no == voucher_no)
    query = query.order_by(AdjustmentEntry.id.desc())

    result = await db.execute(query)
    adjustments = result.scalars().all()

    return AdjustmentListResponse(
        entries=list(adjustments),
        total=len(adjustments)
    )


@router.post("/adjustments", response_model=AdjustmentEntryResponse)
async def create_adjustment(
    data: AdjustmentEntryCreate,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    if not data.subject_code:
        raise HTTPException(status_code=400, detail="科目编码不能为空")
    if data.debit <= 0 and data.credit <= 0:
        raise HTTPException(status_code=400, detail="借方或贷方金额必须大于 0")

    entry = AdjustmentEntry(
        book_name=book_name,
        voucher_no=data.voucher_no,
        summary=data.summary,
        subject_code=data.subject_code,
        subject_name=data.subject_name,
        debit=data.debit,
        credit=data.credit,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.put("/adjustments/{entry_id}", response_model=AdjustmentEntryResponse)
async def update_adjustment(
    entry_id: int,
    data: AdjustmentEntryCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AdjustmentEntry).where(AdjustmentEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="调整分录不存在")

    if not data.subject_code:
        raise HTTPException(status_code=400, detail="科目编码不能为空")
    if data.debit <= 0 and data.credit <= 0:
        raise HTTPException(status_code=400, detail="借方或贷方金额必须大于 0")

    entry.voucher_no = data.voucher_no
    entry.summary = data.summary
    entry.subject_code = data.subject_code
    entry.subject_name = data.subject_name
    entry.debit = data.debit
    entry.credit = data.credit

    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.delete("/adjustments/{entry_id}", response_model=DeleteResponse)
async def delete_adjustment(
    entry_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(AdjustmentEntry).where(AdjustmentEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="调整分录不存在")

    await db.delete(entry)
    await db.flush()
    return {"message": "调整分录已删除"}


@router.delete("/adjustments", response_model=DeleteResponse)
async def batch_delete_adjustments(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        AdjustmentEntry.__table__.delete().where(AdjustmentEntry.book_name == book_name)
    )
    await db.flush()
    return {"message": f"账套 '{book_name}' 的所有调整分录已删除"}


@router.delete("/adjustments/clear-book", response_model=DeleteResponse)
async def clear_book_adjustments(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    await db.execute(
        AdjustmentEntry.__table__.delete().where(AdjustmentEntry.book_name == book_name)
    )
    await db.flush()
    return {"message": f"账套 '{book_name}' 的所有调整分录已清除"}


# ========== 试算平衡表 ==========


@router.get(
    "/trial-balance",
    response_model=TrialBalanceResponse,
    tags=["试算平衡表"],
)
async def get_trial_balance(
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db)
):
    # 获取该账套下所有科目
    subjects_result = await db.execute(
        select(BalanceSubject)
        .where(BalanceSubject.book_name == book_name)
        .order_by(BalanceSubject.code)
    )
    subjects = subjects_result.scalars().all()

    # 获取该账套所有调整分录
    adjustments_result = await db.execute(
        select(AdjustmentEntry).where(AdjustmentEntry.book_name == book_name)
    )
    adjustments = adjustments_result.scalars().all()

    # 构建科目编码集合，用于判断是否有子科目
    code_set = {s.code for s in subjects}

    rows = []
    total_unaudited_debit = 0.0
    total_unaudited_credit = 0.0
    total_adjustment_debit = 0.0
    total_adjustment_credit = 0.0
    total_audited_debit = 0.0
    total_audited_credit = 0.0

    for subj in subjects:
        code = subj.code
        # 判断是否有子科目：是否有其他科目编码以该科目编码 + '.' 开头
        has_children = any(other_code != code and other_code.startswith(code + '.') for other_code in code_set)

        level = code.count('.') + 1

        # 未审数
        unaudited_debit = float(subj.end_debit or 0)
        unaudited_credit = float(subj.end_credit or 0)

        # 调整数：仅末级科目直接匹配调整分录，非末级科目汇总子科目
        adj_debit = 0.0
        adj_credit = 0.0
        if not has_children:
            # 末级科目：直接匹配
            for a in adjustments:
                if a.subject_code == code:
                    adj_debit += float(a.debit or 0)
                    adj_credit += float(a.credit or 0)
        # 非末级科目的调整数 = 自身调整 + 子科目调整（已在子科目中计算，此处汇总即可）
        # 但非末级科目的未审数已包含子科目余额，所以调整数也需包含子科目调整
        else:
            for a in adjustments:
                if a.subject_code == code or a.subject_code.startswith(code + '.'):
                    adj_debit += float(a.debit or 0)
                    adj_credit += float(a.credit or 0)

        # 审定数
        audited_debit = unaudited_debit + adj_debit
        audited_credit = unaudited_credit + adj_credit

        total_unaudited_debit += unaudited_debit
        total_unaudited_credit += unaudited_credit
        total_adjustment_debit += adj_debit
        total_adjustment_credit += adj_credit
        total_audited_debit += audited_debit
        total_audited_credit += audited_credit

        rows.append(TrialBalanceRow(
            code=code,
            name=subj.name,
            level=level,
            unaudited_debit=unaudited_debit,
            unaudited_credit=unaudited_credit,
            adjustment_debit=adj_debit,
            adjustment_credit=adj_credit,
            audited_debit=audited_debit,
            audited_credit=audited_credit,
            has_children=has_children,
        ))

    check_ok = abs(total_audited_debit - total_audited_credit) < 0.01

    return TrialBalanceResponse(
        rows=rows,
        total=len(rows),
        check_ok=check_ok,
    )
