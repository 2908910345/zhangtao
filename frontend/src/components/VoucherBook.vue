<template>
  <div class="voucher-book" v-loading="loading">
    <div v-if="vouchers.length === 0 && !loading" class="empty-state">
      <el-icon :size="40"><Notebook /></el-icon>
      <p>暂无凭证数据，请先导入序时账</p>
    </div>

    <template v-else>
      <div class="voucher-toolbar">
        <div class="filter-row">
          <el-select v-model="filterPeriod" placeholder="期间筛选" size="small" clearable style="width: 150px">
            <el-option v-for="p in periodOptions" :key="p" :label="p" :value="p" />
          </el-select>
          <el-input v-model="filterKeyword" placeholder="搜索凭证号/摘要" size="small" clearable style="width: 180px">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button size="small" type="primary" @click="loadData(1)">查询</el-button>
          <span class="total-hint">共 {{ total }} 张凭证</span>
        </div>
      </div>

      <el-table
        :data="vouchers"
        stripe
        size="small"
        max-height="calc(100vh - 300px)"
        style="width: 100%"
        @row-click="handleRowClick"
        highlight-current-row
      >
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="voucher_no" label="凭证号" width="120">
          <template #default="{ row }">
            <el-link type="primary" underline="never">{{ row.voucher_no }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="first_summary" label="首行摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="entry_count" label="分录数" width="80" align="center" />
        <el-table-column label="借方合计" width="140" align="right">
          <template #default="{ row }">
            <span v-if="row.total_debit" class="amount-debit">{{ formatAmount(row.total_debit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="贷方合计" width="140" align="right">
          <template #default="{ row }">
            <span v-if="row.total_credit" class="amount-credit">{{ formatAmount(row.total_credit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="平衡" width="70" align="center">
          <template #default="{ row }">
            <el-icon v-if="Math.abs(row.total_debit - row.total_credit) < 0.01" color="#67c23a"><CircleCheck /></el-icon>
            <el-icon v-else color="#f56c6c"><WarningFilled /></el-icon>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          size="small"
          @current-change="loadData"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Search, Notebook, CircleCheck, WarningFilled } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { getVoucherBook, getStatistics } from '../api/index.js'

const emit = defineEmits(['view-voucher'])

const vouchers = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = 50
const filterPeriod = ref('')
const filterKeyword = ref('')
const periodOptions = ref([])

async function loadData(page) {
  if (page) currentPage.value = page
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize,
    }
    if (filterPeriod.value) params.period = filterPeriod.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    const data = await getVoucherBook(params)
    vouchers.value = data.vouchers || []
    total.value = data.total || 0
  } catch {
    vouchers.value = []
  } finally {
    loading.value = false
  }
}

async function loadPeriods() {
  try {
    // 从凭证汇总接口获取带期间筛选的数据，提取期间列表
    const data = await getVoucherBook({ page: 1, page_size: 200 })
    const periods = new Set()
    for (const v of data.vouchers || []) {
      if (v.period) periods.add(v.period)
    }
    periodOptions.value = [...periods].sort()
  } catch {}
}

function handleRowClick(row) {
  emit('view-voucher', { voucherNo: row.voucher_no, period: row.period })
}

onMounted(() => {
  loadData(1)
  loadPeriods()
})

defineExpose({ loadData })
</script>

<style scoped>
.voucher-book { height: 100%; }

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 80px 20px; color: #c0c4cc;
}
.empty-state p { margin-top: 16px; font-size: 14px; }

.voucher-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 2px solid #e8f0fe;
}

.filter-row { display: flex; gap: 8px; align-items: center; }
.total-hint { font-size: 12px; color: var(--text-secondary, #909399); white-space: nowrap; margin-left: 8px; }

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
  cursor: pointer;
}

:deep(.el-table th.el-table__cell) {
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
  color: var(--text-regular, #606266);
  font-weight: 600;
  font-size: 12px;
  padding: 10px 0;
  letter-spacing: 0.3px;
}

:deep(.el-table__row:hover > td) {
  background-color: #f5f8ff !important;
  transition: background-color 0.2s;
}
</style>
