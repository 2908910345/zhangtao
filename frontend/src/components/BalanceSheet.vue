<template>
  <div class="balance-sheet" v-loading="loading">
    <div v-if="!subjects || subjects.length === 0" class="empty-state">
      <el-icon :size="40"><Coin /></el-icon>
      <p>暂未导入科目余额表，请先在"数据导入"页面上传</p>
    </div>

    <template v-else>
      <div class="filter-info" v-if="parentInfo">
        当前科目：<strong>{{ parentInfo.name }}</strong>
        <span class="parent-code">{{ parentInfo.code }}</span>
        <el-button size="small" text @click="$emit('reset')" style="margin-left:8px">
          <el-icon><Back /></el-icon> 返回全部一级科目
        </el-button>
        <el-button size="small" type="primary" plain @click="exportBalance" style="margin-left:auto">
          <el-icon><Download /></el-icon> 导出Excel
        </el-button>
      </div>
      <div v-else class="filter-info" style="justify-content:space-between">
        <span>全部一级科目</span>
        <el-button size="small" type="primary" plain @click="exportBalance">
          <el-icon><Download /></el-icon> 导出Excel
        </el-button>
      </div>

      <el-table
        v-if="displaySubjects.length > 0"
        :data="displaySubjects"
        stripe
        size="small"
        :row-class-name="tableRowClassName"
        @row-dblclick="handleRowDblclick"
        max-height="calc(100vh - 300px)"
        style="width: 100%"
        highlight-current-row
        table-layout="auto"
      >
        <el-table-column prop="code" label="科目编码" width="150" sortable :filters="codeFilters" :filter-method="filterCodeColumn" />
        <el-table-column prop="name" label="科目名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="期初金额" align="center">
          <el-table-column label="借方" width="130" align="right" sortable prop="year_start_debit">
            <template #default="{ row }">
              <span v-if="row._fmt.ysd" class="amount">{{ row._fmt.ysd }}</span>
            </template>
          </el-table-column>
          <el-table-column label="贷方" width="130" align="right" sortable prop="year_start_credit">
            <template #default="{ row }">
              <span v-if="row._fmt.ysc" class="amount credit">{{ row._fmt.ysc }}</span>
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="本期发生额" align="center">
          <el-table-column label="借方" width="130" align="right" sortable prop="period_debit">
            <template #default="{ row }">
              <span v-if="row._fmt.pd" class="amount">{{ row._fmt.pd }}</span>
            </template>
          </el-table-column>
          <el-table-column label="贷方" width="130" align="right" sortable prop="period_credit">
            <template #default="{ row }">
              <span v-if="row._fmt.pc" class="amount credit">{{ row._fmt.pc }}</span>
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="期末金额" align="center">
          <el-table-column label="借方" width="130" align="right" sortable prop="end_debit">
            <template #default="{ row }">
              <span v-if="row._fmt.ed" class="amount">{{ row._fmt.ed }}</span>
            </template>
          </el-table-column>
          <el-table-column label="贷方" width="130" align="right" sortable prop="end_credit">
            <template #default="{ row }">
              <span v-if="row._fmt.ec" class="amount credit">{{ row._fmt.ec }}</span>
            </template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="核算维度" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="dimension-cell" :class="{ 'no-dimension': !row.dimension }">
              {{ row.dimension || '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="empty-state" style="padding: 32px">
        <p>该科目下暂无下级科目</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Back } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { useSettings } from '../utils/settings.js'
import { exportToExcel } from '../utils/export.js'

const { settings } = useSettings()
const tableRef = ref(null)

const props = defineProps({
  subjects: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  parentCode: { type: String, default: '' },
})

const emit = defineEmits(['dblclick', 'reset'])

const fmt = (v) => v ? formatAmount(v) : ''

function formatRow(s) {
  return {
    ...s,
    _fmt: {
      ysd: fmt(s.year_start_debit),
      ysc: fmt(s.year_start_credit),
      pd: fmt(s.period_debit),
      pc: fmt(s.period_credit),
      ed: fmt(s.end_debit),
      ec: fmt(s.end_credit),
    }
  }
}

const displaySubjects = computed(() => {
  const all = props.subjects
  if (!all || all.length === 0) return []

  if (!props.parentCode) {
    const result = []
    for (let i = 0; i < all.length; i++) {
      const s = all[i]
      if (s.code.includes('.')) continue
      if (!settings.showDimensionSubjects && s.dimension) continue
      result.push(formatRow(s))
    }
    return result
  }

  const prefix = props.parentCode + '.'
  const result = []
  for (let i = 0; i < all.length; i++) {
    const s = all[i]
    if (s.code === props.parentCode ||
        (s.code.startsWith(prefix) && !s.code.substring(prefix.length).includes('.'))) {
      if (!settings.showDimensionSubjects && s.dimension) continue
      result.push(formatRow(s))
    }
  }
  return result
})

const parentInfo = computed(() => {
  if (!props.parentCode) return null
  return props.subjects.find(s => s.code === props.parentCode) || null
})

const codeFilters = computed(() => {
  const values = [...new Set(displaySubjects.value.map(r => r.code).filter(Boolean))]
  return values.map(v => ({ text: v, value: v }))
})

function filterCodeColumn(value, row) {
  return row.code === value
}

async function exportBalance() {
  const headers = [
    { key: 'code', label: '科目编码' },
    { key: 'name', label: '科目名称' },
    { key: 'year_start_debit', label: '期初借方' },
    { key: 'year_start_credit', label: '期初贷方' },
    { key: 'period_debit', label: '本期借方' },
    { key: 'period_credit', label: '本期贷方' },
    { key: 'end_debit', label: '期末借方' },
    { key: 'end_credit', label: '期末贷方' },
    { key: 'dimension', label: '核算维度' },
  ]
  const parent = props.parentCode ? `（${parentInfo.value?.name || ''}）` : ''
  await exportToExcel({
    data: displaySubjects.value.map(r => ({
      code: r.code,
      name: r.name,
      year_start_debit: r.year_start_debit || 0,
      year_start_credit: r.year_start_credit || 0,
      period_debit: r.period_debit || 0,
      period_credit: r.period_credit || 0,
      end_debit: r.end_debit || 0,
      end_credit: r.end_credit || 0,
      dimension: r.dimension || '',
    })),
    headers,
    filename: `科目余额表.xlsx`,
    sheetName: '科目余额表',
    title: '科目余额表',
    subtitle: parent || '全部一级科目',
    amountKeys: [
      'year_start_debit', 'year_start_credit',
      'period_debit', 'period_credit',
      'end_debit', 'end_credit',
    ],
  })
}

function tableRowClassName({ row }) {
  if (row.code === props.parentCode) return 'row-parent'
  if (!row.code.includes('.')) return 'row-level-1'
  return ''
}

function handleRowDblclick(row) {
  emit('dblclick', row)
}
</script>

<style scoped>
.balance-sheet {
  height: 100%;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #c0c4cc;
}

.empty-state p {
  margin-top: 16px;
  font-size: 14px;
}

.filter-info {
  padding: 8px 4px 14px;
  font-size: 13px;
  color: var(--text-regular, #606266);
  display: flex;
  align-items: center;
  gap: 4px;
  border-bottom: 2px solid #e8f0fe;
  margin-bottom: 12px;
}

.parent-code {
  color: var(--text-secondary, #909399);
  font-size: 12px;
  margin-left: 4px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  background: var(--bg-light, #f5f7fa);
  padding: 1px 8px;
  border-radius: 4px;
}

.amount {
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  color: var(--text-primary, #303133);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.amount.credit {
  color: #e23c3c;
}

.dimension-cell {
  font-size: 12px;
  color: var(--text-regular, #606266);
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dimension-cell.no-dimension {
  color: #c0c4cc;
  font-style: italic;
}

:deep(.row-level-1) {
  font-weight: 600;
  background-color: #f4f8ff !important;
}

:deep(.row-level-1:hover > td) {
  background-color: #e8f0fe !important;
}

:deep(.row-parent) {
  font-weight: 600;
  background-color: #edf7ed !important;
}

:deep(.row-parent:hover > td) {
  background-color: #dbefdb !important;
}

:deep(.el-table__row:hover > td) {
  background-color: #f5f8ff !important;
  transition: background-color 0.2s;
}

:deep(.el-table) {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #ebeef5);
}

:deep(.el-table th.el-table__cell) {
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
  color: var(--text-regular, #606266);
  font-weight: 600;
  font-size: 12px;
  padding: 12px 0;
  letter-spacing: 0.3px;
}

:deep(.el-table th.el-table__cell > .cell) {
  color: #515a6e;
}

:deep(.el-table .cell) {
  padding: 0 12px;
}

:deep(.el-table__body tr.current-row > td) {
  background-color: #e8f0fe !important;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: #fafbfc;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped.current-row > td) {
  background-color: #e8f0fe !important;
}
</style>