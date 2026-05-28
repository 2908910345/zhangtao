<template>
  <div class="voucher-wrapper">
    <div v-if="!voucherNo" class="empty-state">
      <el-icon :size="48"><Document /></el-icon>
      <p>请选择凭证查看</p>
    </div>

    <div v-else v-loading="loading" class="voucher-document">
      <div class="voucher-paper">
        <div class="voucher-title-row">
          <div class="title-line">
            <span class="title-deco"></span>
            <h2 class="voucher-title">记 账 凭 证</h2>
            <span class="title-deco"></span>
          </div>
          <div class="voucher-badge">
            <span class="badge-label">凭证号</span>
            <span class="badge-value">{{ voucherNo }}</span>
          </div>
        </div>

        <div class="voucher-info">
          <div class="info-item">
            <span class="info-label">核算组织</span>
            <span class="info-value">{{ voucherData[0]?.org || '-' }}</span>
          </div>
          <div class="info-divider"></div>
          <div class="info-item">
            <span class="info-label">期间</span>
            <span class="info-value">{{ voucherData[0]?.period || '-' }}</span>
          </div>
          <div class="info-divider"></div>
          <div class="info-item">
            <span class="info-label">分录数</span>
            <span class="info-value">{{ voucherData.length }}</span>
          </div>
        </div>

        <div class="voucher-table-area">
          <table class="voucher-table" v-if="voucherData.length > 0">
            <thead>
              <tr>
                <th class="col-index">序号</th>
                <th class="col-summary">摘要</th>
                <th class="col-subject">科目</th>
                <th v-if="settings.showCounterpartSubject" class="col-counterpart">对方科目</th>
                <th class="col-amount">借方金额</th>
                <th class="col-amount">贷方金额</th>
              </tr>
            </thead>
          </table>
          <div class="voucher-table-scroll">
            <table class="voucher-table" v-if="voucherData.length > 0">
              <tbody>
                <tr v-for="(row, index) in voucherData" :key="index" :class="{ 'last-row': index === voucherData.length - 1 }">
                  <td class="col-index">{{ index + 1 }}</td>
                  <td class="col-summary">
                    <el-tooltip
                      :content="row.summary || '-'"
                      placement="top"
                      :show-after="400"
                      :disabled="!row.summary || row.summary.length < 20"
                      popper-class="voucher-tooltip"
                    >
                      <span class="summary-text">{{ row.summary || '-' }}</span>
                    </el-tooltip>
                  </td>
                  <td class="col-subject">
                    <span class="subject-code-text">{{ row.subject_code }}</span>
                    <span class="subject-name-text">{{ row.subject_name }}</span>
                  </td>
                  <td v-if="settings.showCounterpartSubject" class="col-counterpart">
                    {{ counterparties[index] || '-' }}
                  </td>
                  <td class="col-amount amount-debit">{{ row.debit ? formatAmount(row.debit) : '' }}</td>
                  <td class="col-amount amount-credit">{{ row.credit ? formatAmount(row.credit) : '' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="table-empty">暂无分录数据</div>
          </div>
        </div>

        <div class="voucher-footer">
          <div class="voucher-totals">
            <div class="total-item">
              <span class="total-label">借方合计</span>
              <span class="total-sep">：</span>
              <span class="total-value debit">{{ formatAmount(totalDebit) }}</span>
            </div>
            <div class="total-item">
              <span class="total-label">贷方合计</span>
              <span class="total-sep">：</span>
              <span class="total-value credit">{{ formatAmount(totalCredit) }}</span>
            </div>
            <div class="balance-check">
              <span v-if="isBalanced" class="balanced">
                <el-icon><CircleCheck /></el-icon> 借贷平衡
              </span>
              <span v-else class="unbalanced">
                <el-icon><WarningFilled /></el-icon> 借贷不平衡（差额：{{ formatAmount(Math.abs(totalDebit - totalCredit)) }}）
              </span>
            </div>
          </div>
          <div class="voucher-signatures">
            <div class="sig-item">会计：</div>
            <div class="sig-item">审核：</div>
            <div class="sig-item">制单：</div>
            <el-button size="small" text type="primary" @click="exportVoucher" style="margin-left:auto">
              <el-icon><Download /></el-icon> 导出Excel
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Document, CircleCheck, WarningFilled, Download } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import { getVoucherDetail } from '../api/index.js'
import { useSettings } from '../utils/settings.js'
import { exportToExcel } from '../utils/export.js'

const { settings } = useSettings()

const props = defineProps({
  voucherNo: { type: String, default: '' },
  period: { type: String, default: '' },
})

const voucherData = ref([])
const loading = ref(false)

watch(() => props.voucherNo, (no) => {
  if (no) loadVoucher(no)
}, { immediate: true })

async function loadVoucher(no) {
  if (!no) { voucherData.value = []; return }
  loading.value = true
  try {
    voucherData.value = await getVoucherDetail(no, props.period)
  } catch {
    voucherData.value = []
  } finally {
    loading.value = false
  }
}

const totalDebit = computed(() =>
  voucherData.value.reduce((s, i) => s + (i.debit || 0), 0)
)
const totalCredit = computed(() =>
  voucherData.value.reduce((s, i) => s + (i.credit || 0), 0)
)
const isBalanced = computed(() =>
  Math.abs(totalDebit.value - totalCredit.value) < 0.01
)

async function exportVoucher() {
  const headers = [
    { key: 'index', label: '序号' },
    { key: 'summary', label: '摘要' },
    { key: 'subject_code', label: '科目编码' },
    { key: 'subject_name', label: '科目名称' },
    { key: 'debit', label: '借方金额' },
    { key: 'credit', label: '贷方金额' },
  ]
  const periodLabel = props.period ? `（${props.period}）` : ''
  await exportToExcel({
    data: voucherData.value.map((r, i) => ({
      index: i + 1,
      summary: r.summary || '-',
      subject_code: r.subject_code,
      subject_name: r.subject_name,
      debit: r.debit || 0,
      credit: r.credit || 0,
    })),
    headers,
    filename: `凭证_${props.voucherNo}${periodLabel}.xlsx`,
    sheetName: '凭证分录',
    title: '记账凭证',
    subtitle: `凭证号：${props.voucherNo}${periodLabel}`,
    amountKeys: ['debit', 'credit'],
  })
}

const counterparties = computed(() => {
  const data = voucherData.value
  if (!data || data.length === 0) return []
  const groups = {}
  for (let i = 0; i < data.length; i++) {
    const row = data[i]
    const key = `${row.voucher_no || ''}|${row.summary || ''}`
    if (!groups[key]) groups[key] = []
    groups[key].push(i)
  }
  const result = new Array(data.length)
  for (const key of Object.keys(groups)) {
    const indices = groups[key]
    const entries = []
    for (let k = 0; k < indices.length; k++) {
      const r = data[indices[k]]
      entries.push({ code: r.subject_code, name: r.subject_name })
    }
    for (let k = 0; k < indices.length; k++) {
      const r = data[indices[k]]
      const others = []
      for (let m = 0; m < entries.length; m++) {
        if (entries[m].code !== r.subject_code) {
          const e = entries[m]
          others.push(e.code ? `${e.name}(${e.code})` : e.name)
        }
      }
      const unique = [...new Set(others)]
      result[indices[k]] = unique.join('；')
    }
  }
  return result
})
</script>

<style scoped>
.voucher-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #c0c4cc;
}
.empty-state p {
  margin-top: 16px;
  font-size: 14px;
}

.voucher-document {
  display: flex;
  justify-content: center;
  width: 100%;
}

.voucher-paper {
  width: 800px;
  max-width: 100%;
  background: #fff;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.02);
  overflow: hidden;
}

.voucher-title-row {
  padding: 20px 28px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid #1a73e8;
  background: linear-gradient(180deg, #f8faff 0%, #fff 100%);
}

.title-line {
  display: flex;
  align-items: center;
  gap: 14px;
}

.title-deco {
  display: inline-block;
  width: 4px;
  height: 22px;
  background: linear-gradient(180deg, #1a73e8, #409eff);
  border-radius: 2px;
}

.voucher-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
  letter-spacing: 6px;
  margin: 0;
}

.voucher-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #e8f0fe;
  padding: 4px 14px;
  border-radius: 20px;
}
.badge-label {
  font-size: 11px;
  color: #5a7ba8;
}
.badge-value {
  font-size: 13px;
  font-weight: 700;
  color: #1a73e8;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
}

.voucher-info {
  display: flex;
  align-items: center;
  padding: 10px 28px;
  background: #fafbfc;
  border-bottom: 1px solid #e8ecf0;
  gap: 0;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.info-label {
  font-size: 12px;
  color: #8892a4;
}
.info-value {
  font-size: 13px;
  color: #1a1a2e;
  font-weight: 500;
}
.info-divider {
  width: 1px;
  height: 16px;
  background: #d0d5dd;
  margin: 0 20px;
}

.voucher-table-area {
  position: relative;
}

.voucher-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.voucher-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
}

.voucher-table th {
  background: #f0f4f8;
  color: #4a5568;
  font-size: 12px;
  font-weight: 600;
  padding: 10px 8px;
  text-align: center;
  border-bottom: 2px solid #d0d5dd;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.voucher-table td {
  padding: 10px 8px;
  font-size: 13px;
  color: #1a1a2e;
  border-bottom: 1px solid #e8ecf0;
  vertical-align: middle;
}

.voucher-table tbody tr:last-child td {
  border-bottom: none;
}

.voucher-table tbody tr:hover {
  background: #f5f8ff;
}

.voucher-table-scroll {
  max-height: 420px;
  overflow-y: auto;
  overflow-x: hidden;
}

.voucher-table-scroll::-webkit-scrollbar {
  width: 5px;
}
.voucher-table-scroll::-webkit-scrollbar-track {
  background: #f0f2f5;
  border-radius: 3px;
}
.voucher-table-scroll::-webkit-scrollbar-thumb {
  background: #c4c9d4;
  border-radius: 3px;
}
.voucher-table-scroll::-webkit-scrollbar-thumb:hover {
  background: #a8aeb8;
}

.col-index {
  width: 56px;
  text-align: center;
  color: #8892a4 !important;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 12px !important;
}
.col-summary {
  min-width: 180px;
  padding-left: 14px !important;
  max-width: 260px;
}
.summary-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-subject {
  min-width: 200px;
  padding-left: 14px !important;
}
.subject-code-text {
  font-size: 11px;
  color: #8892a4;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  margin-right: 6px;
}
.subject-name-text {
  color: #1a1a2e;
}
.col-counterpart {
  min-width: 180px;
  padding-left: 14px !important;
  font-size: 12px;
  color: #4a5568;
}
.col-amount {
  width: 140px;
  text-align: right;
  padding-right: 16px !important;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.amount-debit {
  color: #1a1a2e;
}
.amount-credit {
  color: #d4380d;
}

.table-empty {
  text-align: center;
  padding: 40px;
  color: #c0c4cc;
  font-size: 14px;
}

.voucher-footer {
  border-top: 2px solid #1a73e8;
  background: #fafbfc;
}

.voucher-totals {
  display: flex;
  align-items: center;
  padding: 14px 28px;
  gap: 32px;
  border-bottom: 1px solid #e8ecf0;
}

.total-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.total-label {
  font-size: 13px;
  color: #4a5568;
  font-weight: 500;
}
.total-sep {
  color: #4a5568;
}
.total-value {
  font-size: 15px;
  font-weight: 700;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
}
.total-value.debit {
  color: #1a1a2e;
}
.total-value.credit {
  color: #d4380d;
}

.balance-check {
  margin-left: auto;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}
.balanced {
  color: #52c41a;
}
.unbalanced {
  color: #f5222d;
}

.voucher-signatures {
  display: flex;
  justify-content: flex-end;
  padding: 14px 28px;
  gap: 40px;
}
.sig-item {
  font-size: 13px;
  color: #8892a4;
  letter-spacing: 2px;
  min-width: 80px;
  border-bottom: 1px solid #d0d5dd;
  padding-bottom: 2px;
  text-align: center;
}
</style>