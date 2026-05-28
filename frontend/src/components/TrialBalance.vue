<template>
  <div class="trial-balance-panel">
    <div class="tb-toolbar">
      <div class="tb-toolbar-left">
        <span class="tb-title">试算平衡表</span>
        <el-tag v-if="checkStatus === 'balanced'" type="success" size="small">✅ 平衡</el-tag>
        <el-tag v-else-if="checkStatus === 'unbalanced'" type="danger" size="small">❌ 不平衡</el-tag>
      </div>
      <div class="tb-toolbar-right">
        <el-switch
          v-model="showNonZeroOnly"
          active-text="仅显示调整非零"
          inactive-text="显示全部"
          size="small"
        />
      </div>
    </div>

    <div class="tb-note" v-if="showNonZeroOnly">
      <el-icon><InfoFilled /></el-icon> 非末级科目的调整数为该科目自身及其全部子科目的汇总。
    </div>

    <el-table
      :data="displayData"
      stripe
      size="small"
      max-height="calc(100vh - 340px)"
      style="width: 100%"
      :summary-method="summaryMethod"
      show-summary
      v-loading="loading"
      row-key="code"
      default-expand-all
      :tree-props="{ children: 'children', hasChildren: 'has_children' }"
    >
      <el-table-column label="科目编码" width="120">
        <template #default="{ row }">
          <span class="tb-code">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="科目名称" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span :style="{ paddingLeft: (row.level - 1) * 24 + 'px' }">
            {{ row.name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="未审借方" width="130" align="right" prop="unaudited_debit">
        <template #default="{ row }">
          <span class="amount-number">{{ formatAmount(row.unaudited_debit) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="未审贷方" width="130" align="right" prop="unaudited_credit">
        <template #default="{ row }">
          <span class="amount-number">{{ formatAmount(row.unaudited_credit) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="调整借方" width="130" align="right" prop="adjustment_debit">
        <template #default="{ row }">
          <span :class="row.adjustment_debit ? 'amount-adjust' : 'amount-number'">
            {{ formatAmount(row.adjustment_debit) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="调整贷方" width="130" align="right" prop="adjustment_credit">
        <template #default="{ row }">
          <span :class="row.adjustment_credit ? 'amount-adjust' : 'amount-number'">
            {{ formatAmount(row.adjustment_credit) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="审定借方" width="130" align="right" prop="audited_debit">
        <template #default="{ row }">
          <span class="amount-number">{{ formatAmount(row.audited_debit) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="审定贷方" width="130" align="right" prop="audited_credit">
        <template #default="{ row }">
          <span class="amount-number">{{ formatAmount(row.audited_credit) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="!loading && treeData.length === 0" class="empty-state">
      <p>暂无试算数据，请先导入科目余额表</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { getTrialBalance } from '../api/index.js'
import { formatAmount } from '../utils/format.js'

const loading = ref(false)
const rows = ref([])
const treeData = ref([])
const showNonZeroOnly = ref(false)

function buildTree(flatRows) {
  if (!flatRows || flatRows.length === 0) return []

  const codeMap = {}
  flatRows.forEach(r => { codeMap[r.code] = { ...r, children: [] } })

  const roots = []
  flatRows.forEach(r => {
    const node = codeMap[r.code]
    const lastDot = r.code.lastIndexOf('.')
    if (lastDot === -1) {
      roots.push(node)
    } else {
      const parentCode = r.code.substring(0, lastDot)
      const parent = codeMap[parentCode]
      if (parent) {
        parent.children.push(node)
      } else {
        roots.push(node)
      }
    }
  })

  return roots
}

async function fetchData() {
  loading.value = true
  try {
    const resp = await getTrialBalance()
    const list = resp?.rows || resp || []
    rows.value = list
    treeData.value = buildTree(list)
  } catch {
    rows.value = []
    treeData.value = []
  } finally {
    loading.value = false
  }
}

const displayData = computed(() => {
  if (!showNonZeroOnly.value) return treeData.value

  function filterNonZero(nodes) {
    const result = []
    for (const node of nodes) {
      const children = node.children ? filterNonZero(node.children) : []
      const hasNonZero = node.adjustment_debit || node.adjustment_credit
      if (hasNonZero || children.length > 0) {
        result.push({ ...node, children })
      }
    }
    return result
  }
  return filterNonZero(treeData.value)
})

function flattenAll(nodes) {
  const result = []
  for (const node of nodes) {
    result.push(node)
    if (node.children && node.children.length > 0) {
      result.push(...flattenAll(node.children))
    }
  }
  return result
}

const allRows = computed(() => flattenAll(displayData.value))

const totals = computed(() => {
  const rows = allRows.value
  const sum = (field) => rows.reduce((s, r) => s + (parseFloat(r[field]) || 0), 0)
  return {
    unaudited_debit: sum('unaudited_debit'),
    unaudited_credit: sum('unaudited_credit'),
    adjustment_debit: sum('adjustment_debit'),
    adjustment_credit: sum('adjustment_credit'),
    audited_debit: sum('audited_debit'),
    audited_credit: sum('audited_credit'),
  }
})

const checkStatus = computed(() => {
  const t = totals.value
  return Math.abs(t.audited_debit - t.audited_credit) < 0.01 ? 'balanced' : 'unbalanced'
})

function summaryMethod() {
  const t = totals.value
  return [
    '',
    '合计',
    formatAmount(t.unaudited_debit),
    formatAmount(t.unaudited_credit),
    formatAmount(t.adjustment_debit),
    formatAmount(t.adjustment_credit),
    formatAmount(t.audited_debit),
    formatAmount(t.audited_credit),
  ]
}

onMounted(fetchData)
onActivated(fetchData)
</script>

<style scoped>
.trial-balance-panel { height: 100%; }

.tb-note {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.tb-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.tb-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tb-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tb-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #c0c4cc;
  font-size: 14px;
}

.tb-code {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--text-secondary, #909399);
}

.amount-number {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 13px;
}

.amount-adjust {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 13px;
  color: #e6a23c;
  font-weight: 600;
}
</style>
