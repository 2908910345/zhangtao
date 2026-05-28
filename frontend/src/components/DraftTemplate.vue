<template>
  <div class="draft-template">
    <!-- 模板选择视图 -->
    <div class="template-selector" v-if="!activeTemplate">
      <div class="selector-header">
        <h3>审计工作底稿</h3>
        <p class="selector-desc">选择底稿模板，系统自动填入科目余额表数据</p>
      </div>

      <div class="category-tabs">
        <el-radio-group v-model="activeCategory" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="资产">资产</el-radio-button>
          <el-radio-button value="负债">负债</el-radio-button>
          <el-radio-button value="权益">权益</el-radio-button>
          <el-radio-button value="损益">损益</el-radio-button>
        </el-radio-group>
        <el-checkbox v-model="showWithData" size="small">仅显示有数据的</el-checkbox>
      </div>

      <!-- 标准底稿模板 -->
      <div class="section-label">
        <span class="label-text">标准底稿模板</span>
        <el-button v-if="filteredAccountTemplates.length > 0" size="small" text type="primary" @click="showAccountDetail = !showAccountDetail">
          {{ showAccountDetail ? '收起按科目展开 ▲' : '按科目展开 ▼' }}
        </el-button>
      </div>
      <div class="template-grid" v-show="!showAccountDetail">
        <div
          v-for="tpl in filteredTemplates"
          :key="tpl.code"
          class="template-card"
          :class="{ 'no-data': !tpl.has_data }"
          @click="tpl.has_data && handleSelectTemplate(tpl)"
        >
          <div class="card-category" :class="'cat-' + tpl.category">{{ tpl.category }}</div>
          <div class="card-body">
            <div class="card-name">{{ tpl.name }}</div>
            <div class="card-meta">{{ tpl.row_count }} 行</div>
          </div>
          <div v-if="!tpl.has_data" class="card-badge">无数据</div>
        </div>
      </div>

      <!-- 按科目展开的明细底稿 -->
      <div v-show="showAccountDetail" class="section-label" style="margin-top: 14px;">
        <span class="label-text">按一级科目展开的明细底稿</span>
        <el-button size="small" text type="primary" @click="showAccountDetail = false">收起 ▲</el-button>
      </div>
      <div class="template-grid" v-show="showAccountDetail">
        <div
          v-for="tpl in filteredAccountTemplates"
          :key="tpl.code"
          class="template-card account-card"
          @click="handleSelectTemplate(tpl)"
        >
          <div class="card-category" :class="'cat-' + tpl.category">{{ tpl.category }}</div>
          <div class="card-body">
            <div class="card-name">{{ tpl.name }}</div>
            <div class="card-meta">
              <template v-if="tpl.detail_info">
                {{ tpl.detail_info.has_sub_accounts ? '有子科目' : '' }}
                {{ tpl.detail_info.dim_count > 0 ? `${tpl.detail_info.dim_count}个维度` : '' }}
                {{ !tpl.detail_info.has_sub_accounts && tpl.detail_info.dim_count === 0 ? '无明细' : '' }}
              </template>
            </div>
          </div>
          <div class="card-badge account-badge">明细</div>
        </div>
      </div>
    </div>

    <!-- 模板内容视图 -->
    <div class="template-content" v-else v-loading="loading">
      <div class="content-header">
        <el-button size="small" @click="handleBack" text>
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h3>{{ templateData.name }}</h3>
        <el-tag size="small" :type="categoryTagType">{{ templateData.category }}</el-tag>
        <div class="header-tabs">
          <el-radio-group v-model="subTab" size="small">
            <el-radio-button value="audit">审定表</el-radio-button>
            <el-radio-button value="detail">明细表</el-radio-button>
          </el-radio-group>
        </div>
        <el-button size="small" type="primary" @click="handleExport">
          <el-icon><Download /></el-icon> 导出
        </el-button>
        <el-tag v-if="adjustmentSaved" type="success" size="small" class="save-tag">已保存</el-tag>
        <el-tag v-else-if="adjustmentDirty" type="warning" size="small" class="save-tag">未保存</el-tag>
      </div>

      <!-- 审定表 -->
      <div v-show="subTab === 'audit'">
        <table class="draft-table" v-if="templateData.rows">
          <thead>
            <tr>
              <th class="col-label">项目</th>
              <th v-for="col in templateData.columns" :key="col.key" class="col-value">
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(row, idx) in templateData.rows" :key="idx">
              <tr :class="rowClass(row)">
                <td class="col-label">
                  <span :class="labelClass(row)">{{ row.label }}</span>
                </td>
                <td v-for="col in templateData.columns" :key="col.key" class="col-value">
                  <!-- 未审数：使用后端计算值 -->
                  <template v-if="col.source === 'end_balance'">
                    {{ formatAmount(row.values.unaudited || 0) }}
                  </template>
                  <!-- 调整借方/贷方：可编辑输入框 -->
                  <template v-else-if="col.source === 'adjustment_debit'">
                    <el-input-number
                      v-if="!row.is_total && !row.is_net"
                      v-model="adjustments[row.code].adj_debit"
                      size="small"
                      :controls="false"
                      :precision="2"
                      :min="0"
                      @change="onAdjustmentChange"
                      class="adj-input"
                    />
                    <span v-else class="computed-value">—</span>
                  </template>
                  <template v-else-if="col.source === 'adjustment_credit'">
                    <el-input-number
                      v-if="!row.is_total && !row.is_net"
                      v-model="adjustments[row.code].adj_credit"
                      size="small"
                      :controls="false"
                      :precision="2"
                      :min="0"
                      @change="onAdjustmentChange"
                      class="adj-input"
                    />
                    <span v-else class="computed-value">—</span>
                  </template>
                  <!-- 审定数：动态计算 -->
                  <template v-else-if="col.source === 'audited_balance'">
                    <span class="computed-value">{{ formatAmount(row.values.audited || 0) }}</span>
                  </template>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 明细表：层级结构 -->
      <div v-show="subTab === 'detail'" v-loading="hierarchyLoading">
        <template v-if="hierarchyData && hierarchyData.rows && hierarchyData.rows.length > 0">
          <div class="detail-header">
            <h4>{{ hierarchyData.template_name }} · 明细表</h4>
            <el-switch
              v-model="openingDebitPositive"
              style="margin-left: 8px"
              size="small"
              active-text="借方为正"
              inactive-text="贷方为正"
              @change="handleOpeningSignChange"
            />
            <el-tag size="small" :type="categoryTagType">{{ hierarchyData.category }}</el-tag>
          </div>

          <table class="hierarchy-table">
            <thead>
              <tr>
                <th class="h-col-name" style="width:40px">层级</th>
                <th class="h-col-name">单位名称</th>
                <th class="h-col-name">款项性质</th>
                <th class="h-col-amount">期初金额</th>
                <th class="h-col-amount">借方发生额</th>
                <th class="h-col-amount">贷方发生额</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(row, idx) in hierarchyData.rows" :key="idx">
                <tr :class="{ 'h-row-total': row.is_total }">
                  <td class="h-col-level">{{ row.level }}</td>
                  <td class="h-col-name" :style="{ paddingLeft: (20 + row.level * 16) + 'px' }">
                    <span :class="{ 'h-label-total': row.is_total }">{{ row.unit_name }}</span>
                  </td>
                  <td class="h-col-name">{{ row.nature }}</td>
                  <td class="h-col-amount">{{ formatAmount(row.opening) }}</td>
                  <td class="h-col-amount debit">{{ formatAmount(row.debit) }}</td>
                  <td class="h-col-amount credit">{{ formatAmount(row.credit) }}</td>
                </tr>
              </template>
            </tbody>
            <tfoot v-if="hierarchyData.total_row">
              <tr class="h-row-grand-total">
                <td class="h-col-level">—</td>
                <td class="h-col-name" style="paddingLeft: 20px">
                  <strong>{{ hierarchyData.total_row.unit_name }}</strong>
                </td>
                <td class="h-col-name"><strong>{{ hierarchyData.total_row.nature }}</strong></td>
                <td class="h-col-amount"><strong>{{ formatAmount(hierarchyData.total_row.opening) }}</strong></td>
                <td class="h-col-amount debit"><strong>{{ formatAmount(hierarchyData.total_row.debit) }}</strong></td>
                <td class="h-col-amount credit"><strong>{{ formatAmount(hierarchyData.total_row.credit) }}</strong></td>
              </tr>
            </tfoot>
          </table>
        </template>

        <div v-else-if="!hierarchyLoading" class="empty-state">
          <el-icon :size="40"><InfoFilled /></el-icon>
          <p>暂无明细数据</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ArrowLeft, Download } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { listDraftTemplates, getDraftTemplate, getTemplateAdjustments, saveTemplateAdjustments, getDetailHierarchy } from '../api/index.js'
import ExcelJS from 'exceljs'

const templates = ref([])
const accountTemplates = ref([])
const showAccountDetail = ref(false)
const activeTemplate = ref(null)
const templateData = ref({})
const loading = ref(false)
const adjustments = reactive({})
const adjustmentDirty = ref(false)
const adjustmentSaved = ref(true)
const saveTimer = ref(null)
const subTab = ref('audit')
const hierarchyData = ref(null)
const hierarchyLoading = ref(false)
const openingDebitPositive = ref(true)  // true=借方为正, false=贷方为正
const activeCategory = ref('all')
const showWithData = ref(false)

onMounted(async () => {
  try {
    const data = await listDraftTemplates()
    templates.value = data.templates || []
    accountTemplates.value = data.account_templates || []
  } catch {}
})

// ==================== 模板过滤 ====================

const filteredTemplates = computed(() => {
  let list = templates.value
  if (activeCategory.value !== 'all') {
    list = list.filter(t => t.category === activeCategory.value)
  }
  if (showWithData.value) {
    list = list.filter(t => t.has_data)
  }
  return list
})

const showDetailTemplates = computed(() => {
  if (showAccountDetail.value) return true
  // 当选择了全部或具体分类，且有 account_templates 时显示切换按钮
  return accountTemplates.value.length > 0
})

const filteredAccountTemplates = computed(() => {
  let list = accountTemplates.value
  if (activeCategory.value !== 'all') {
    list = list.filter(t => t.category === activeCategory.value)
  }
  return list
})

const categoryTagType = computed(() => {
  const map = { '资产': '', '负债': 'danger', '权益': 'warning', '损益': 'success' }
  return map[templateData.value.category] || 'info'
})

// ==================== 选择/切换模板 ====================

async function handleSelectTemplate(tpl) {
  activeTemplate.value = tpl
  subTab.value = tpl.is_account_detail ? 'detail' : 'audit'
  loading.value = true
  hierarchyData.value = null

  if (!tpl.is_account_detail) {
    try {
      const data = await getDraftTemplate(tpl.code)
      templateData.value = data
      initAdjustments()
      await loadAdjustments()
    } catch {} finally {
      loading.value = false
    }
  } else {
    // 科目级模板：直接用科目名称作为模板名，仅展示明细表
    templateData.value = {
      name: tpl.name,
      code: tpl.code,
      category: tpl.category || '',
      columns: [],
      rows: [],
    }
    loading.value = false
  }
  // 加载层级明细
  await loadHierarchy()
}

function handleBack() {
  // 退出前自动保存
  if (adjustmentDirty.value && activeTemplate.value) {
    saveAdjustmentsNow()
  }
  activeTemplate.value = null
  templateData.value = {}
  hierarchyData.value = null
  // 清空 adjustments
  Object.keys(adjustments).forEach(k => delete adjustments[k])
}

async function loadHierarchy() {
  if (!activeTemplate.value) return
  hierarchyLoading.value = true
  const sign = openingDebitPositive.value ? 'debit' : 'credit'
  try {
    hierarchyData.value = await getDetailHierarchy(activeTemplate.value.code, sign)
  } catch {
    hierarchyData.value = null
  } finally {
    hierarchyLoading.value = false
  }
}

function handleOpeningSignChange(val) {
  if (!activeTemplate.value) return
  loadHierarchy()
}

// ==================== 调整值管理 ====================

function initAdjustments() {
  // 为每个数据行初始化调整值
  for (const row of templateData.value.rows) {
    if (!row.is_total && !row.is_net && row.code) {
      if (!adjustments[row.code]) {
        adjustments[row.code] = { adj_debit: 0, adj_credit: 0 }
      }
    }
  }
}

async function loadAdjustments() {
  if (!activeTemplate.value) return
  try {
    const data = await getTemplateAdjustments(activeTemplate.value.code)
    const saved = data.adjustments || {}
    for (const [code, adj] of Object.entries(saved)) {
      if (adjustments[code]) {
        adjustments[code].adj_debit = adj.adj_debit || 0
        adjustments[code].adj_credit = adj.adj_credit || 0
      } else {
        adjustments[code] = { adj_debit: adj.adj_debit || 0, adj_credit: adj.adj_credit || 0 }
      }
    }
    // 加载后重新计算
    recalcAll()
    adjustmentDirty.value = false
    adjustmentSaved.value = true
  } catch {
    // 没有保存的调整值，用默认0
    adjustmentDirty.value = false
    adjustmentSaved.value = true
  }
}

function onAdjustmentChange() {
  adjustmentDirty.value = true
  adjustmentSaved.value = false
  recalcAll()

  // 防抖自动保存
  if (saveTimer.value) clearTimeout(saveTimer.value)
  saveTimer.value = setTimeout(() => {
    saveAdjustmentsNow()
  }, 2000)
}

async function saveAdjustmentsNow() {
  if (!activeTemplate.value || !adjustmentDirty.value) return

  // 只保存有非零调整的行
  const adjData = {}
  for (const [code, adj] of Object.entries(adjustments)) {
    if (adj.adj_debit || adj.adj_credit) {
      adjData[code] = { adj_debit: adj.adj_debit, adj_credit: adj.adj_credit }
    }
  }

  try {
    await saveTemplateAdjustments(activeTemplate.value.code, adjData)
    adjustmentDirty.value = false
    adjustmentSaved.value = true
  } catch {
    adjustmentSaved.value = false
  }
}

// ==================== 核心计算引擎 ====================

function recalcAll() {
  const rows = templateData.value.rows
  if (!rows) return

  // Step 1: 计算所有数据行的审定数
  for (const row of rows) {
    if (row.is_total || row.is_net) continue
    const unaudited = row.values.unaudited || 0
    const adj = adjustments[row.code]
    const adjDebit = adj?.adj_debit || 0
    const adjCredit = adj?.adj_credit || 0
    row.values.audited = round(unaudited + adjDebit - adjCredit, 2)
  }

  // Step 2: 计算合计/净额行的审定数（基于公式）
  for (const row of rows) {
    if (!row.is_total && !row.is_net) continue
    row.values.audited = computeFormulaValue(row)
  }
}

/**
 * 根据公式计算某行的审定数
 * 公式规则：
 * - 有 source_rows 时：遍历 source_rows，每行的审定数 × 该行的 sign，累加
 * - is_total 无 source_rows 时：汇总所有前序数据行的审定数 × sign
 */
function computeFormulaValue(row) {
  const rows = templateData.value.rows
  const sourceRows = row.source_rows
  const rowIndex = rows.indexOf(row)

  if (sourceRows && sourceRows.length > 0) {
    // 显式公式
    let total = 0
    for (const srcCode of sourceRows) {
      const srcRow = rows.find(r => r.code === srcCode)
      if (srcRow) {
        const srcSign = srcRow.sign || 1
        const srcAudited = srcRow.values.audited || 0
        total += srcAudited * srcSign
      }
    }
    return round(total, 2)
  }

  if (row.is_total) {
    // 隐式合计：前序所有数据行
    let total = 0
    for (let j = 0; j < rowIndex; j++) {
      const prev = rows[j]
      if (prev.is_total || prev.is_net) continue
      total += (prev.values.audited || 0) * (prev.sign || 1)
    }
    return round(total, 2)
  }

  return row.values.unaudited || 0
}

// ==================== 样式辅助 ====================

function rowClass(row) {
  if (row.is_net) return 'row-net'
  if (row.is_total) return 'row-total'
  return ''
}

function labelClass(row) {
  if (row.is_net) return 'label-net'
  if (row.is_total) return 'label-total'
  return 'label-indent'
}

// ==================== 导出 Excel ====================

async function handleExport() {
  // 明细表导出
  if (subTab.value === 'detail' && hierarchyData.value) {
    await exportHierarchyExcel()
    return
  }

  await saveAdjustmentsNow()

  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet(templateData.value.name || '审定表')

  // 标题行
  ws.mergeCells('A1:E1')
  const titleCell = ws.getCell('A1')
  titleCell.value = `${templateData.value.name} 审定表`
  titleCell.font = { bold: true, size: 14 }
  titleCell.alignment = { horizontal: 'center' }

  // 表头
  const headers = ['项目', ...templateData.value.columns.map(c => c.label)]
  ws.addRow(headers)
  const headerRow = ws.getRow(2)
  headerRow.font = { bold: true, size: 11 }
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F0FE' } }
  headerRow.alignment = { horizontal: 'center' }

  // 数据行
  for (let i = 0; i < templateData.value.rows.length; i++) {
    const row = templateData.value.rows[i]
    const rowData = [row.label]

    for (const col of templateData.value.columns) {
      if (col.source === 'end_balance') {
        rowData.push(row.values.unaudited || 0)
      } else if (col.source === 'adjustment_debit') {
        if (row.is_total || row.is_net) {
          rowData.push(0)
        } else {
          rowData.push(adjustments[row.code]?.adj_debit || 0)
        }
      } else if (col.source === 'adjustment_credit') {
        if (row.is_total || row.is_net) {
          rowData.push(0)
        } else {
          rowData.push(adjustments[row.code]?.adj_credit || 0)
        }
      } else if (col.source === 'audited_balance') {
        rowData.push(row.values.audited || 0)
      }
    }

    const excelRow = ws.addRow(rowData)
    if (row.is_total || row.is_net) {
      excelRow.font = { bold: true }
    }
  }

  // 列宽 + 数字格式
  ws.getColumn(1).width = 24
  for (let c = 2; c <= headers.length; c++) {
    ws.getColumn(c).width = 18
    for (let r = 3; r <= ws.rowCount; r++) {
      const cell = ws.getCell(r, c)
      cell.numFmt = '#,##0.00'
    }
  }

  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${templateData.value.name}_审定表.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

// ==================== 明细表导出 ====================

async function exportHierarchyExcel() {
  if (!hierarchyData.value) return
  const hd = hierarchyData.value

  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet(`${hd.template_name}明细表`)

  // 标题行
  ws.mergeCells('A1:F1')
  const titleCell = ws.getCell('A1')
  titleCell.value = `${hd.template_name} 明细表`
  titleCell.font = { bold: true, size: 14 }
  titleCell.alignment = { horizontal: 'center' }

  // 表头
  const headers = ['层级', '单位名称', '款项性质', '期初金额', '借方发生额', '贷方发生额']
  ws.addRow(headers)
  const headerRow = ws.getRow(2)
  headerRow.font = { bold: true, size: 11 }
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F0FE' } }
  headerRow.alignment = { horizontal: 'center' }

  // 数据行
  for (const row of hd.rows || []) {
    ws.addRow([row.level, row.unit_name, row.nature, row.opening, row.debit, row.credit])
  }

  // 总计行
  if (hd.total_row) {
    const t = hd.total_row
    const totalExcelRow = ws.addRow(['—', t.unit_name, t.nature, t.opening, t.debit, t.credit])
    totalExcelRow.font = { bold: true }
  }

  // 列宽 + 数字格式
  ws.getColumn(1).width = 8   // 层级
  ws.getColumn(2).width = 26  // 单位名称
  ws.getColumn(3).width = 20  // 款项性质
  for (let c = 4; c <= 6; c++) {
    ws.getColumn(c).width = 18
    for (let r = 3; r <= ws.rowCount; r++) {
      ws.getCell(r, c).numFmt = '#,##0.00'
    }
  }

  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${hd.template_name}_明细表.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

// ==================== 工具函数 ====================

function round(val, decimals = 2) {
  const factor = Math.pow(10, decimals)
  return Math.round(val * factor) / factor
}
</script>

<style scoped>
.draft-template { height: 100%; }

.template-selector {
  display: flex; flex-direction: column; align-items: center;
  padding: 24px 20px;
}

.selector-header { text-align: center; margin-bottom: 20px; }
.selector-header h3 { font-size: 18px; color: #303133; margin: 0 0 6px; }
.selector-desc { font-size: 13px; color: #909399; margin: 0; }

.category-tabs {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 20px; width: 100%; max-width: 900px;
  justify-content: center;
}

.template-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px; width: 100%; max-width: 900px;
}

.template-card {
  display: flex; align-items: stretch; gap: 0;
  border-radius: 8px; border: 1px solid #ebeef5;
  cursor: pointer; transition: all 0.2s; overflow: hidden;
  position: relative;
}
.template-card:hover:not(.no-data) {
  border-color: #409eff; box-shadow: 0 2px 12px rgba(64,158,255,0.12);
  transform: translateY(-1px);
}
.template-card.no-data {
  opacity: 0.5; cursor: not-allowed;
}

.card-category {
  writing-mode: vertical-lr; text-orientation: mixed;
  font-size: 11px; font-weight: 600; padding: 8px 4px;
  display: flex; align-items: center; justify-content: center;
  min-width: 24px; letter-spacing: 2px;
  color: #fff;
}
.cat-资产 { background: #409eff; }
.cat-负债 { background: #f56c6c; }
.cat-权益 { background: #e6a23c; }
.cat-损益 { background: #67c23a; }

.card-body {
  flex: 1; padding: 12px 14px;
  display: flex; flex-direction: column; justify-content: center;
}
.card-name { font-size: 13px; font-weight: 600; color: #303133; }
.card-meta { font-size: 11px; color: #909399; margin-top: 4px; }

.card-badge {
  position: absolute; top: 4px; right: 4px;
  font-size: 10px; color: #c0c4cc; background: #f5f7fa;
  padding: 1px 6px; border-radius: 3px;
}

.template-content { height: 100%; }

.content-header {
  display: flex; align-items: center; gap: 10px;
  padding-bottom: 14px; border-bottom: 2px solid #e8f0fe; margin-bottom: 16px;
}
.content-header h3 { font-size: 16px; margin: 0; }
.header-tabs { flex: 1; }

.save-tag { margin-left: auto; }

.detail-subject-selector {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 16px; padding: 10px 14px;
  background: #f8f9fb; border-radius: 8px;
}
.selector-label { font-size: 13px; color: #606266; font-weight: 500; white-space: nowrap; }

.draft-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}

.draft-table th, .draft-table td {
  border: 1px solid #ebeef5; padding: 10px 12px; text-align: right;
}

.draft-table th {
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
  font-weight: 600; color: #606266;
  text-align: center; font-size: 12px;
}

.draft-table .col-label {
  text-align: left; min-width: 160px; background: #fafbfc;
}

.draft-table .col-value { min-width: 120px; }

.draft-table .row-total td {
  background: #f5f7fa; font-weight: 600;
  border-top: 2px solid #dcdfe6;
}

.draft-table .row-net td {
  background: #edf7ed; font-weight: 700;
  border-top: 2px double #67c23a;
}

.label-indent { padding-left: 12px; }
.label-total { font-weight: 600; }
.label-net { font-weight: 700; }

.adj-input { width: 100%; }
.adj-input :deep(.el-input__inner) { text-align: right; padding: 0 4px; }

.computed-value {
  font-family: 'SF Mono', Consolas, monospace;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

/* ==================== 层级明细表样式 ==================== */

.detail-header {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px;
}
.detail-header h4 { font-size: 15px; margin: 0; color: #303133; }

.hierarchy-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}

.hierarchy-table th, .hierarchy-table td {
  border: 1px solid #ebeef5; padding: 8px 10px; text-align: right;
}

.hierarchy-table th {
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
  font-weight: 600; color: #606266; text-align: center; font-size: 12px;
}

.h-col-level { text-align: center; width: 40px; color: #909399; font-size: 11px; }
.h-col-name { text-align: left; min-width: 120px; }
.h-col-amount {
  min-width: 120px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.h-col-amount.debit { color: #303133; }
.h-col-amount.credit { color: #e23c3c; }

.h-row-total td {
  background: #f5f7fa; font-weight: 600;
  border-top: 1px solid #dcdfe6;
}

.h-row-grand-total td {
  background: #e8f0fe; font-weight: 700;
  border-top: 2px solid #409eff;
}

.h-label-total { font-weight: 600; }

/* ==================== 按科目展开样式 ==================== */

.section-label {
  display: flex; align-items: center; justify-content: center; gap: 12px;
  margin-bottom: 12px; width: 100%; max-width: 900px;
}
.section-label .label-text {
  font-size: 13px; color: #606266; font-weight: 500;
}

.account-card {
  border: 1px dashed #c0c4cc !important;
}
.account-card:hover {
  border-color: #67c23a !important;
  box-shadow: 0 2px 12px rgba(103,194,58,0.15) !important;
}
.account-badge {
  background: #e8f8e8 !important;
  color: #67c23a !important;
}
</style>
