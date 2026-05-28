# Plan: 数据库迁移 SQLite → MySQL

## Goal
将账套管理系统从 SQLite 迁移到 MySQL，保留现有数据，密码 229175899。

## Context
- 当前数据库：SQLite，文件位于 `backend/data/accounting.db`
- 目标数据库：MySQL
- 项目已内置 MySQL 支持（`aiomysql` 驱动、`Settings` 类支持 `db_type=mysql`）
- 配置方式：通过 `.env` 文件或环境变量（前缀 `ACCT_`）
- ORM：SQLAlchemy 2.0 Async，使用 `Base.metadata.create_all` 自动建表
- 3 张核心表：`books`、`balance_subjects`、`journal_entries`，外加动态分表 `journal_{book_name}`
- 无 Alembic 等迁移工具

## Steps

### 1. 确认 MySQL 环境及创建数据库
- **What**: 检查 MySQL 是否安装并运行，创建 `accounting_system` 数据库
- **Files**: 无
- **Verify**: MySQL 可连接，数据库已创建

### 2. 创建 .env 配置文件
- **What**: 在项目根目录创建 `.env`，配置 MySQL 连接参数
- **Files**: `.env`
- **Verify**: 配置参数正确

### 3. 编写数据迁移脚本
- **What**: 编写 Python 脚本将 SQLite 数据迁移到 MySQL，包括：
  - 使用 Base.metadata.create_all 在 MySQL 中建表
  - 迁移 `books`、`balance_subjects`、`journal_entries` 数据
  - 迁移动态分表 `journal_{book_name}` 数据
- **Files**: `backend/migrate_data.py`（新建）
- **Verify**: 脚本执行无错误

### 4. 执行数据迁移并验证
- **What**: 运行迁移脚本，检查 MySQL 中数据完整性
- **Files**: `backend/migrate_data.py`
- **Verify**: MySQL 中表结构正确，数据行数一致

### 5. 启动项目验证功能正常
- **What**: 启动后端服务，确认前端能正常访问数据
- **Files**: 无
- **Verify**: 后端无报错启动，前端正常加载数据

## Success Criteria
- MySQL 数据库中包含完整的 `books`、`balance_subjects`、`journal_entries` 及动态分表
- 数据行数与 SQLite 一致
- 后端以 MySQL 模式正常启动
- 前端功能正常

## Risks & Mitigations
- **动态分表迁移**：分表不在 `Base.metadata` 中，需要单独处理。方案：先读取 SQLite 中所有 `journal_*` 表名，为每个表在 MySQL 中建表并迁移数据
- **MySQL 服务未安装/未启动**：先检查 MySQL 可用性，如不可用则提示用户
- **字符编码**：MySQL 使用 `utf8mb4`，已在代码中配置 `charset=utf8mb4`