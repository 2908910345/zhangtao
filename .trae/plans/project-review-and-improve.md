# Plan: 项目审查与改进

## Goal
对账套管理系统进行全面代码审查，识别并修复安全问题、代码质量问题、架构问题，提升项目整体质量。

## Context
项目是一个前后端分离的账套管理系统，后端使用 FastAPI + SQLAlchemy (async)，前端使用 Vue 3 + Element Plus。当前版本 v2.0.0。

## 发现的问题（按严重程度排序）

### 🔴 严重安全问题
1. **SQL 注入风险** - `balance.py`、`export.py`、`books.py` 中使用 f-string 拼接 SQL
2. **`.env` 包含明文密码** - 数据库密码暴露在版本控制中
3. **缺少 `.gitignore`** - `__pycache__`、`dist`、数据文件等被提交

### 🟡 数据完整性问题
4. **使用 Float 存储金额** - 浮点数精度问题，应使用 Numeric/Decimal
5. **`save-as` 硬编码源账套为 "default"** - 应使用当前激活账套

### 🟠 代码质量问题
6. **`parser.py` 中 `vars()` 误用** - `vars()[debit_var] = c` 无效，是死代码
7. **`parse_journal` 函数未使用** - 只有 `parse_journal_streaming` 被调用
8. **`_count_subjects_and_vouchers` 未使用** - `books.py` 中的死代码
9. **序时账序列化代码重复3次** - `journal.py` 中相同的字典构建逻辑
10. **`datetime.utcnow()` 已弃用** - Python 3.12+ 应使用 `datetime.now(UTC)`
11. **`get_db` 自动提交** - GET 请求也会触发 commit，效率低下
12. **`migrate_data.py` 硬编码密码** - 与 `.env` 重复

### 🔵 前端问题
13. **`xlsx` 包未使用** - `package.json` 中引入但代码使用 `exceljs`
14. **`exportToExcel` 中 URL 过早释放** - 可能导致下载失败
15. **CORS 配置过于宽松** - `allow_methods=["*"]` 和 `allow_headers=["*"]`

### ⚪ 项目结构问题
16. **根目录有数据文件** - `.xlsx` 文件不应在仓库中
17. **`analyze_excel.py`** - 独立脚本不应在主项目中

## Steps

### 1. 创建 .gitignore 并清理不应提交的文件
- **What**: 创建 `.gitignore`，排除 `__pycache__`、`.env`、`dist`、数据文件等
- **Files**: `.gitignore`（新建）
- **Verify**: 文件存在且规则正确

### 2. 修复 SQL 注入风险
- **What**: 将 f-string SQL 替换为参数化查询或 SQLAlchemy ORM 方法
- **Files**: `backend/routers/balance.py`, `backend/routers/export.py`, `backend/routers/books.py`, `backend/routers/journal.py`
- **Verify**: 所有 SQL 构造不再使用 f-string 拼接用户输入

### 3. 修复 Float 金额精度问题
- **What**: 将 `Float` 替换为 `Numeric(precision=18, scale=2)` 用于所有金额字段
- **Files**: `backend/models.py`, `backend/database.py`
- **Verify**: 金额字段使用 Decimal 类型

### 4. 清理死代码和重复代码
- **What**: 移除 `vars()` 误用、未使用的函数、提取公共序列化逻辑
- **Files**: `backend/services/parser.py`, `backend/routers/journal.py`, `backend/routers/books.py`
- **Verify**: 无死代码，无重复逻辑

### 5. 修复 save-as 硬编码问题
- **What**: `save_current_as` 应从当前激活账套复制，而非硬编码 "default"
- **Files**: `backend/routers/books.py`
- **Verify**: save-as 使用当前激活账套

### 6. 修复其他问题
- **What**: 修复 `datetime.utcnow()`、`get_db` 自动提交、CORS 配置、移除未使用的 `xlsx` 包、修复导出 URL 释放
- **Files**: `backend/routers/books.py`, `backend/database.py`, `backend/main.py`, `frontend/package.json`, `frontend/src/utils/export.js`
- **Verify**: 所有修复正确

## Success Criteria
- 无 SQL 注入风险
- 金额字段使用 Decimal 类型
- 无死代码和重复代码
- `.gitignore` 正确配置
- 所有其他问题已修复

## Risks & Mitigations
- Float → Numeric 可能需要数据库迁移 → 添加迁移说明
- SQL 重构可能影响功能 → 保持 API 接口不变
