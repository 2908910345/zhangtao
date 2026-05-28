<template>
  <div class="detail-schedule" v-loading="loading">
    <div v-if="!subjectCode" class="empty-state">
      <el-icon :size="40"><Memo /></el-icon>
      <p>请在底稿模板中选择科目查看明细表</p>
    </div>

    <template v-else-if="data.rows && data.rows.length > 0">
      <div class="schedule-header">
        <div class="header-info">
          <h3>{{ data.subject_name }} · 明细表</h3>
          <el-select v-model="selectedDimType" size="small" style="width: 120px" @change="handleDimTypeChange">
            <el-option v-for="dt in dimTypes" :key="dt" :label="dt" :value="dt" />
          </el-select>
          <el-switch
            v-model="openingDebitPositive"
            style="margin-left: 8px"
            active-text="借方为正"
            inactive-text="贷方为正"
            @change="handleOpeningSignChange"
          />
          <el-tag v-if="data.reconciled" type="success" size="small">已勾稽</el-tag>
          <el-tag v-else type="danger" size="small">未勾稽</el-tag>
        </div>
        <el-button size="small" type="primary" @click="handleExport">
          <el-icon><Download /></el-icon> 导出Excel
        </el-button>
      </div>

      <table class="schedule-table">
        <thead>
          <tr>
            <th class="col-name">{{ data.dimension_type }}</th>
            <th class="col-amount">期初数</th>
            <th class="col-amount">借方发生额</th>
            <th class="col-amount">贷方发生额</th>
            <th class="col-amount">期末数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in data.rows" :key="idx" :class="{ 'row-other': row.name === '其他' }">
            <td class="col-name">{{ row.name }}</td>
            <td class="col-amount">{{ formatAmount(row.opening) }}</td>
            <td class="col-amount debit">{{ formatAmount(row.debit) }}</td>
            <td class="col-amount credit">{{ formatAmount(row.credit) }}</td>
            <td class="col-amount">{{ formatAmount(row.closing) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="row-total">
            <td class="col-name">合计（科目余额表）</td>
            <td class="col-amount">{{ formatAmount(data.ctrl_opening) }}</td>
            <td class="col-amount debit">{{ formatAmount(data.ctrl_debit) }}</td>
            <td class="col-amount credit">{{ formatAmount(data.ctrl_credit) }}</td>
            <td class="col-amount">{{ formatAmount(data.ctrl_closing) }}</td>
          </tr>
        </tfoot>
      </table>
    </template>

    <div v-else-if="loaded && dimTypes.length === 0" class="empty-state">
      <el-icon :size="40"><WarningFilled /></el-icon>
      <p>该科目暂无维度数据</p>
      <p class="empty-hint">请确保科目余额表中的核算维度字段包含维度信息（如"客商:张三"或"部门:财务部;客商:甲公司"）</p>
    </div>

    <div v-else-if="loaded && dimTypes.length > 0" class="empty-state">
      <el-icon :size="40"><InfoFilled /></el-icon>
      <p>该科目有维度数据，但未匹配到明细行</p>
      <p class="empty-hint">当前维度类型：{{ selectedDimType }}，共有 {{ dimTypes.length }} 种维度类型可供选择</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Memo, Download, WarningFilled, InfoFilled } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { getDetailSchedule, getDetailDimensionTypes } from '../api/index.js'
import ExcelJS from 'exceljs'

const props = defineProps({
  subjectCode: { type: String, default: '' },
  dimensionType: { type: String, default: '' },
})

const data = ref({})
const loading = ref(false)
const loaded = ref(false)
const dimTypes = ref([])
const selectedDimType = ref('')
const openingDebitPositive = ref(true)  // true=借方为正, false=贷方为正

watch(() => props.subjectCode, (code) => {
  if (code) {
    loadDimensionTypes(code)
  } else {
    data.value = {}
    loaded.value = false
    dimTypes.value = []
  }
}, { immediate: true })

async function loadDimensionTypes(code) {
  try {
    const res = await getDetailDimensionTypes(code)
    dimTypes.value = res.dimension_types || []
    if (dimTypes.value.length > 0) {
      selectedDimType.value = props.dimensionType || dimTypes.value[0]
    }
    await loadSchedule(code, selectedDimType.value)
  } catch {
    dimTypes.value = []
    await loadSchedule(code, '')
  }
}

async function loadSchedule(code, dimType) {
  loading.value = true
  loaded.value = false
  const sign = openingDebitPositive.value ? 'debit' : 'credit'
  try {
    data.value = await getDetailSchedule(code, dimType, sign)
  } catch {
    data.value = {}
  } finally {
    loading.value = false
    loaded.value = true
  }
}

function handleOpeningSignChange(val) {
  if (!props.subjectCode) return
  loadSchedule(props.subjectCode, selectedDimType.value)
}

function handleDimTypeChange(dimType) {
  if (props.subjectCode) {
    loadSchedule(props.subjectCode, dimType)
  }
}

async function handleExport() {
  const wb = new ExcelJS.Workbook()
  const ws = wb.addWorksheet(`${data.value.subject_name || ''}明细表`)

  const title = `${data.value.subject_name} 明细表（按${data.value.dimension_type}）`
  ws.mergeCells('A1:E1')
  const titleCell = ws.getCell('A1')
  titleCell.value = title
  titleCell.font = { bold: true, size: 14 }
  titleCell.alignment = { horizontal: 'center' }

  const headers = [data.value.dimension_type, '期初数', '借方发生额', '贷方发生额', '期末数']
  ws.addRow(headers)
  const headerRow = ws.getRow(2)
  headerRow.font = { bold: true, size: 11 }
  headerRow.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F0FE' } }
  headerRow.alignment = { horizontal: 'center' }

  for (const row of data.value.rows || []) {
    ws.addRow([row.name, row.opening, row.debit, row.credit, row.closing])
  }

  const totalRow = ws.addRow([
    '合计（科目余额表）',
    data.value.ctrl_opening,
    data.value.ctrl_debit,
    data.value.ctrl_credit,
    data.value.ctrl_closing,
  ])
  totalRow.font = { bold: true }

  ws.getColumn(1).width = 24
  for (let c = 2; c <= 5; c++) {
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
  a.download = `${data.value.subject_name}_明细表.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

defineExpose({ loadDimensions: loadDimensionTypes, handleExport })
</script>

<style scoped>
.detail-schedule { height: 100%; }

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 60px 20px; color: #c0c4cc;
}
.empty-state p { margin-top: 12px; font-size: 14px; }
.empty-hint { font-size: 12px; color: #dcdfe6; margin-top: 4px; }

.schedule-header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 14px; border-bottom: 2px solid #e8f0fe; margin-bottom: 16px;
}

.header-info { display: flex; align-items: center; gap: 10px; }
.header-info h3 { font-size: 16px; margin: 0; color: #303133; }

.schedule-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}

.schedule-table th, .schedule-table td {
  border: 1px solid #ebeef5; padding: 10px 14px; text-align: right;
}

.schedule-table th {
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
  font-weight: 600; color: #606266; text-align: center; font-size: 12px;
  letter-spacing: 0.3px;
}

.col-name {
  text-align: left; min-width: 180px; background: #fafbfc;
  font-weight: 500;
}

.col-amount {
  min-width: 130px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

.col-amount.debit { color: #303133; }
.col-amount.credit { color: #e23c3c; }

.row-other td { background: #fef0f0; color: #f56c6c; }

.row-total td {
  background: #f5f7fa; font-weight: 700;
  border-top: 2px solid #dcdfe6;
}

.schedule-table tfoot {
  border-top: 2px solid #dcdfe6;
}
</style>
