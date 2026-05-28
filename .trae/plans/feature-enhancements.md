# Plan: 功能增强 - 底稿模板、凭证簿、备份恢复、快捷操作

## Goal ✅
为账套管理系统添加4个核心功能：底稿模板系统、凭证簿/凭证列表、数据备份与恢复、快捷操作与搜索。

## Status: 全部完成 ✅

### 1. 凭证簿/凭证列表 ✅
- 后端: `GET /api/vouchers` 端点（分页、期间筛选、关键词搜索）
- 前端: `VoucherBook.vue` 组件（表格展示、期间筛选、借贷平衡检查、分页）
- 集成到 App.vue 的 tab 栏

### 2. 数据备份与恢复 ✅
- 后端: `GET /api/books/{name}/backup` 导出JSON备份、`POST /api/books/restore` 从备份恢复
- 前端: BookManager 中添加"备份"按钮和"从备份恢复"按钮
- 备份格式: JSON（含版本号、账套信息、科目数据、序时账数据）

### 3. 快捷操作与搜索 ✅
- 全局搜索: Ctrl+K 打开搜索对话框，支持科目编码/名称搜索
- 最近查看历史: 双击科目自动记录，localStorage 持久化
- 快捷键: Ctrl+K 搜索、Escape 关闭对话框

### 4. 底稿模板系统 ✅
- 5个预置模板: 货币资金、应收账款、应付账款、固定资产、营业收入
- 后端: `GET /api/draft-templates` 列表、`GET /api/draft-templates/{code}` 获取模板数据
- 前端: `DraftTemplate.vue` 组件（模板选择、自动填入、调整分录输入、审定数自动计算、导出Excel）
