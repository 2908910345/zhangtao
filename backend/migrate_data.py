import asyncio
import aiosqlite
import aiomysql
import os

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data", "accounting.db")

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "229175899",
    "db": "accounting_system",
    "charset": "utf8mb4",
}

CORE_TABLES = ["books", "balance_subjects", "journal_entries"]


async def get_sqlite_tables(sqlite_conn):
    cursor = await sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_alembic%'")
    rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def get_sqlite_table_info(sqlite_conn, table_name):
    cursor = await sqlite_conn.execute(f"PRAGMA table_info([{table_name}])")
    rows = await cursor.fetchall()
    columns = []
    for row in rows:
        col_name = row[1]
        col_type = row[2]
        nullable = not row[3]
        default = row[4]
        is_primary = row[5] == 1
        columns.append({"name": col_name, "type": col_type, "nullable": nullable, "default": default, "primary": is_primary})
    return columns


async def get_sqlite_data(sqlite_conn, table_name):
    cursor = await sqlite_conn.execute(f"SELECT * FROM [{table_name}]")
    rows = await cursor.fetchall()
    column_info = await get_sqlite_table_info(sqlite_conn, table_name)
    column_names = [col["name"] for col in column_info]
    return column_names, rows


def map_sqlite_type_to_mysql(col_type: str) -> str:
    col_type_upper = col_type.upper()
    if "INT" in col_type_upper:
        return "INT"
    elif "FLOAT" in col_type_upper or "REAL" in col_type_upper or "DOUBLE" in col_type_upper:
        return "DOUBLE"
    elif "TEXT" in col_type_upper or "VARCHAR" in col_type_upper or "CHAR" in col_type_upper:
        return "VARCHAR(500)"
    elif "BLOB" in col_type_upper:
        return "LONGBLOB"
    elif "DATETIME" in col_type_upper or "TIMESTAMP" in col_type_upper:
        return "DATETIME"
    else:
        return "VARCHAR(500)"


def format_default(col):
    default = col["default"]
    if default is None:
        return ""
    default_str = str(default)
    if default_str.upper() in ("CURRENT_TIMESTAMP", "(CURRENT_TIMESTAMP)"):
        return "DEFAULT CURRENT_TIMESTAMP"
    if default_str.upper() in ("CURRENT_DATE", "(CURRENT_DATE)"):
        return "DEFAULT CURRENT_DATE"
    if default_str.startswith("'") and default_str.endswith("'"):
        return f"DEFAULT {default_str}"
    return f"DEFAULT '{default_str}'"


async def create_mysql_table(mysql_conn, table_name, columns):
    col_defs = []
    for col in columns:
        col_name = col["name"]
        mysql_type = map_sqlite_type_to_mysql(col["type"])
        nullable = "NULL" if col["nullable"] else "NOT NULL"
        default_clause = format_default(col)
        
        if col.get("primary") and "INT" in mysql_type.upper():
            nullable = "NOT NULL AUTO_INCREMENT"
        elif default_clause:
            nullable = default_clause
            
        col_defs.append(f"`{col_name}` {mysql_type} {nullable}")
    
    primary_cols = [f"`{c['name']}`" for c in columns if c.get("primary")]
    if primary_cols:
        col_defs.append(f"PRIMARY KEY ({', '.join(primary_cols)})")
    
    col_defs_str = ", ".join(col_defs)
    create_sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({col_defs_str}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    cursor = await mysql_conn.cursor()
    await cursor.execute(create_sql)
    await cursor.close()


async def copy_table_data(sqlite_conn, mysql_conn, table_name):
    column_names, rows = await get_sqlite_data(sqlite_conn, table_name)
    if not rows:
        print(f"  [{table_name}] 无数据，跳过")
        return 0

    placeholders = ", ".join(["%s"] * len(column_names))
    col_names_quoted = ", ".join([f"`{c}`" for c in column_names])
    insert_sql = f"INSERT INTO `{table_name}` ({col_names_quoted}) VALUES ({placeholders})"

    cursor = await mysql_conn.cursor()
    batch_size = 500
    total = 0
    batch = []
    for row in rows:
        batch.append(tuple(row))
        if len(batch) >= batch_size:
            await cursor.executemany(insert_sql, batch)
            total += len(batch)
            batch = []
    if batch:
        await cursor.executemany(insert_sql, batch)
        total += len(batch)
    await cursor.close()
    print(f"  [{table_name}] 迁移 {total} 条记录")
    return total


async def migrate():
    print("=" * 50)
    print("SQLite → MySQL 数据迁移")
    print("=" * 50)

    print(f"\nSQLite 文件: {SQLITE_PATH}")
    if not os.path.exists(SQLITE_PATH):
        print(f"错误: SQLite 文件不存在: {SQLITE_PATH}")
        return

    sqlite_conn = await aiosqlite.connect(SQLITE_PATH)
    mysql_conn = await aiomysql.connect(**MYSQL_CONFIG)

    try:
        tables = await get_sqlite_tables(sqlite_conn)
        print(f"\nSQLite 中的表: {tables}")

        for table_name in tables:
            print(f"\n处理表: {table_name}")
            columns = await get_sqlite_table_info(sqlite_conn, table_name)
            print(f"  列: {[c['name'] for c in columns]}")
            await create_mysql_table(mysql_conn, table_name, columns)
            await copy_table_data(sqlite_conn, mysql_conn, table_name)
            await mysql_conn.commit()

        print("\n" + "=" * 50)
        print("迁移完成！")
        print("=" * 50)
    finally:
        await sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())