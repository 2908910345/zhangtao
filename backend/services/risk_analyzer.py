"""
风险分析引擎
基于序时账和科目余额表进行审计风险分析：
1. 大额交易凭证查找 — 按阈值筛选并穿透完整凭证
2. 科目余额波动分析（跨账套同比/环比）
3. 毛利率联动分析
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from backend.database import (
    get_journal_table, get_existing_journal_table_name,
    escape_like,
)
from backend.models import BalanceSubject, JournalEntry
from backend.services.template_defs import DRAFT_TEMPLATES


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════


async def _get_journal_table_for_query(book_name: str, db: AsyncSession):
    """获取账套对应的序时账 Table 对象（分表优先，共享表回退）"""
    table_name = await get_existing_journal_table_name(book_name)
    if table_name == "journal_entries":
        return JournalEntry.__table__
    return get_journal_table(book_name)


def _build_name_code_map(subjects):
    """建立科目名称→一级编码映射（与 draft.py 逻辑一致）"""
    name_map = {}
    for s in subjects:
        if '.' not in s.code:
            name_map[s.name] = s.code
    for s in subjects:
        if '.' in s.code:
            l1_code = s.code.split('.')[0]
            for nm, code in list(name_map.items()):
                if code == l1_code:
                    if nm not in name_map:
                        name_map[nm] = l1_code
                    break
    return name_map


def _get_category_map() -> dict[str, str]:
    """建立科目名称→分类的映射（资产/负债/权益/损益）"""
    name_cat = {}
    for tpl in DRAFT_TEMPLATES.values():
        cat = tpl.get('category', '')
        for sn in tpl.get('subject_names', []):
            name_cat[sn] = cat
    return name_cat


def _normalize_balance(debit: float, credit: float,
                       balance_type: str, category: str) -> float:
    """
    归一化余额。
    - 资产/成本类: 借方为正 (debit - credit)
    - 负债/权益/损益类: 贷方为正 (credit - debit)
    balance_type: 'end' | 'period' | 'year_total'
    """
    if category in ('负债', '权益', '损益'):
        return round(credit - debit, 2)
    return round(debit - credit, 2)


def _calc_change(current: float, compare: float):
    """计算变化额、变化率、方向"""
    change_amount = round(current - compare, 2)
    if compare == 0:
        if current == 0:
            return change_amount, 0.0, 'flat'
        return change_amount, None, 'increase'
    change_pct = round(change_amount / abs(compare) * 100, 2)
    direction = 'increase' if change_pct > 0 else ('decrease' if change_pct < 0 else 'flat')
    return change_amount, change_pct, direction


def _risk_level(change_pct: float | None) -> tuple[str, str]:
    """根据波动率返回 (风险等级, 理由)"""
    if change_pct is None:
        return 'critical', '新增科目（对比期为 0）'
    abs_pct = abs(change_pct)
    if abs_pct > 100:
        return 'critical', f'波动 {change_pct:+.2f}%，超过 100%'
    elif abs_pct > 50:
        return 'high', f'波动 {change_pct:+.2f}%，超过 50%'
    elif abs_pct > 30:
        return 'medium', f'波动 {change_pct:+.2f}%，超过 30%'
    return 'normal', ''


def _serialize_entry(e, counterpart: str = '') -> dict:
    """序列化单条序时账分录"""
    return {
        'id': getattr(e, 'id', 0),
        'book_name': getattr(e, 'book_name', ''),
        'org': getattr(e, 'org', '') or '',
        'period': getattr(e, 'period', '') or '',
        'voucher_no': getattr(e, 'voucher_no', ''),
        'summary': getattr(e, 'summary', '') or '',
        'subject_code': getattr(e, 'subject_code', ''),
        'subject_name': getattr(e, 'subject_name', '') or '',
        'debit': float(getattr(e, 'debit', 0) or 0),
        'credit': float(getattr(e, 'credit', 0) or 0),
        'dimension': getattr(e, 'dimension', '') or '',
        'counterpart': counterpart,
    }


def _group_subjects_by_code(subjects: list) -> dict:
    """按 code 分组科目，正确处理维度行。

    规则（与 draft.py 一致）：
    - 如果同编码有汇总行（dimension=""），只取汇总行的金额
    - 如果只有维度行（dimension 不为空），累加所有维度行的金额
    - 返回 {code: {name, debit, credit, ...}}
    """
    from collections import OrderedDict

    # 第一步：按 code 分组，区分汇总行和维度行
    raw_groups = OrderedDict()
    for s in subjects:
        code = s.code
        if code not in raw_groups:
            raw_groups[code] = {'summary': None, 'dim_rows': []}
        entry = {
            'year_start_debit': float(s.year_start_debit or 0),
            'year_start_credit': float(s.year_start_credit or 0),
            'period_debit': float(s.period_debit or 0),
            'period_credit': float(s.period_credit or 0),
            'year_total_debit': float(s.year_total_debit or 0),
            'year_total_credit': float(s.year_total_credit or 0),
            'end_debit': float(s.end_debit or 0),
            'end_credit': float(s.end_credit or 0),
            'name': s.name,
        }
        if s.dimension:
            raw_groups[code]['dim_rows'].append(entry)
        else:
            raw_groups[code]['summary'] = entry

    # 第二步：合并
    result = {}
    for code, rg in raw_groups.items():
        name = rg['summary']['name'] if rg['summary'] else (rg['dim_rows'][0]['name'] if rg['dim_rows'] else '')

        g = {
            'code': code,
            'name': name,
            'year_start_debit': 0.0,
            'year_start_credit': 0.0,
            'period_debit': 0.0,
            'period_credit': 0.0,
            'year_total_debit': 0.0,
            'year_total_credit': 0.0,
            'end_debit': 0.0,
            'end_credit': 0.0,
        }

        if rg['summary']:
            # 有汇总行：只用汇总行
            for key in g:
                if key in ('code', 'name'):
                    continue
                g[key] = rg['summary'][key]
        else:
            # 无汇总行：累加所有维度行
            for entry in rg['dim_rows']:
                for key in g:
                    if key in ('code', 'name'):
                        continue
                    g[key] += entry[key]

        result[code] = g
    return result


# ═══════════════════════════════════════════
# 1. 大额交易凭证查找
# ═══════════════════════════════════════════


async def find_large_transactions(
    db: AsyncSession,
    book_name: str,
    threshold: float,
    threshold_side: str = 'either',
    period: Optional[str] = None,
    subject_prefix: Optional[str] = None,
    min_entries: Optional[int] = None,
    max_entries: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    找大额分录 → 按凭证分组 → 反查完整凭证 → 计算对方科目 → 返回。

    SQL 策略（MySQL）：
    - threshold_side=either → 两个 SELECT 各自走 (book_name, debit) 和 (book_name, credit) 索引，UNION 去重
    - threshold_side=debit/credit → 单条件走对应索引
    """
    # --- 获取序时账表 ---
    try:
        table = await _get_journal_table_for_query(book_name, db)
        tc = table.c
    except Exception:
        return _empty_large_response(threshold, threshold_side, page, page_size)

    # --- 先查大额分录（仅 id + voucher_no + period 够分组即可） ---
    # 用 UNION 策略避免 OR 索引失效
    base_conditions_debit = [tc.book_name == book_name]
    base_conditions_credit = [tc.book_name == book_name]
    if period:
        base_conditions_debit.append(tc.period == period)
        base_conditions_credit.append(tc.period == period)
    if subject_prefix:
        like_pattern = f"{escape_like(subject_prefix)}%"
        base_conditions_debit.append(tc.subject_code.like(like_pattern, escape="/"))
        base_conditions_credit.append(tc.subject_code.like(like_pattern, escape="/"))

    slim_cols = [tc.id, tc.voucher_no, tc.period, tc.subject_code, tc.debit, tc.credit]

    if threshold_side == 'debit':
        q = select(*slim_cols).where(and_(tc.debit >= threshold, *base_conditions_debit))
    elif threshold_side == 'credit':
        q = select(*slim_cols).where(and_(tc.credit >= threshold, *base_conditions_credit))
    else:
        q_debit = select(*slim_cols).where(and_(tc.debit >= threshold, *base_conditions_debit))
        q_credit = select(*slim_cols).where(and_(tc.credit >= threshold, *base_conditions_credit))
        q = q_debit.union(q_credit)

    q = q.order_by(tc.period, tc.voucher_no)
    offset = (page - 1) * page_size
    q = q.limit(page_size).offset(offset)

    result = await db.execute(q)
    large_rows = result.all()

    if not large_rows:
        return _empty_large_response(threshold, threshold_side, page, page_size)

    # --- 收集凭证 key 和大额分录 id ---
    voucher_keys = {}   # (period, voucher_no) → {'large_ids': set(), 'summary': ''}
    for r in large_rows:
        key = (r.period, r.voucher_no)
        if key not in voucher_keys:
            voucher_keys[key] = {'large_ids': set(), 'summary': ''}
        voucher_keys[key]['large_ids'].add(r.id)
        if hasattr(r, 'summary') and r.summary and not voucher_keys[key]['summary']:
            voucher_keys[key]['summary'] = r.summary

    # --- 拉取完整凭证分录 ---
    full_vouchers = []
    for (period_key, vno), meta in voucher_keys.items():
        conds = [
            tc.book_name == book_name,
            tc.period == period_key,
            tc.voucher_no == vno,
        ]
        ve = await db.execute(
            select(table).where(and_(*conds)).order_by(tc.id)
        )
        entries = ve.all()

        # 按 min_entries / max_entries 过滤
        if min_entries is not None and len(entries) < min_entries:
            continue
        if max_entries is not None and len(entries) > max_entries:
            continue

        # --- 对方科目计算（同一张凭证内） ---
        groups = {}
        for e in entries:
            gkey = (e.period, e.voucher_no, e.summary or '')
            if gkey not in groups:
                groups[gkey] = []
            groups[gkey].append(e)

        counterpart_map = {}
        for gkey, g in groups.items():
            seen = {}
            for e in g:
                if e.subject_code not in seen:
                    seen[e.subject_code] = e.subject_name or ''
            for e in g:
                others = []
                for sc, sn in seen.items():
                    if sc != e.subject_code:
                        others.append(f"{sn}({sc})")
                cmap_key = (e.period, e.voucher_no, e.subject_code, e.summary or '')
                counterpart_map[cmap_key] = '；'.join(dict.fromkeys(others))

        total_debit = sum(float(e.debit or 0) for e in entries)
        total_credit = sum(float(e.credit or 0) for e in entries)
        is_balanced = abs(total_debit - total_credit) < 0.01

        first_summary = ''
        for e in entries:
            if e.summary:
                first_summary = e.summary
                break

        large_entries_list = []
        for e in entries:
            if e.id in meta['large_ids']:
                cmap_key = (e.period, e.voucher_no, e.subject_code, e.summary or '')
                large_entries_list.append(_serialize_entry(
                    e, counterpart_map.get(cmap_key, '')
                ))

        full_vouchers.append({
            'voucher_no': vno,
            'period': period_key,
            'entry_count': len(entries),
            'total_debit': round(total_debit, 2),
            'total_credit': round(total_credit, 2),
            'is_balanced': is_balanced,
            'first_summary': first_summary,
            'large_entries': large_entries_list,
        })

    # --- 总计数（对凭证去重） ---
    total_vouchers = len(full_vouchers)

    return {
        'threshold': threshold,
        'threshold_side': threshold_side,
        'total_vouchers': total_vouchers,
        'total_entries': sum(v['entry_count'] for v in full_vouchers),
        'page': page,
        'page_size': page_size,
        'items': full_vouchers,
    }


def _empty_large_response(threshold: float, threshold_side: str, page: int, page_size: int) -> dict:
    return {
        'threshold': threshold,
        'threshold_side': threshold_side,
        'total_vouchers': 0,
        'total_entries': 0,
        'page': page,
        'page_size': page_size,
        'items': [],
    }


# ═══════════════════════════════════════════
# 2. 跨账套科目余额波动分析
# ═══════════════════════════════════════════


async def cross_book_fluctuation(
    db: AsyncSession,
    book_name: str,
    compare_book: str,
    compare_type: str = 'mom',
    balance_type: str = 'end',
    threshold_pct: float = 30.0,
    category: Optional[str] = None,
    subject_prefix: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    跨账套对比分析。
    两个账套的科目按 code 匹配，计算余额波动率，标记异常。
    """
    # --- 读两账套数据 ---
    cur_r = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
    )
    cur_all = cur_r.scalars().all()
    if not cur_all:
        return _error_fluctuation_response(book_name, compare_book, compare_type,
                                           balance_type, threshold_pct,
                                           f'账套 "{book_name}" 没有科目数据')

    cmp_r = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == compare_book)
    )
    cmp_all = cmp_r.scalars().all()
    if not cmp_all:
        return _error_fluctuation_response(book_name, compare_book, compare_type,
                                           balance_type, threshold_pct,
                                           f'对比账套 "{compare_book}" 没有科目数据')

    cur_groups = _group_subjects_by_code(cur_all)
    cmp_groups = _group_subjects_by_code(cmp_all)

    name_category_map = _get_category_map()

    codes_cur = set(cur_groups.keys())
    codes_cmp = set(cmp_groups.keys())
    common = codes_cur & codes_cmp

    # --- 波动计算 ---
    items = []
    for code in common:
        cur_g = cur_groups[code]
        cmp_g = cmp_groups[code]
        name = cur_g['name']
        cat = name_category_map.get(name, '')

        if category and cat != category:
            continue
        if subject_prefix and not code.startswith(subject_prefix):
            continue

        # 按 balance_type 选取字段
        cur_bal = _normalize_balance(cur_g[f'{balance_type}_debit'],
                                     cur_g[f'{balance_type}_credit'], balance_type, cat)
        cmp_bal = _normalize_balance(cmp_g[f'{balance_type}_debit'],
                                     cmp_g[f'{balance_type}_credit'], balance_type, cat)

        chg_amt, chg_pct, direction = _calc_change(cur_bal, cmp_bal)
        level, reason = _risk_level(chg_pct)

        items.append({
            'code': code,
            'name': name,
            'category': cat,
            'current_balance': cur_bal,
            'compare_balance': cmp_bal,
            'change_amount': chg_amt,
            'change_pct': chg_pct,
            'direction': direction,
            'is_anomaly': level != 'normal',
            'risk_level': level,
            'risk_reason': reason,
        })

    items.sort(key=lambda x: -(abs(x['change_pct']) if x['change_pct'] is not None else float('inf')))

    # --- 未匹配科目（当前账套独有） ---
    unmatched = []
    for code in sorted(codes_cur - codes_cmp):
        if subject_prefix and not code.startswith(subject_prefix):
            continue
        g = cur_groups[code]
        bal = _normalize_balance(g[f'{balance_type}_debit'],
                                 g[f'{balance_type}_credit'], balance_type,
                                 name_category_map.get(g['name'], ''))
        unmatched.append({
            'code': code,
            'name': g['name'],
            'reason': '对比账套中不存在此科目',
            'current_balance': bal,
        })

    # 分页
    total = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset:offset + page_size]

    anomaly_count = sum(1 for it in items if it['is_anomaly'])

    return {
        'book_name': book_name,
        'compare_book': compare_book,
        'compare_type': compare_type,
        'balance_type': balance_type,
        'threshold_pct': threshold_pct,
        'summary': {
            'total_subjects': len(cur_all),
            'matched_subjects': len(common),
            'unmatched_subjects': len(codes_cur - codes_cmp),
            'anomaly_count': anomaly_count,
            'anomaly_rate': f"{round(anomaly_count / len(common) * 100, 1)}%" if common else "0%",
        },
        'items': page_items,
        'unmatched': unmatched[:50],
    }


def _error_fluctuation_response(book_name, compare_book, compare_type,
                                balance_type, threshold_pct, error_msg):
    return {
        'book_name': book_name,
        'compare_book': compare_book,
        'compare_type': compare_type,
        'balance_type': balance_type,
        'threshold_pct': threshold_pct,
        'summary': {
            'total_subjects': 0, 'matched_subjects': 0,
            'unmatched_subjects': 0, 'anomaly_count': 0, 'anomaly_rate': '0%',
        },
        'items': [],
        'unmatched': [],
        'error': error_msg,
    }


# ═══════════════════════════════════════════
# 3. 毛利率联动分析
# ═══════════════════════════════════════════


async def gross_margin_analysis(
    db: AsyncSession,
    book_name: str,
    compare_book: Optional[str] = None,
    revenue_subjects: Optional[list[str]] = None,
    cost_subjects: Optional[list[str]] = None,
) -> dict:
    """
    毛利率分析。
    通过模板匹配或手动指定收入/成本科目名称，计算毛利率和变动。
    """
    # --- 从模板获取默认收入/成本科目名称 ---
    if not revenue_subjects:
        for tpl in DRAFT_TEMPLATES.values():
            if tpl.get('code') == 'revenue':
                revenue_subjects = tpl.get('subject_names', [])
                break
        if not revenue_subjects:
            revenue_subjects = ['主营业务收入', '其他业务收入']

    if not cost_subjects:
        for tpl in DRAFT_TEMPLATES.values():
            if tpl.get('code') == 'cost':
                cost_subjects = tpl.get('subject_names', [])
                break
        if not cost_subjects:
            cost_subjects = ['主营业务成本', '其他业务成本']

    def _calc_for_book(book: str) -> dict:
        """计算单个账套的营收/成本/毛利率"""
        r = db.execute(
            select(BalanceSubject).where(BalanceSubject.book_name == book)
        )
        # 注意: this is a coroutine that needs await
        # We'll handle it differently below
        ...

    # 因为 SQLAlchemy 异步 session 的限制，不能在嵌套函数中 await，
    # 直接在顶层读取并传参处理
    cur_r = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
    )
    cur_all = cur_r.scalars().all()

    cmp_all = []
    if compare_book:
        cmp_r = await db.execute(
            select(BalanceSubject).where(BalanceSubject.book_name == compare_book)
        )
        cmp_all = cmp_r.scalars().all()

    def _calc(subjects) -> dict:
        """从科目列表汇总收入/成本"""
        groups = _group_subjects_by_code(subjects)
        name_code_map = _build_name_code_map(subjects)

        total_revenue = 0.0
        total_cost = 0.0
        rev_names = set()
        cost_names = set()

        def _sum_subjects(l1_code, balance_fn) -> float:
            """汇总一级科目及其子科目。
            策略：如果一级科目本身有余额，直接用一级科目（已含子科目总和）；
            否则累加直接子科目（code == l1_code.XXX 且只有一级子级）。"""
            if l1_code not in groups:
                # 一级编码本身不存在，累加子科目
                total = 0.0
                prefix = l1_code + '.'
                for code, g in groups.items():
                    if code.startswith(prefix) and code.count('.') == 1:
                        total += balance_fn(g)
                return total

            l1_balance = balance_fn(groups[l1_code])
            if l1_balance != 0:
                # 一级科目有余额，直接用（已包含子科目）
                return l1_balance

            # 一级科目余额为 0（可能没有数据），累加子科目
            total = 0.0
            prefix = l1_code + '.'
            for code, g in groups.items():
                if code.startswith(prefix) and code.count('.') == 1:
                    total += balance_fn(g)
            return total

        for name in revenue_subjects:
            l1_code = name_code_map.get(name)
            if not l1_code:
                continue
            rev_names.add(name)
            total_revenue += _sum_subjects(l1_code,
                lambda g: g['end_credit'] - g['end_debit'])

        for name in cost_subjects:
            l1_code = name_code_map.get(name)
            if not l1_code:
                continue
            cost_names.add(name)
            total_cost += _sum_subjects(l1_code,
                lambda g: g['end_debit'] - g['end_credit'])

        total_revenue = round(total_revenue, 2)
        total_cost = round(total_cost, 2)
        gross_profit = round(total_revenue - total_cost, 2)
        gross_margin = round(gross_profit / total_revenue * 100, 2) if total_revenue != 0 else 0.0

        return {
            'revenue': total_revenue,
            'cost': total_cost,
            'gross_profit': gross_profit,
            'gross_margin': gross_margin,
            'revenue_subjects': sorted(rev_names),
            'cost_subjects': sorted(cost_names),
        }

    try:
        current = _calc(cur_all)
    except Exception as e:
        current = {
            'revenue': 0, 'cost': 0, 'gross_profit': 0, 'gross_margin': 0,
            'revenue_subjects': [], 'cost_subjects': [],
            'error': str(e),
        }

    compare = None
    change = None
    risk_assessment = {'has_risk': False, 'alerts': []}

    if compare_book and cmp_all:
        try:
            compare = _calc(cmp_all)
        except Exception as e:
            compare = {
                'revenue': 0, 'cost': 0, 'gross_profit': 0, 'gross_margin': 0,
                'revenue_subjects': [], 'cost_subjects': [],
                'error': str(e),
            }

        if compare and 'error' not in compare:
            rev_chg = round(
                (current['revenue'] - compare['revenue']) / abs(compare['revenue']) * 100, 2
            ) if compare['revenue'] != 0 else None
            cost_chg = round(
                (current['cost'] - compare['cost']) / abs(compare['cost']) * 100, 2
            ) if compare['cost'] != 0 else None
            gp_chg = round(
                (current['gross_profit'] - compare['gross_profit']) / abs(compare['gross_profit']) * 100, 2
            ) if compare['gross_profit'] != 0 else None
            gm_chg_ppt = round(current['gross_margin'] - compare['gross_margin'], 2)

            change = {
                'revenue_change_pct': rev_chg,
                'cost_change_pct': cost_chg,
                'gross_profit_change_pct': gp_chg,
                'gross_margin_change_ppt': gm_chg_ppt,
            }

            # --- 风险判断 ---
            alerts = []
            if rev_chg is not None and abs(rev_chg) >= 20 and abs(gm_chg_ppt) >= 5:
                alerts.append({
                    'type': 'revenue_cost_mismatch',
                    'severity': 'high',
                    'message': (
                        f'收入变动 {rev_chg:+.1f}% 同时毛利率变动 {gm_chg_ppt:+.1f}pp，'
                        f'可能存在收入跨期或成本错配'
                    ),
                })
            if abs(gm_chg_ppt) >= 10:
                alerts.append({
                    'type': 'gross_margin_volatility',
                    'severity': 'critical',
                    'message': f'毛利率波动 {gm_chg_ppt:+.1f}pp，超过 10pp（重大异常）',
                })
            if current['gross_margin'] < 0:
                alerts.append({
                    'type': 'negative_margin',
                    'severity': 'critical',
                    'message': '毛利率为负，成本大于收入，检查是否错记科目',
                })
            if gm_chg_ppt > 5 and rev_chg is not None and rev_chg > 20:
                alerts.append({
                    'type': 'revenue_growth_margin_drop',
                    'severity': 'medium',
                    'message': (
                        f'收入增长 {rev_chg:+.1f}% > 20%，但毛利率下降 {abs(gm_chg_ppt):.1f}pp，'
                        f'可能收入跨期或成本多计'
                    ),
                })
            if rev_chg is not None and rev_chg < -20 and gm_chg_ppt > 5:
                alerts.append({
                    'type': 'revenue_drop_margin_rise',
                    'severity': 'medium',
                    'message': (
                        f'收入下降 {rev_chg:+.1f}%，但毛利率上升 {gm_chg_ppt:+.1f}pp，'
                        f'可能成本跨期或收入少计'
                    ),
                })

            risk_assessment = {
                'has_risk': len(alerts) > 0,
                'alerts': alerts,
            }

    return {
        'book_name': book_name,
        'compare_book': compare_book,
        'current': current,
        'compare': compare,
        'change': change,
        'risk_assessment': risk_assessment,
    }
