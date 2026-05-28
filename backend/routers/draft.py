from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from backend.database import get_db, escape_like
from backend.models import BalanceSubject, AdjustmentEntry
from backend.services.template_defs import DRAFT_TEMPLATES
from backend.schemas import DetailHierarchyResponse, DetailHierarchyRow

router = APIRouter(prefix="/api/draft-templates", tags=["底稿模板"])


@router.get("")
async def list_templates(book_name: str = Query("default"), db: AsyncSession = Depends(get_db)):
    """列出所有底稿模板，标记哪些在当前账套中有数据"""
    result = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
    )
    all_subjects = result.scalars().all()

    # 建立名称→编码映射（一级科目名称 → 一级科目编码）
    name_code_map = {}  # name → l1_code
    l1_info = {}  # l1_code → {"name", "category"}
    for s in all_subjects:
        l1_code = s.code.split('.')[0]
        if l1_code not in l1_info:
            l1_info[l1_code] = {"name": s.name}
        # 以一级科目精确编码为准
        if s.code == l1_code:
            l1_info[l1_code]["name"] = s.name
            name_code_map[s.name] = l1_code
    # 二级科目用一级编码的名称
    for s in all_subjects:
        l1_code = s.code.split('.')[0]
        if l1_code in l1_info:
            nm = l1_info[l1_code]["name"]
            if nm not in name_code_map:
                name_code_map[nm] = l1_code

    # 收集所有模板已覆盖的科目名称
    covered_names = set()
    for tpl in DRAFT_TEMPLATES.values():
        for sn in tpl.get("subject_names", []):
            covered_names.add(sn)

    # 收集所有模板已覆盖的一级编码（通过名称反查）
    covered_l1_codes = set()
    for sn in covered_names:
        if sn in name_code_map:
            covered_l1_codes.add(name_code_map[sn])

    templates = []
    for name, tpl in DRAFT_TEMPLATES.items():
        subject_names = tpl.get("subject_names", [])
        # 检查数据中是否有匹配的科目名称
        has_data = any(
            sn in name_code_map
            for sn in subject_names
        )
        templates.append({
            "name": name,
            "code": tpl["code"],
            "category": tpl.get("category", ""),
            "subject_names": subject_names,
            "row_count": len(tpl["rows"]),
            "has_data": has_data,
        })

    # 按一级编码聚合
    from collections import OrderedDict
    account_groups = OrderedDict()
    for s in all_subjects:
        parts = s.code.split('.')
        l1_code = parts[0]
        if l1_code not in account_groups:
            account_groups[l1_code] = set()
        account_groups[l1_code].add(s.code)

    # 对每个一级科目，判断是否需要作为独立模板显示
    account_templates = []
    seen_account_codes = set()
    for s in all_subjects:
        l1_code = s.code.split('.')[0]
        if l1_code in seen_account_codes:
            continue
        seen_account_codes.add(l1_code)

        l1_name = l1_info.get(l1_code, {}).get("name", s.name)

        # 找对应的分类（按名称匹配）
        category = ""
        if l1_name in covered_names:
            for tname, tpl in DRAFT_TEMPLATES.items():
                if l1_name in tpl.get("subject_names", []):
                    category = tpl.get("category", "")
                    break

        # 判断是否有明细数据
        codes_for_l1 = account_groups.get(l1_code, {l1_code})
        has_sub_accounts = any('.' in c for c in codes_for_l1)
        dim_entries = sum(
            1 for s2 in all_subjects
            if s2.code.split('.')[0] == l1_code and s2.dimension
        )

        account_templates.append({
            "name": l1_name,
            "code": f"account:{l1_code}",
            "category": category,
            "subject_names": [l1_name],
            "row_count": 1,
            "has_data": True,
            "is_account_detail": True,
            "detail_info": {
                "has_sub_accounts": has_sub_accounts,
                "dim_count": dim_entries,
            },
        })

    return {
        "templates": templates,
        "account_templates": account_templates,
    }


@router.get("/{template_code}")
async def get_template_data(
    template_code: str,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db),
):
    tpl = None
    tpl_name = ""
    for name, t in DRAFT_TEMPLATES.items():
        if t["code"] == template_code:
            tpl = t
            tpl_name = name
            break

    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 查询当前账套所有科目
    result = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
        .order_by(BalanceSubject.code)
    )
    all_subjects_raw = result.scalars().all()

    # 按 code 分组合并
    subject_map = _build_subject_map(all_subjects_raw)

    # 建立名称→编码映射
    name_code_map = _build_name_code_map(all_subjects_raw)

    # 逐行计算
    rows = []
    computed_values = {}  # code -> 计算后的值

    # 第一遍：计算所有数据行的值（按名称匹配实际科目）
    for row_def in tpl["rows"]:
        is_total = row_def.get("is_total", False)
        is_net = row_def.get("is_net", False)
        code = row_def["code"]
        sign = row_def.get("sign", 1)
        label = row_def["label"]

        row_data = {
            "label": label,
            "code": code,
            "sign": sign,
            "is_total": is_total,
            "is_net": is_net,
            "source_rows": row_def.get("source_rows"),
            "values": {},
        }

        if is_total or is_net:
            row_data["values"] = {
                "unaudited": 0.0,
                "adj_debit": 0.0,
                "adj_credit": 0.0,
                "audited": 0.0,
            }
        else:
            # 数据行：按名称查找实际科目编码，汇总取值
            subject = _find_subject_by_name(name_code_map, subject_map, label)
            if subject and subject.get("end_balance") is not None:
                val = float(subject["end_balance"])
            else:
                val = 0.0
            row_data["values"] = {
                "unaudited": val,
                "adj_debit": 0.0,
                "adj_credit": 0.0,
                "audited": val,
            }
            computed_values[code] = val

        rows.append(row_data)

    # 第二遍：计算合计行和净额行
    row_by_code = {}
    for i, r in enumerate(rows):
        row_by_code[r["code"]] = {"index": i, "row": r}

    for i, row_data in enumerate(rows):
        if not row_data["is_total"] and not row_data["is_net"]:
            continue

        source_rows = row_data.get("source_rows")
        is_total = row_data["is_total"]

        if source_rows:
            total = 0.0
            for src_code in source_rows:
                if src_code in row_by_code:
                    src = row_by_code[src_code]["row"]
                    src_sign = src.get("sign", 1)
                    src_val = src["values"].get("unaudited", 0.0) or 0.0
                    total += src_val * src_sign
                else:
                    # source_rows 可能引用一个科目名称，尝试按名称查找
                    subject = _find_subject_by_name(name_code_map, subject_map, src_code)
                    if subject and subject.get("end_balance") is not None:
                        total += float(subject["end_balance"])
            row_data["values"]["unaudited"] = round(total, 2)
            row_data["values"]["audited"] = round(total, 2)
        elif is_total:
            total = 0.0
            for j in range(0, i):
                prev = rows[j]
                if prev["is_total"] or prev["is_net"]:
                    continue
                prev_sign = prev.get("sign", 1)
                prev_val = prev["values"].get("unaudited", 0.0) or 0.0
                total += prev_val * prev_sign
            row_data["values"]["unaudited"] = round(total, 2)
            row_data["values"]["audited"] = round(total, 2)

        computed_values[row_data["code"]] = row_data["values"]["unaudited"]

    return {
        "name": tpl_name,
        "code": tpl["code"],
        "category": tpl.get("category", ""),
        "columns": tpl["columns"],
        "rows": rows,
    }


# -------------------- 调整值持久化 --------------------


@router.get("/{template_code}/adjustments")
async def get_template_adjustments(
    template_code: str,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db),
):
    """获取某底稿模板所有科目的调整值（从 adjustment_entries 聚合）"""
    tpl = None
    for name, t in DRAFT_TEMPLATES.items():
        if t["code"] == template_code:
            tpl = t
            break
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 查询当前账套所有科目，建立名称→编码映射
    result = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
    )
    all_subjects = result.scalars().all()
    name_code_map = _build_name_code_map(all_subjects)

    # 按名称收集模板涉及的所有实际科目编码
    all_codes = set()
    for row in tpl["rows"]:
        code = row["code"]
        if code and code not in ("TOTAL", "NET", "NET_1", "SUBTOTAL_1"):
            # 尝试通过名称映射得到实际编码
            actual_codes = _resolve_actual_codes(code, name_code_map, all_subjects)
            all_codes.update(actual_codes)

    if not all_codes:
        return {"adjustments": {}}

    result = await db.execute(
        select(
            AdjustmentEntry.subject_code,
            func.coalesce(func.sum(AdjustmentEntry.debit), 0).label("total_debit"),
            func.coalesce(func.sum(AdjustmentEntry.credit), 0).label("total_credit"),
        ).where(
            AdjustmentEntry.book_name == book_name,
            AdjustmentEntry.subject_code.in_(list(all_codes)),
        ).group_by(AdjustmentEntry.subject_code)
    )
    adjust_rows = result.all()

    adjustments = {}
    for code, debit, credit in adjust_rows:
        adjustments[code] = {
            "adj_debit": float(debit),
            "adj_credit": float(credit),
        }

    return {"adjustments": adjustments}


@router.put("/{template_code}/adjustments")
async def save_template_adjustments(
    template_code: str,
    data: dict,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db),
):
    """
    保存底稿模板的调整值。
    body: {"adjustments": {"<科目名称或编码>": {"adj_debit": 1000, "adj_credit": 0}, ...}}
    前端可以使用模板行 label 名称或实际科目编码，后端自动转换。
    """
    tpl = None
    tpl_name = ""
    for name, t in DRAFT_TEMPLATES.items():
        if t["code"] == template_code:
            tpl = t
            tpl_name = name
            break
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 查询当前账套所有科目，建立名称→编码映射
    result = await db.execute(
        select(BalanceSubject).where(BalanceSubject.book_name == book_name)
    )
    all_subjects = result.scalars().all()
    name_code_map = _build_name_code_map(all_subjects)

    adjustments = data.get("adjustments", {})

    for key, adj in adjustments.items():
        adj_debit = float(adj.get("adj_debit", 0))
        adj_credit = float(adj.get("adj_credit", 0))

        # 将 key（可能是科目名称或编码）解析为实际一级科目编码
        actual_codes = _resolve_actual_codes(key, name_code_map, all_subjects)
        if not actual_codes:
            # 如果无法解析为名称，直接作为编码使用
            actual_codes = [key]

        for subject_code in actual_codes:
            result2 = await db.execute(
                select(AdjustmentEntry).where(
                    AdjustmentEntry.book_name == book_name,
                    AdjustmentEntry.subject_code == subject_code,
                    AdjustmentEntry.summary == f"[底稿]{tpl_name}",
                )
            )
            existing = result2.scalars().first()

            if existing:
                if adj_debit == 0 and adj_credit == 0:
                    await db.delete(existing)
                else:
                    existing.debit = adj_debit
                    existing.credit = adj_credit
            else:
                if adj_debit != 0 or adj_credit != 0:
                    entry = AdjustmentEntry(
                        book_name=book_name,
                        voucher_no="",
                        summary=f"[底稿]{tpl_name}",
                        subject_code=subject_code,
                        subject_name="",
                        debit=adj_debit,
                        credit=adj_credit,
                    )
                    db.add(entry)

    await db.commit()
    return {"ok": True}


# -------------------- 科目数据工具函数 --------------------


def _build_subject_map(subjects):
    """按 code 分组，无维度的汇总行作为主记录，有维度的保留在 dim_rows。
    修复：当同一编码只有维度行（无汇总行）时，所有维度行金额累加到主记录。"""
    from collections import OrderedDict
    groups = OrderedDict()

    def _make_entry(s):
        return {
            "code": s.code,
            "name": s.name,
            "year_start_debit": float(s.year_start_debit or 0),
            "year_start_credit": float(s.year_start_credit or 0),
            "period_debit": float(s.period_debit or 0),
            "period_credit": float(s.period_credit or 0),
            "year_total_debit": float(s.year_total_debit or 0),
            "year_total_credit": float(s.year_total_credit or 0),
            "end_debit": float(s.end_debit or 0),
            "end_credit": float(s.end_credit or 0),
            "end_balance": float(s.end_debit or 0) - float(s.end_credit or 0),
            "dimension": s.dimension or "",
            "dim_rows": [],
        }

    for s in subjects:
        if s.code not in groups:
            groups[s.code] = _make_entry(s)
        else:
            existing = groups[s.code]
            if s.dimension:
                existing["dim_rows"].append(_make_entry(s))
            else:
                existing["year_start_debit"] += float(s.year_start_debit or 0)
                existing["year_start_credit"] += float(s.year_start_credit or 0)
                existing["period_debit"] += float(s.period_debit or 0)
                existing["period_credit"] += float(s.period_credit or 0)
                existing["year_total_debit"] += float(s.year_total_debit or 0)
                existing["year_total_credit"] += float(s.year_total_credit or 0)
                existing["end_debit"] += float(s.end_debit or 0)
                existing["end_credit"] += float(s.end_credit or 0)
                existing["end_balance"] = existing["end_debit"] - existing["end_credit"]

    # 修复：纯维度行编码（无汇总行），将所有维度行金额累加到主记录
    for code, entry in groups.items():
        if entry["dim_rows"] and not any(
            not s.dimension for s in subjects if s.code == code
        ):
            # 无汇总行：维度行金额累加
            for dr in entry["dim_rows"]:
                entry["year_start_debit"] += dr["year_start_debit"]
                entry["year_start_credit"] += dr["year_start_credit"]
                entry["period_debit"] += dr["period_debit"]
                entry["period_credit"] += dr["period_credit"]
                entry["year_total_debit"] += dr["year_total_debit"]
                entry["year_total_credit"] += dr["year_total_credit"]
                entry["end_debit"] += dr["end_debit"]
                entry["end_credit"] += dr["end_credit"]
            entry["end_balance"] = entry["end_debit"] - entry["end_credit"]

    return groups


def _build_name_code_map(subjects):
    """建立科目名称 → 一级编码的映射。
    优先精确匹配一级科目编码（code 中不含 '.'）的名称。
    返回 {科目名称: 一级编码} 字典。"""
    name_map = {}
    # 第一遍：精确一级科目（code 中不含 '.'）
    for s in subjects:
        if '.' not in s.code:
            name_map[s.name] = s.code
    # 第二遍：子级科目的父级名称
    for s in subjects:
        if '.' in s.code:
            l1_code = s.code.split('.')[0]
            # 查找一级科目的名称
            for nm, code in list(name_map.items()):
                if code == l1_code:
                    if nm not in name_map:
                        name_map[nm] = l1_code
                    break
    return name_map


def _find_subject_by_name(name_code_map, subject_map, name):
    """按科目名称查找并汇总所有匹配科目的数据。
    匹配逻辑：
    1. 通过 name_code_map 找到名称对应的实际一级编码
    2. 汇总一级编码 + 所有直属二级编码（最多一个 "." 的编码）
    3. 跳过三级及以上（因为二级汇总行已包含其子级）
    例如：汇总 1124 + 1124.04 + 1124.12，但不汇总 1124.06.01（1124.06 已包含）
    """
    l1_code = name_code_map.get(name)
    if not l1_code:
        return None

    # 汇总一级编码 + 直属二级编码
    matched = []
    for code, s in subject_map.items():
        if code == l1_code:
            matched.append(s)
        elif code.startswith(l1_code + ".") and code.count('.') == 1:
            matched.append(s)

    if not matched:
        return None
    if len(matched) == 1:
        return matched[0]

    return {
        "code": l1_code,
        "name": name,
        "year_start_debit": sum(s["year_start_debit"] for s in matched),
        "year_start_credit": sum(s["year_start_credit"] for s in matched),
        "period_debit": sum(s["period_debit"] for s in matched),
        "period_credit": sum(s["period_credit"] for s in matched),
        "year_total_debit": sum(s["year_total_debit"] for s in matched),
        "year_total_credit": sum(s["year_total_credit"] for s in matched),
        "end_debit": sum(s["end_debit"] for s in matched),
        "end_credit": sum(s["end_credit"] for s in matched),
        "end_balance": sum(s["end_balance"] for s in matched),
        "dimension": "",
        "dim_rows": [],
    }


def _resolve_actual_codes(key, name_code_map, all_subjects):
    """将模板中的 key（可能是科目名称或编码）解析为实际一级科目编码列表。
    优先按名称查找，失败则作为编码使用。"""
    # 尝试作为名称匹配
    l1_code = name_code_map.get(key)
    if l1_code:
        return [l1_code]

    # 如果 key 本身就是实际编码，直接返回
    for s in all_subjects:
        if s.code.split('.')[0] == key:
            return [key]

    # 尝试模糊匹配（key 是名称的子串）
    for name, code in name_code_map.items():
        if key in name or name in key:
            return [code]

    return []


# -------------------- 明细表 --------------------


def _parse_dimension_value(dim_str, dim_type=None):
    """从维度字符串中提取指定类型的值"""
    if not dim_str:
        return ''
    parts = dim_str.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            key, val = part.split(':', 1)
            if dim_type and key.strip() == dim_type:
                return val.strip()
        elif not dim_type:
            return part.strip()
    return ''


def _extract_dim_types(dim_str):
    """从维度字符串中提取所有维度类型"""
    if not dim_str:
        return []
    types = []
    seen = set()
    parts = dim_str.split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            key = part.split(':', 1)[0].strip()
            if key and key not in seen:
                seen.add(key)
                types.append(key)
    return types


@router.get("/detail/{subject_code}/dimensions")
async def get_detail_dimension_types(
    subject_code: str,
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db),
):
    """查询该科目的维度类型，优先从科目余额表维度行获取"""
    result = await db.execute(
        select(BalanceSubject.dimension).where(
            BalanceSubject.book_name == book_name,
            BalanceSubject.code == subject_code,
            BalanceSubject.dimension != '',
            BalanceSubject.dimension.isnot(None),
        ).distinct()
    )
    dim_samples = [row[0] for row in result if row[0]]

    dim_type_set = set()
    dim_types = []
    for sample in dim_samples:
        for dt in _extract_dim_types(sample):
            if dt not in dim_type_set:
                dim_type_set.add(dt)
                dim_types.append(dt)

    return {"dimension_types": dim_types}


@router.get("/detail/{subject_code}")
async def get_detail_schedule(
    subject_code: str,
    dimension_type: str = Query("", description="维度类型，为空则使用第一个可用维度"),
    opening_sign: str = Query("debit", description="期初数正负方向: debit=借方为正(年初借-年初贷), credit=贷方为正(年初贷-年初借)"),
    book_name: str = Query("default"),
    db: AsyncSession = Depends(get_db),
):
    """
    按维度划分的往来明细表。
    直接从科目余额表的维度行获取数据，确保与科目余额表完全勾稽。

    opening_sign: 控制期初数正负方向
      - "debit" (默认): 期初 = 年初借方 - 年初贷方
      - "credit": 期初 = 年初贷方 - 年初借方
    不影响借方发生额/贷方发生额。
    """
    # 期初数方向
    def calc_opening(debit, credit):
        if opening_sign == "credit":
            return float(credit or 0) - float(debit or 0)
        return float(debit or 0) - float(credit or 0)
    result = await db.execute(
        select(BalanceSubject).where(
            BalanceSubject.book_name == book_name,
            BalanceSubject.code == subject_code,
        )
    )
    all_rows = result.scalars().all()

    if not all_rows:
        return _empty_detail(subject_code, dimension_type)

    summary_row = None
    dim_rows = []
    for r in all_rows:
        if not r.dimension:
            summary_row = r
        else:
            dim_rows.append(r)

    if not summary_row:
        summary_row = all_rows[0]
        for r in all_rows[1:]:
            summary_row.year_start_debit = (summary_row.year_start_debit or 0) + (r.year_start_debit or 0)
            summary_row.year_start_credit = (summary_row.year_start_credit or 0) + (r.year_start_credit or 0)
            summary_row.period_debit = (summary_row.period_debit or 0) + (r.period_debit or 0)
            summary_row.period_credit = (summary_row.period_credit or 0) + (r.period_credit or 0)
            summary_row.end_debit = (summary_row.end_debit or 0) + (r.end_debit or 0)
            summary_row.end_credit = (summary_row.end_credit or 0) + (r.end_credit or 0)
        dim_rows = [r for r in all_rows if r.dimension]

    ctrl_opening = calc_opening(summary_row.year_start_debit, summary_row.year_start_credit)
    ctrl_debit = float(summary_row.period_debit or 0)
    ctrl_credit = float(summary_row.period_credit or 0)
    ctrl_closing = float(summary_row.end_debit or 0) - float(summary_row.end_credit or 0)

    if not dimension_type and dim_rows:
        for r in dim_rows:
            types = _extract_dim_types(r.dimension)
            if types:
                dimension_type = types[0]
                break

    if not dimension_type or not dim_rows:
        return {
            "subject_code": subject_code,
            "subject_name": summary_row.name,
            "dimension_type": dimension_type,
            "ctrl_opening": ctrl_opening,
            "ctrl_debit": ctrl_debit,
            "ctrl_credit": ctrl_credit,
            "ctrl_closing": ctrl_closing,
            "rows": [],
            "reconciled": True,
        }

    rows = []
    seen_names = {}
    for r in dim_rows:
        dim_value = _parse_dimension_value(r.dimension, dimension_type)
        if not dim_value:
            dim_value = r.dimension

        opening = calc_opening(r.year_start_debit, r.year_start_credit)
        debit = float(r.period_debit or 0)
        credit = float(r.period_credit or 0)
        closing = float(r.end_debit or 0) - float(r.end_credit or 0)

        if dim_value in seen_names:
            idx = seen_names[dim_value]
            rows[idx]['opening'] += opening
            rows[idx]['debit'] += debit
            rows[idx]['credit'] += credit
            rows[idx]['closing'] += closing
        else:
            seen_names[dim_value] = len(rows)
            rows.append({
                'name': dim_value,
                'opening': round(opening, 2),
                'debit': round(debit, 2),
                'credit': round(credit, 2),
                'closing': round(closing, 2),
            })

    # "其他"行 = 控制数 - 维度行合计（确保勾稽）
    dim_opening_total = round(sum(r['opening'] for r in rows), 2)
    dim_debit_total = round(sum(r['debit'] for r in rows), 2)
    dim_credit_total = round(sum(r['credit'] for r in rows), 2)
    dim_closing_total = round(sum(r['closing'] for r in rows), 2)

    other_opening = round(ctrl_opening - dim_opening_total, 2)
    other_debit = round(ctrl_debit - dim_debit_total, 2)
    other_credit = round(ctrl_credit - dim_credit_total, 2)
    other_closing = round(ctrl_closing - dim_closing_total, 2)

    if abs(other_opening) > 0.005 or abs(other_debit) > 0.005 or abs(other_credit) > 0.005 or abs(other_closing) > 0.005:
        rows.append({
            'name': '其他',
            'opening': other_opening,
            'debit': other_debit,
            'credit': other_credit,
            'closing': other_closing,
        })

    rows.sort(key=lambda r: (r['name'] == '其他', r['name']))

    # 勾稽校验
    sum_opening = round(sum(r['opening'] for r in rows), 2)
    sum_debit = round(sum(r['debit'] for r in rows), 2)
    sum_credit = round(sum(r['credit'] for r in rows), 2)
    sum_closing = round(sum(r['closing'] for r in rows), 2)

    reconciled = (
        abs(sum_opening - ctrl_opening) < 0.01
        and abs(sum_debit - ctrl_debit) < 0.01
        and abs(sum_credit - ctrl_credit) < 0.01
        and abs(sum_closing - ctrl_closing) < 0.01
    )

    return {
        "subject_code": subject_code,
        "subject_name": summary_row.name,
        "dimension_type": dimension_type,
        "opening_sign": opening_sign,
        "ctrl_opening": ctrl_opening,
        "ctrl_debit": ctrl_debit,
        "ctrl_credit": ctrl_credit,
        "ctrl_closing": ctrl_closing,
        "rows": rows,
        "reconciled": reconciled,
    }


def _empty_detail(subject_code, dimension_type):
    return {
        "subject_code": subject_code,
        "subject_name": "",
        "dimension_type": dimension_type,
        "ctrl_opening": 0,
        "ctrl_debit": 0,
        "ctrl_credit": 0,
        "ctrl_closing": 0,
        "rows": [],
        "reconciled": True,
        "opening_sign": "debit",
    }


# ==================== 层级底稿明细表（新） ====================


class _DimRow:
    """维度明细行"""
    def __init__(self, dimension: str, year_start_debit: float, year_start_credit: float,
                 period_debit: float, period_credit: float):
        self.dimension = dimension
        self.year_start_debit = year_start_debit
        self.year_start_credit = year_start_credit
        self.period_debit = period_debit
        self.period_credit = period_credit


class _HierGroup:
    """单个科目编码的分组合并结果"""
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name
        self.year_start_debit = 0.0
        self.year_start_credit = 0.0
        self.period_debit = 0.0
        self.period_credit = 0.0
        self.dim_rows: list[_DimRow] = []
        self.has_summary = False


def _merge_hier_subjects(subjects: list[BalanceSubject]) -> dict[str, _HierGroup]:
    """将同编码科目合并：无维度的汇总到主记录，有维度的放进 dim_rows"""
    groups: dict[str, _HierGroup] = {}
    for s in subjects:
        code = s.code
        if code not in groups:
            groups[code] = _HierGroup(code, s.name)
        g = groups[code]
        if s.dimension:
            g.dim_rows.append(_DimRow(
                dimension=s.dimension,
                year_start_debit=float(s.year_start_debit or 0),
                year_start_credit=float(s.year_start_credit or 0),
                period_debit=float(s.period_debit or 0),
                period_credit=float(s.period_credit or 0),
            ))
        else:
            g.year_start_debit += float(s.year_start_debit or 0)
            g.year_start_credit += float(s.year_start_credit or 0)
            g.period_debit += float(s.period_debit or 0)
            g.period_credit += float(s.period_credit or 0)
            g.has_summary = True
    return groups


def _is_direct_child(code: str, parent_code: str) -> bool:
    """判断 code 是否是 parent_code 的直接子级（恰好多一个层级）"""
    if not code.startswith(parent_code + '.'):
        return False
    rest = code[len(parent_code) + 1:]
    return '.' not in rest


def _get_dim_display(dim_str: str) -> str:
    """维度信息原样展示，不做解析"""
    return dim_str or ''


@router.get("/{template_code}/detail-hierarchy", response_model=DetailHierarchyResponse)
async def get_detail_hierarchy(
    template_code: str,
    book_name: str = Query("default"),
    opening_sign: str = Query("debit", description="期初数正负方向: debit=借方为正(年初借-年初贷), credit=贷方为正(年初贷-年初借)"),
    db: AsyncSession = Depends(get_db),
):
    """
    按科目层级生成底稿明细表。
    根据模板的 subject_names 获取所有相关科目（按名称动态匹配实际编码），按编码层级展开。
    支持 account:XXXX 格式直接按一级科目编码查询。

    输出字段：单位名称、款项性质、期初金额(年初借+年初贷)、借方发生额、贷方发生额
    """
    # 1. 解析模板编码，支持 "account:XXXX" 格式直接按科目编码查询
    is_account_mode = template_code.startswith("account:")
    tpl = None
    tpl_name = ""
    prefixes = []

    if is_account_mode:
        account_code = template_code[len("account:"):]
        prefixes = [account_code]
        # 找对应的分类和名称
        result = await db.execute(
            select(BalanceSubject).where(
                BalanceSubject.book_name == book_name,
                BalanceSubject.code == account_code,
            ).limit(1)
        )
        acct = result.scalar_one_or_none()
        if acct:
            tpl_name = acct.name
            # 尝试找对应的模板分类（按名称匹配）
            for name, t in DRAFT_TEMPLATES.items():
                if acct.name in t.get("subject_names", []):
                    tpl = {"code": account_code, "category": t.get("category", ""),
                           "subject_names": [acct.name]}
                    break
        if not tpl:
            tpl = {"code": account_code, "category": "", "subject_names": [acct.name] if acct else []}
    else:
        for name, t in DRAFT_TEMPLATES.items():
            if t["code"] == template_code:
                tpl = t
                tpl_name = name
                break
        if not tpl:
            raise HTTPException(status_code=404, detail="模板不存在")
        # 按名称解析为实际编码
        result = await db.execute(
            select(BalanceSubject).where(BalanceSubject.book_name == book_name)
        )
        all_subjects_raw = result.scalars().all()
        name_code_map = _build_name_code_map(all_subjects_raw)
        subject_names = tpl.get("subject_names", [])
        for sn in subject_names:
            l1_code = name_code_map.get(sn)
            if l1_code:
                prefixes.append(l1_code)

    # 2. 查询所有匹配的科目
    conditions = []
    for prefix in prefixes:
        conditions.append(BalanceSubject.code == prefix)
        conditions.append(BalanceSubject.code.like(f"{escape_like(prefix)}.%", escape="/"))

    result = await db.execute(
        select(BalanceSubject).where(
            BalanceSubject.book_name == book_name,
            or_(*conditions)
        ).order_by(BalanceSubject.code)
    )
    all_subjects = result.scalars().all()

    if not all_subjects:
        return DetailHierarchyResponse(
            template_name=tpl_name,
            template_code=template_code,
            category=tpl.get("category", ""),
            rows=[],
        )

    # 3. 分组合并
    groups = _merge_hier_subjects(all_subjects)

    # 4. 找出顶级编码：只取前缀本身在 groups 中的编码
    #    例如 prefix=6602，如果 groups 中有 "6602"，则只以 "6602" 为顶级
    #    其子级 6602.01 等会在递归中自动找到
    #    如果前缀本身不在 groups（例如只有一个 6602.01 没有 6602），则取直接子级
    top_codes = set()
    for prefix in prefixes:
        if prefix in groups:
            top_codes.add(prefix)
        else:
            # 前缀不在 groups 中 → 取它的直接子级作为顶级
            for code in groups:
                if code.startswith(prefix + '.'):
                    rest = code[len(prefix) + 1:]
                    if '.' not in rest:
                        top_codes.add(code)
    top_level_codes = sorted(top_codes)

    if not top_level_codes:
        top_level_codes = sorted(groups.keys())

    # 5. 递归生成行
    all_rows: list[dict] = []
    for tc in top_level_codes:
        section_rows = _build_section_rows(tc, groups, opening_sign)
        all_rows.extend(section_rows)

    # 6. 计算总计行
    total_opening = sum(r['opening'] for r in all_rows if not r['is_total'])
    total_debit = sum(r['debit'] for r in all_rows if not r['is_total'])
    total_credit = sum(r['credit'] for r in all_rows if not r['is_total'])

    total_row = DetailHierarchyRow(
        unit_name=f"{tpl_name}合计",
        nature=tpl_name,
        opening=round(total_opening, 2),
        debit=round(total_debit, 2),
        credit=round(total_credit, 2),
        is_total=True,
        level=0,
        subject_code="TOTAL",
    )

    return DetailHierarchyResponse(
        template_name=tpl_name,
        template_code=template_code,
        category=tpl.get("category", ""),
        opening_sign=opening_sign,
        rows=[DetailHierarchyRow(**r) for r in all_rows],
        total_row=total_row,
    )


def _calc_opening(opening_sign: str, debit, credit) -> float:
    """根据方向计算期初数"""
    if opening_sign == "credit":
        return float(credit or 0) - float(debit or 0)
    return float(debit or 0) - float(credit or 0)


def _build_section_rows(code: str, groups: dict[str, _HierGroup], opening_sign: str = "debit") -> list[dict]:
    """
    为一个科目编码生成层级行（递归）。
    返回 dict 列表。
    """
    g = groups.get(code)
    if not g:
        return []

    # 找直接子级
    children = sorted(
        [c for c in groups.keys() if _is_direct_child(c, code)],
        key=lambda x: x
    )

    rows: list[dict] = []

    level_base = _calc_level(code)

    if children:
        # ----- 场景1: 有子科目 -----
        for child_code in children:
            child_rows = _build_section_rows(child_code, groups, opening_sign)
            rows.extend(child_rows)

        sub_total = _sum_detail_rows(rows)
        rows.append(_make_row(
            unit_name=g.name, nature=g.name,
            opening=sub_total['opening'], debit=sub_total['debit'],
            credit=sub_total['credit'], is_total=True,
            level=level_base, subject_code=code,
        ))

    elif g.dim_rows:
        # ----- 场景2: 无子科目，有维度行 -----
        # 展开维度行，小计行 = 维度行的合计（确保勾稽）
        for dr in g.dim_rows:
            dim_val = _get_dim_display(dr.dimension)
            rows.append(_make_row(
                unit_name=dim_val, nature=g.name,
                opening=_calc_opening(opening_sign, dr.year_start_debit, dr.year_start_credit),
                debit=dr.period_debit, credit=dr.period_credit,
                is_total=False, level=level_base + 1, subject_code=code,
            ))
        total = _sum_dim_rows(g.dim_rows)
        rows.append(_make_row(
            unit_name=g.name, nature=g.name,
            opening=total['opening'], debit=total['debit'],
            credit=total['credit'], is_total=True,
            level=level_base, subject_code=code,
        ))

    else:
        # ----- 场景3: 无子科目无维度 → 直接作为数据行 -----
        opening = _calc_opening(opening_sign, g.year_start_debit, g.year_start_credit)
        rows.append(_make_row(
            unit_name=g.name, nature=g.name,
            opening=opening, debit=g.period_debit, credit=g.period_credit,
            is_total=False, level=level_base, subject_code=code,
        ))

    return rows


def _calc_level(code: str) -> int:
    """计算层级（1-indexed: 一级=1, 二级=2, 三级=3）"""
    return code.count('.') + 1


def _make_row(**kwargs) -> dict:
    """创建行字典"""
    return {
        'unit_name': kwargs.get('unit_name', ''),
        'nature': kwargs.get('nature', ''),
        'opening': round(kwargs.get('opening', 0.0), 2),
        'debit': round(kwargs.get('debit', 0.0), 2),
        'credit': round(kwargs.get('credit', 0.0), 2),
        'is_total': kwargs.get('is_total', False),
        'level': kwargs.get('level', 0),
        'subject_code': kwargs.get('subject_code', ''),
    }


def _sum_detail_rows(rows: list[dict]) -> dict:
    """汇总所有非合计行的金额"""
    opening = sum(r['opening'] for r in rows if not r['is_total'])
    debit = sum(r['debit'] for r in rows if not r['is_total'])
    credit = sum(r['credit'] for r in rows if not r['is_total'])
    return {'opening': opening, 'debit': debit, 'credit': credit}


def _sum_dim_rows(dim_rows: list[_DimRow]) -> dict:
    """汇总维度行的金额"""
    opening = sum(r.year_start_debit + r.year_start_credit for r in dim_rows)
    debit = sum(r.period_debit for r in dim_rows)
    credit = sum(r.period_credit for r in dim_rows)
    return {'opening': opening, 'debit': debit, 'credit': credit}

