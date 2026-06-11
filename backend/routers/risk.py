"""
风险分析 API 路由
提供 3 个只读风险分析端点：
1. 大额交易凭证查找
2. 跨账套科目余额波动分析
3. 毛利率联动分析
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.services.risk_analyzer import (
    find_large_transactions,
    cross_book_fluctuation,
    gross_margin_analysis,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/risk", tags=["风险分析"])


# ═════════════════════════════════════════════════
# Pydantic 响应模型
# ═════════════════════════════════════════════════


class LargeEntryItem(BaseModel):
    """单条大额分录"""
    id: int = 0
    book_name: str = ''
    org: str = ''
    period: str = ''
    voucher_no: str = ''
    summary: str = ''
    subject_code: str = ''
    subject_name: str = ''
    debit: float = 0.0
    credit: float = 0.0
    dimension: str = ''
    counterpart: str = ''


class LargeVoucherItem(BaseModel):
    """包含大额分录的完整凭证"""
    voucher_no: str = ''
    period: str = ''
    entry_count: int = 0
    total_debit: float = 0.0
    total_credit: float = 0.0
    is_balanced: bool = True
    first_summary: str = ''
    large_entries: list[LargeEntryItem] = []


class LargeTransactionResponse(BaseModel):
    threshold: float = 0.0
    threshold_side: str = 'either'
    total_vouchers: int = 0
    total_entries: int = 0
    page: int = 1
    page_size: int = 50
    items: list[LargeVoucherItem] = []


class FluctuationItem(BaseModel):
    code: str = ''
    name: str = ''
    category: str = ''
    current_balance: float = 0.0
    compare_balance: float = 0.0
    change_amount: float = 0.0
    change_pct: float | None = None
    direction: str = 'flat'
    is_anomaly: bool = False
    risk_level: str = 'normal'
    risk_reason: str = ''


class UnmatchedSubject(BaseModel):
    code: str = ''
    name: str = ''
    reason: str = ''
    current_balance: float = 0.0


class FluctuationSummary(BaseModel):
    total_subjects: int = 0
    matched_subjects: int = 0
    unmatched_subjects: int = 0
    anomaly_count: int = 0
    anomaly_rate: str = '0%'


class FluctuationResponse(BaseModel):
    book_name: str = ''
    compare_book: str = ''
    compare_type: str = 'mom'
    balance_type: str = 'end'
    threshold_pct: float = 30.0
    amount_threshold: float = 0.0
    summary: FluctuationSummary = FluctuationSummary()
    items: list[FluctuationItem] = []
    unmatched: list[UnmatchedSubject] = []
    error: str = ''


class PeriodGrossMargin(BaseModel):
    revenue: float = 0.0
    cost: float = 0.0
    gross_profit: float = 0.0
    gross_margin: float = 0.0
    revenue_subjects: list[str] = []
    cost_subjects: list[str] = []
    error: str = ''


class GrossMarginChange(BaseModel):
    revenue_change_pct: float | None = None
    cost_change_pct: float | None = None
    gross_profit_change_pct: float | None = None
    gross_margin_change_ppt: float = 0.0


class GrossMarginAlert(BaseModel):
    type: str = ''
    severity: str = ''
    message: str = ''


class GrossMarginRiskAssessment(BaseModel):
    has_risk: bool = False
    alerts: list[GrossMarginAlert] = []


class GrossMarginResponse(BaseModel):
    book_name: str = ''
    compare_book: str | None = None
    current: PeriodGrossMargin = PeriodGrossMargin()
    compare: PeriodGrossMargin | None = None
    change: GrossMarginChange | None = None
    risk_assessment: GrossMarginRiskAssessment = GrossMarginRiskAssessment()


# ═════════════════════════════════════════════════
# 1. 大额交易凭证查找
# ═════════════════════════════════════════════════

@router.get("/large-transactions", response_model=LargeTransactionResponse)
async def api_large_transactions(
    threshold: float = Query(..., gt=0, description="单笔分录金额阈值，必须 > 0"),
    threshold_side: str = Query("either", pattern="^(debit|credit|either)$",
                                description="debit=只看借方 / credit=只看贷方 / either=任一方"),
    period: Optional[str] = Query(None, description="限定期间，如 '2024-03'"),
    subject_prefix: Optional[str] = Query(None, description="科目编码前缀，如 '1002' 只看银行存款"),
    min_entries: Optional[int] = Query(None, ge=1, description="凭证最少分录数"),
    max_entries: Optional[int] = Query(None, ge=1, description="凭证最多分录数"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    book_name: str = Query("default", description="目标账套"),
    db: AsyncSession = Depends(get_db),
):
    """查找超过阈值的大额交易，按凭证分组并展示完整借贷明细"""
    result = await find_large_transactions(
        db=db,
        book_name=book_name,
        threshold=threshold,
        threshold_side=threshold_side,
        period=period,
        subject_prefix=subject_prefix,
        min_entries=min_entries,
        max_entries=max_entries,
        page=page,
        page_size=page_size,
    )
    return result


# ═════════════════════════════════════════════════
# 2. 跨账套科目余额波动分析
# ═════════════════════════════════════════════════

@router.get("/balance-fluctuation", response_model=FluctuationResponse)
async def api_balance_fluctuation(
    book_name: str = Query(..., description="当前期间账套"),
    compare_book: str = Query(..., description="对比期间账套"),
    compare_type: str = Query("mom", pattern="^(mom|yoy)$",
                              description="mom=环比 / yoy=同比（仅影响标签）"),
    balance_type: str = Query("end", pattern="^(end|period|year_total)$",
                              description="end=期末余额 / period=本期发生额 / year_total=本年累计"),
    threshold_pct: float = Query(30.0, ge=0, le=1000,
                                 description="波动率阈值百分比，超过此值的标记为异常"),
    amount_threshold: float = Query(0.0, ge=0,
                                     description="变化额绝对阈值，低于此值的波动降级（0 表示不启用）"),
    category: Optional[str] = Query(None, description="按分类筛选（资产/负债/权益/损益）"),
    subject_prefix: Optional[str] = Query(None, description="科目编码前缀"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """跨账套科目余额波动分析（同比/环比）"""
    result = await cross_book_fluctuation(
        db=db,
        book_name=book_name,
        compare_book=compare_book,
        compare_type=compare_type,
        balance_type=balance_type,
        threshold_pct=threshold_pct,
        amount_threshold=amount_threshold,
        category=category,
        subject_prefix=subject_prefix,
        page=page,
        page_size=page_size,
    )
    return result


# ═════════════════════════════════════════════════
# 3. 毛利率联动分析
# ═════════════════════════════════════════════════

@router.get("/gross-margin-analysis", response_model=GrossMarginResponse)
async def api_gross_margin_analysis(
    book_name: str = Query(..., description="当前期间账套"),
    compare_book: Optional[str] = Query(None, description="对比账套（可选，仅返回当期数据）"),
    revenue_subjects: Optional[str] = Query(None, description="收入科目名称，逗号分隔，不传则模板自动匹配"),
    cost_subjects: Optional[str] = Query(None, description="成本科目名称，逗号分隔，不传则模板自动匹配"),
    db: AsyncSession = Depends(get_db),
):
    """收入-成本毛利率联动分析，支持两期对比"""
    rev_list = None
    if revenue_subjects:
        rev_list = [s.strip() for s in revenue_subjects.split(',') if s.strip()]

    cost_list = None
    if cost_subjects:
        cost_list = [s.strip() for s in cost_subjects.split(',') if s.strip()]

    result = await gross_margin_analysis(
        db=db,
        book_name=book_name,
        compare_book=compare_book,
        revenue_subjects=rev_list,
        cost_subjects=cost_list,
    )
    return result
