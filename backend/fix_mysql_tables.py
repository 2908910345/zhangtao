import asyncio
import aiomysql

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "229175899",
    "db": "accounting_system",
    "charset": "utf8mb4",
}

async def fix_tables():
    print("正在连接MySQL...")
    conn = await aiomysql.connect(**MYSQL_CONFIG)
    cursor = await conn.cursor()
    
    tables_to_fix = ["books", "balance_subjects", "journal_entries"]
    
    try:
        for table_name in tables_to_fix:
            print(f"\n修复表: {table_name}")
            
            try:
                await cursor.execute(f"DROP INDEX PRIMARY ON `{table_name}`")
                print(f"  - 已移除PRIMARY KEY索引")
            except Exception as e1:
                print(f"  - 移除主键索引: {e1}")
            
            try:
                alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT"
                await cursor.execute(alter_sql)
                print(f"  ✓ {table_name}.id 已设置为 AUTO_INCREMENT")
            except Exception as e2:
                print(f"  修改字段失败: {e2}")
        
        await conn.commit()
        print("\n所有表修复完成！")
        
    except Exception as e:
        print(f"\n错误: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    asyncio.run(fix_tables())
