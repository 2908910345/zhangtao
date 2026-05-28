# 项目审查报告

## 目标
全面审查项目代码，识别所有问题并按严重程度分类。

---

## 严重问题（运行时崩溃）

### B1. adjustments.py 字段名不匹配 — 运行时 ValidationError
- **文件**: `backend/routers/adjustments.py` 第33行
- **问题**: 传入 `adjustments=list(adjustments)`，但 `AdjustmentListResponse` schema 的字段名是 `entries`
- **修复**: 将 `adjustments=` 改为 `entries=`

### B2. SubjectTreeNode 缺少 has_children 字段 — 数据静默丢失
- **文件**: `backend/schemas.py` 第54-66行, `backend/routers/balance.py` 第151、185行
- **问题**: `balance.py` 传入 `has_children=...`，但 `SubjectTreeNode` 没有定义该字段，Pydantic 静默丢弃
- **修复**: 在 `SubjectTreeNode` 中添加 `has_children: bool = False`

### B3. 前端缺少14个 API 函数 — 多个功能完全不可用
- **文件**: `frontend/src/api/index.js`
- **缺失函数**:
  | 函数名 | 后端端点 | 使用组件 |
  |--------|----------|----------|
  | `searchSubjects` | `GET /api/subjects/search` | App.vue |
  | `getAdjustments` | `GET /api/adjustments` | AdjustmentPanel.vue |
  | `createAdjustment` | `POST /api/adjustments` | AdjustmentPanel.vue |
  | `updateAdjustment` | `PUT /api/adjustments/{id}` | AdjustmentPanel.vue |
  | `deleteAdjustment` | `DELETE /api/adjustments/{id}` | AdjustmentPanel.vue |
  | `clearAdjustments` | `DELETE /api/adjustments` | AdjustmentPanel.vue |
  | `getTrialBalance` | `GET /api/trial-balance` | TrialBalance.vue |
  | `getVoucherBook` | `GET /api/vouchers` | VoucherBook.vue |
  | `listDraftTemplates` | `GET /api/draft-templates` | DraftTemplate.vue |
  | `getDraftTemplate` | `GET /api/draft-templates/{code}` | DraftTemplate.vue |
  | `getDetailSchedule` | `GET /api/draft-templates/detail/{code}` | DetailSchedule.vue |
  | `getDetailDimensionTypes` | `GET /api/draft-templates/detail/{code}/dimensions` | DetailSchedule.vue |
  | `backupBook` | `GET /api/books/{name}/backup` | BookManager.vue |
  | `restoreBook` | `POST /api/books/restore` | BookManager.vue |

### B4. DraftTemplate 调用未暴露的方法 — TypeError
- **文件**: `frontend/src/components/DraftTemplate.vue` 第224行
- **问题**: 调用 `detailRef.value.handleExport()`，但 `DetailSchedule.vue` 只暴露了 `loadDimensions`
- **修复**: 在 `DetailSchedule.vue` 的 `defineExpose` 中添加 `handleExport`

---

## 高优先级问题（逻辑错误/数据不正确）

### H1. 试算平衡表调整数重复计算
- **文件**: `backend/routers/adjustments.py` 第183-186行
- **问题**: 遍历所有科目（含父子），调整分录同时匹配父科目和子科目，导致父科目重复计入子科目的调整
- **修复**: 只对末级科目计算调整数，父科目通过汇总子科目得出

### H2. restore_book 删除共享表但插入分账套表
- **文件**: `backend/routers/books.py` 第155、175-176行
- **问题**: 恢复时从 `JournalEntry.__table__`（共享表）删除，但插入到分账套动态表，导致旧数据残留
- **修复**: 同时删除分账套表中的旧数据

### H3. 明细表期初余额计算错误
- **文件**: `backend/routers/draft.py` 第272-274行
- **问题**: "其他"行的期初余额计算公式有误，维度行的期初余额始终为0
- **修复**: 重新设计期初余额计算逻辑

### H4. BookManager 保存后 saving 状态未重置
- **文件**: `frontend/src/components/BookManager.vue` 第167行
- **问题**: `handleSave()` 成功后 `saving.value` 未设为 `false`，按钮持续 loading
- **修复**: 添加 `finally { saving.value = false }`

### H5. VoucherView 对方科目分组逻辑错误
- **文件**: `frontend/src/components/VoucherView.vue` 第191-223行
- **问题**: 仅按 `summary` 分组，未考虑 `voucher_no`/`period`，不同凭证的相同摘要会被错误合并
- **修复**: 按 `voucher_no` + `summary` 联合分组

### H6. Element Plus 使用英文 locale
- **文件**: `frontend/src/main.js` 第13行
- **问题**: 中文应用使用了英文 locale，分页、日期选择等内置文本显示英文
- **修复**: 导入并使用 `zh-cn` locale

---

## 中优先级问题（功能不完整/不一致）

### M1. export.py 级次筛选逻辑错误
- **文件**: `backend/routers/export.py` 第73-78行
- **问题**: 用 `LIKE "%..%"` 匹配2级科目，实际匹配的是含两个连续点的编码
- **修复**: 改为统计点号数量来筛选级次

### M2. export.py 缺少年累计借方/贷方列
- **文件**: `backend/routers/export.py` 第87-88行
- **问题**: 导出 Excel 缺少 `year_total_debit` / `year_total_credit` 列

### M3. clear_all_data 不清除调整分录
- **文件**: `backend/routers/balance.py` 第326-342行
- **问题**: 清除数据时不删除 `AdjustmentEntry`，留下孤立数据

### M4. delete_book 不删除调整分录
- **文件**: `backend/routers/books.py` 第207-234行
- **问题**: 删除账套时不删除 `AdjustmentEntry`

### M5. export.py 重复 Content-Type 头
- **文件**: `backend/routers/export.py` 第18-21行
- **问题**: `StreamingResponse` 同时设置 `media_type` 和 `headers` 中的 `Content-Type`

### M6. draft.py 返回 200 + error 而非 404
- **文件**: `backend/routers/draft.py` 第38行
- **问题**: 模板不存在时返回 `{"error": "..."}` + HTTP 200，应返回 404

### M7. KeepAlive 与 v-if/v-else-if 链配合不可靠
- **文件**: `frontend/src/App.vue` 第72-124行
- **问题**: `<KeepAlive>` 配合7分支 `v-if/v-else-if` 只能缓存1个组件，切换时组件被销毁重建
- **修复**: 改用动态组件 `<component :is="...">` 配合 `<KeepAlive>`

### M8. VoucherBook 期间筛选显示范围字符串
- **文件**: `frontend/src/components/VoucherBook.vue` 第110-117行
- **问题**: `periodOptions` 设为范围字符串如 "2026年1期 ~ 2026年3期"，无法匹配实际期间

### M9. ImportPanel 清除后状态对象缺少 pending 字段
- **文件**: `frontend/src/components/ImportPanel.vue` 第153-158行
- **问题**: 清除时 emit 的状态对象缺少 `pending` 字段，与初始化形状不一致

### M10. DetailSchedule/DraftTemplate 直接用 ExcelJS 而非共享导出工具
- **文件**: `frontend/src/components/DetailSchedule.vue` 第67行, `DraftTemplate.vue` 第112行
- **问题**: 导出样式与其他组件不一致

---

## 低优先级问题（代码质量）

### L1. balance.py 内部延迟导入 JournalEntry
- **文件**: `backend/routers/balance.py` 第275、299、336行
- **问题**: 在函数内部 `from backend.models import JournalEntry`，应移到文件顶部

### L2. journal.py 导入了未使用的 get_journal_table_name
- **文件**: `backend/routers/journal.py` 第7行

### L3. BalanceSheet.vue 未使用的 tableRef
- **文件**: `frontend/src/components/BalanceSheet.vue` 第100行

### L4. api/index.js 死代码
- **文件**: `frontend/src/api/index.js` 第65-67、97-99行
- **问题**: `getSubjectBalance` 和 `saveAsBook` 定义但从未被导入使用

### L5. schemas.py datetime 类型注解不一致
- **文件**: `backend/schemas.py` 第144-145行 vs 第23、48、162行
- **问题**: `BookResponse` 用 `datetime | None`，其他用 `Optional[datetime]`

### L6. LIKE 查询未转义通配符
- **文件**: `backend/routers/balance.py` 第250-253行, `journal.py` 第193、431行
- **问题**: 用户输入的 `%`、`_` 会作为 LIKE 通配符

### L7. parser.py 异常时未关闭 workbook
- **文件**: `backend/services/parser.py` 第42-178行
- **问题**: `ValueError` 时 `wb` 未关闭，应使用 `try/finally`

### L8. 数据库会话管理不一致
- **文件**: 多个路由文件
- **问题**: 部分用 `Depends(get_db)`，部分自建 session，部分用 `engine.connect()`

---

## 修复优先级建议

1. **立即修复**: B1, B2, B3, B4（运行时崩溃）
2. **尽快修复**: H1-H6（逻辑错误/数据不正确）
3. **计划修复**: M1-M10（功能不完整）
4. **择机修复**: L1-L8（代码质量）
