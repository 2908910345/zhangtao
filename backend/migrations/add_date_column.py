"""
迁移脚本：给已存在的序时账表添加 date（记账日期）列

用法：
    python -m backend.migrations.add_date_column

说明：
    扫描数据库中的所有 journal_* 表和 journal_entries 表，
    对缺少 date 列的表执行 ALTER TABLE ADD COLUMN。
    幂等安全 — 重复运行不会报错。
"""

import asyncio
import re
from sqlalchemy import inspect, text
from backend.database import engine, sanitize_table_name


async def migrate():
    async with engine.connect() as conn:
        # 获取所有用户表
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

        journal_tables = [t for t in tables if t == "journal_entries" or t.startswith("journal_")]

        if not journal_tables:
            print("✓ 未找到任何序时账表，无需迁移")
            return

        for table_name in sorted(journal_tables):
            columns = await conn.run_sync(
                lambda sync_conn: [col["name"] for col in inspect(sync_conn).get_columns(table_name)]
            )
            if "date" in columns:
                print(f"  → {table_name}: date 列已存在，跳过")
                continue

            print(f"  → {table_name}: 添加 date 列...")
            await conn.execute(
                text(f'ALTER TABLE "{table_name}" ADD COLUMN date VARCHAR(20) NOT NULL DEFAULT \'\'')
            )
            print(f"    ✓ 完成")

        await conn.commit()
        print(f"\n✓ 迁移完成，共处理 {len(journal_tables)} 张表")


if __name__ == "__main__":
    print("=== 序时账表添加记账日期(date)列迁移 ===\n")
    asyncio.run(migrate())
