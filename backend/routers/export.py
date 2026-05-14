from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from io import BytesIO
import openpyxl
from urllib.parse import quote
from backend.database import async_session_factory
from backend.models import BalanceSubject
from sqlalchemy import select, text

router = APIRouter(prefix="/api", tags=["模板下载与底稿导出"])


def _download_excel(stream, filename):
    encoded = quote(filename)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    )


@router.get("/templates/balance")
async def download_balance_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "科目余额表"
    ws.append(["科目编码", "科目名称", "年初余额-借方", "年初余额-贷方",
                "本期发生额-借方", "本期发生额-贷方",
                "本年累计-借方", "本年累计-贷方",
                "期末余额-借方", "期末余额-贷方", "核算维度"])
    ws.append(["1002", "银行存款", 100000, "", 50000, 20000, 50000, 20000, 130000, "", "银行账户:XX支行"])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return _download_excel(stream, "科目余额表模板.xlsx")


@router.get("/templates/journal")
async def download_journal_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "序时账"
    ws.append(["核算组织", "期间", "凭证号", "摘要", "科目编码", "科目名称", "借方", "贷方", "核算维度"])
    ws.append(["XX公司", "2026年1期", "0001", "计提工资", "6602.18", "管理费用_审计咨询费", 10000, "", "部门:综合部"])
    ws.append(["XX公司", "2026年1期", "0001", "计提工资", "2211.02", "应付职工薪酬_奖金", "", 10000, ""])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return _download_excel(stream, "序时账模板.xlsx")


@router.get("/export/draft")
async def export_balance_to_draft(
    book_name: str = "default",
    code_prefix: str = "",
    level: int = 0,
):
    async with async_session_factory() as session:
        filters = ["book_name = :bn"]
        params = {"bn": book_name}

        if code_prefix:
            filters.append("code LIKE :cp")
            params["cp"] = f"{code_prefix}%"

        if level > 0:
            dots = "." * level
            filters.append(f"code LIKE :dots_pat")
            filters.append(f"code NOT LIKE :dots_sub_pat")
            params["dots_pat"] = f"%{dots}%"
            params["dots_sub_pat"] = f"%{dots}.%"

        where_clause = " AND ".join(filters)
        result = await session.execute(
            text(f"SELECT code, name, year_start_debit, year_start_credit, "
                 f"period_debit, period_credit, end_debit, end_credit, dimension "
                 f"FROM balance_subjects WHERE {where_clause} ORDER BY code"),
            params
        )
        subjects = result.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "科目余额表"
    ws.append(["科目编码", "科目名称", "年初借方", "年初贷方",
                "本期借方", "本期贷方", "期末借方", "期末贷方", "核算维度"])

    for s in subjects:
        ws.append(list(s))

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"科目余额表_{book_name}"
    if code_prefix:
        filename += f"_{code_prefix}"
    filename += ".xlsx"

    return _download_excel(stream, filename)