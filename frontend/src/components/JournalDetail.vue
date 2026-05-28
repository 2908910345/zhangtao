<template>
  <div class="journal-detail" v-loading="loading">
    <div v-if="!selectedSubject" class="empty-state">
      <el-icon :size="40"><List /></el-icon>
      <p>请点击或双击科目名称查看序时账明细</p>
    </div>

    <template v-else>
      <div class="journal-toolbar">
        <div class="subject-info">
          科目：<strong>{{ selectedSubject.name }}</strong>
          <span class="subject-code">{{ selectedSubject.code }}</span>
          <el-tag v-if="includeChildren" size="small" type="info" style="margin-left: 8px">
            含{{ getLevel(selectedSubject.code) === 1 ? '全部' : '' }}子科目
          </el-tag>
        </div>
        <div class="filter-row">
          <el-input v-model="filterPeriod" placeholder="期间筛选" size="small" clearable style="width: 120px" />
          <el-input v-model="filterVoucher" placeholder="凭证号" size="small" clearable style="width: 120px" />
          <el-input v-model="filterKeyword" placeholder="模糊查找" size="small" clearable style="width: 150px">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button size="small" @click="loadData(1)">查询</el-button>
          <span class="total-hint">共 {{ totalRows }} 行</span>
          <el-button size="small" type="primary" plain @click="exportJournal">
            <el-icon><Download /></el-icon> 导出Excel
          </el-button>
        </div>
      </div>

      <el-table
        v-if="journalData.length > 0"
        ref="tableRef"
        :data="journalData"
        stripe
        size="small"
        max-height="calc(100vh - 340px)"
        style="width: 100%"
      >
        <el-table-column prop="period" label="期间" width="110" />
        <el-table-column prop="voucher_no" label="凭证号" width="100">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="viewVoucher(row)">
              {{ row.voucher_no }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="subject_code" label="科目编码" width="120" />
        <el-table-column prop="subject_name" label="科目名称" min-width="150" show-overflow-tooltip />
        <el-table-column v-if="settings.showCounterpartSubject" label="对方科目" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.counterpart || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="debit" label="借方" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.debit" class="amount-debit">{{ formatAmount(row.debit) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="credit" label="贷方" width="130" align="right">
          <template #default="{ row }">
            <span v-if="row.credit" class="amount-credit">{{ formatAmount(row.credit) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="empty-state" style="padding: 32px">
        <p>该科目暂无序时账数据</p>
      </div>

      <div class="pagination-row" v-if="totalRows > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalRows"
          layout="prev, pager, next"
          size="small"
          @current-change="loadData"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { getSubjectJournal } from '../api/index.js'
import { useSettings } from '../utils/settings.js'
import { exportToExcel } from '../utils/export.js'

const { settings } = useSettings()

const props = defineProps({
  selectedSubject: { type: Object, default: null },
})

const emit = defineEmits(['view-voucher'])

const journalData = ref([])
const loading = ref(false)
const filterPeriod = ref('')
const filterVoucher = ref('')
const filterKeyword = ref('')
const includeChildren = ref(false)
const tableRef = ref(null)
const currentPage = ref(1)
const pageSize = 500
const totalRows = ref(0)

function getLevel(code) {
  return code ? code.split('.').length : 1
}

watch(() => props.selectedSubject, (subject) => {
  if (subject) {
    loadData(1)
  } else {
    journalData.value = []
    totalRows.value = 0
  }
}, { immediate: true })

async function loadData(page) {
  if (!props.selectedSubject) return
  if (page) currentPage.value = page
  loading.value = true
  try {
    const level = getLevel(props.selectedSubject.code)
    const params = {}
    if (filterPeriod.value) params.period = filterPeriod.value
    if (filterVoucher.value) params.voucher_no = filterVoucher.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    params.include_children = level === 1
    params.with_counterpart = settings.showCounterpartSubject
    params.page = currentPage.value
    params.page_size = pageSize
    includeChildren.value = level === 1

    const data = await getSubjectJournal(props.selectedSubject.code, params)
    if (data && data.entries) {
      journalData.value = data.entries
      totalRows.value = data.total || 0
    } else {
      journalData.value = Array.isArray(data) ? data : []
      totalRows.value = journalData.value.length
    }
  } catch {
    journalData.value = []
    totalRows.value = 0
  } finally {
    loading.value = false
  }
}

function viewVoucher(row) {
  emit('view-voucher', { voucherNo: row.voucher_no, period: row.period })
}

async function exportJournal() {
  const headers = [
    { key: 'period', label: '期间' },
    { key: 'voucher_no', label: '凭证号' },
    { key: 'summary', label: '摘要' },
    { key: 'subject_code', label: '科目编码' },
    { key: 'subject_name', label: '科目名称' },
  ]
  if (settings.showCounterpartSubject) {
    headers.push({ key: 'counterpart', label: '对方科目' })
  }
  headers.push({ key: 'debit', label: '借方金额' })
  headers.push({ key: 'credit', label: '贷方金额' })
  const label = props.selectedSubject?.name || ''
  const code = props.selectedSubject?.code || ''
  await exportToExcel({
    data: journalData.value.map(r => ({
      ...r,
      debit: r.debit || 0,
      credit: r.credit || 0,
      counterpart: r.counterpart || '-',
    })),
    headers,
    filename: `序时账_${label}_${code}.xlsx`,
    sheetName: '序时账明细',
    title: '序时账明细',
    subtitle: `科目：${label}（${code}）`,
    amountKeys: ['debit', 'credit'],
  })
}

defineExpose({ loadData })
</script>

<style scoped>
.journal-detail { height: 100%; }

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 80px 20px; color: #c0c4cc;
}
.empty-state p { margin-top: 16px; font-size: 14px; }

.journal-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px; flex-wrap: wrap; gap: 10px;
  padding-bottom: 12px;
  border-bottom: 2px solid #e8f0fe;
}

.subject-info { font-size: 14px; color: var(--text-primary, #303133); display: flex; align-items: center; gap: 4px; font-weight: 500; }
.subject-code {
  color: var(--text-secondary, #909399); font-size: 12px;
  background: var(--bg-light, #f5f7fa); padding: 1px 8px; border-radius: 4px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
}

.filter-row { display: flex; gap: 8px; align-items: center; }
.filter-row :deep(.el-input__wrapper) {
  border-radius: 6px;
  transition: var(--transition, all 0.25s);
}
.total-hint { font-size: 12px; color: var(--text-secondary, #909399); white-space: nowrap; }

.amount-debit {
  color: var(--text-primary, #303133); font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.amount-credit {
  color: #e23c3c; font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

.pagination-row {
  display: flex; justify-content: center; padding: 16px 0 4px;
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
  padding: 10px 0;
  letter-spacing: 0.3px;
}

:deep(.el-table th.el-table__cell > .cell) {
  color: #515a6e;
}

:deep(.el-table__row:hover > td) {
  background-color: #f5f8ff !important;
  transition: background-color 0.2s;
}
</style>
