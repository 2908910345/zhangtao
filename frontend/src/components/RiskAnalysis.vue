<template>
  <div class="risk-analysis">
    <el-tabs v-model="activeSubTab" @tab-change="handleTabChange">
      <!-- ════════════════════════════════════════════ -->
      <!-- Tab 1: 大额交易 -->
      <!-- ════════════════════════════════════════════ -->
      <el-tab-pane label="大额交易" name="large">
        <el-form :model="largeForm" inline size="small" class="risk-form">
          <el-form-item label="金额阈值" required>
            <el-input-number v-model="largeForm.threshold" :min="1" :precision="2" style="width:150px" placeholder="输入阈值" />
          </el-form-item>
          <el-form-item label="方向">
            <el-select v-model="largeForm.threshold_side" style="width:100px">
              <el-option label="任一" value="either" />
              <el-option label="借方" value="debit" />
              <el-option label="贷方" value="credit" />
            </el-select>
          </el-form-item>
          <el-form-item label="期间">
            <el-input v-model="largeForm.period" placeholder="如 2024-03" style="width:130px" />
          </el-form-item>
          <el-form-item label="科目前缀">
            <el-input v-model="largeForm.subject_prefix" placeholder="如 1002" style="width:110px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="searchLarge" :loading="largeLoading">
              <el-icon><Search /></el-icon> 查询
            </el-button>
            <el-button @click="resetLarge">重置</el-button>
          </el-form-item>
        </el-form>

        <!-- 高级筛选（折叠） -->
        <el-collapse v-model="largeCollapse" class="risk-collapse">
          <el-collapse-item title="高级筛选" name="advanced">
            <el-form :model="largeForm" inline size="small">
              <el-form-item label="最少分录数">
                <el-input-number v-model="largeForm.min_entries" :min="1" style="width:100px" />
              </el-form-item>
              <el-form-item label="最多分录数">
                <el-input-number v-model="largeForm.max_entries" :min="1" style="width:100px" />
              </el-form-item>
              <el-form-item>
                <el-tag type="info" size="small">一借一贷 = 分录数 2</el-tag>
              </el-form-item>
            </el-form>
          </el-collapse-item>
        </el-collapse>

        <!-- 结果 -->
        <template v-if="largeResult">
          <div class="risk-summary">
            <span>共 <strong>{{ largeResult.total_vouchers }}</strong> 张凭证，
                  涉及 <strong>{{ largeResult.total_entries }}</strong> 笔大额分录，
                  阈值: ¥{{ largeResult.threshold.toLocaleString() }}</span>
          </div>

          <el-table :data="largeResult.items" stripe border size="small" v-if="largeResult.items.length > 0">
            <el-table-column label="凭证号" width="140">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="viewVoucher(row)">
                  {{ row.voucher_no }}
                </el-button>
              </template>
            </el-table-column>
            <el-table-column prop="period" label="期间" width="110" />
            <el-table-column prop="entry_count" label="分录数" width="70" align="center" />
            <el-table-column prop="total_debit" label="借方合计" width="130" align="right">
              <template #default="{ row }">¥{{ row.total_debit.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column prop="total_credit" label="贷方合计" width="130" align="right">
              <template #default="{ row }">¥{{ row.total_credit.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="平衡" width="60" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_balanced ? 'success' : 'danger'" size="small">
                  {{ row.is_balanced ? '✓' : '✗' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="first_summary" label="摘要" min-width="180" show-overflow-tooltip />
            <el-table-column label="大额分录" min-width="220">
              <template #default="{ row }">
                <div v-for="(e, i) in row.large_entries" :key="i" class="large-entry-row">
                  <span class="entry-subject">{{ e.subject_name }}</span>
                  <span class="entry-amount" :class="e.debit > 0 ? 'debit' : 'credit'">
                    {{ e.debit > 0 ? '借' + e.debit.toLocaleString() : '贷' + e.credit.toLocaleString() }}
                  </span>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-else description="未发现超过阈值的分录" :image-size="80" />

          <el-pagination
            v-if="largeResult.total_vouchers > largePageSize"
            v-model:current-page="largePage"
            :page-size="largePageSize"
            :total="largeResult.total_vouchers"
            layout="prev, pager, next, total"
            size="small"
            background
            style="margin-top:12px"
            @current-change="searchLarge"
          />
        </template>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════ -->
      <!-- Tab 2: 余额波动 -->
      <!-- ════════════════════════════════════════════ -->
      <el-tab-pane label="余额波动" name="fluctuation">
        <el-form :model="fluctForm" inline size="small" class="risk-form">
          <el-form-item label="对比账套" required>
            <el-select v-model="fluctForm.compare_book" placeholder="选择对比账套" style="width:180px">
              <el-option v-for="b in bookList" :key="b.name" :label="b.name" :value="b.name"
                         :disabled="b.name === currentBookName" />
            </el-select>
          </el-form-item>
          <el-form-item label="余额类型">
            <el-select v-model="fluctForm.balance_type" style="width:120px">
              <el-option label="期末余额" value="end" />
              <el-option label="本期发生额" value="period" />
              <el-option label="本年累计" value="year_total" />
            </el-select>
          </el-form-item>
          <el-form-item label="波动阈值">
            <el-select v-model="fluctForm.threshold_pct" style="width:100px">
              <el-option label="30%" :value="30" />
              <el-option label="50%" :value="50" />
              <el-option label="100%" :value="100" />
            </el-select>
          </el-form-item>
          <el-form-item label="金额阈值">
            <el-input-number v-model="fluctForm.amount_threshold" :min="0" :step="50000"
                             style="width:150px" placeholder="0=不启用" />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="fluctForm.category" placeholder="全部" style="width:110px" clearable>
              <el-option label="资产" value="资产" />
              <el-option label="负债" value="负债" />
              <el-option label="权益" value="权益" />
              <el-option label="损益" value="损益" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="searchFluctuation" :loading="fluctLoading">
              <el-icon><Search /></el-icon> 查询
            </el-button>
          </el-form-item>
        </el-form>

        <template v-if="fluctResult">
          <!-- 汇总卡片 -->
          <el-row :gutter="12" class="risk-summary-cards">
            <el-col :span="6">
              <el-card shadow="never" class="summary-card">
                <div class="card-label">匹配科目</div>
                <div class="card-value">{{ fluctResult.summary.matched_subjects }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="summary-card">
                <div class="card-label">异常科目</div>
                <div class="card-value anomaly">{{ fluctResult.summary.anomaly_count }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="summary-card">
                <div class="card-label">异常率</div>
                <div class="card-value">{{ fluctResult.summary.anomaly_rate }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="never" class="summary-card">
                <div class="card-label">未匹配</div>
                <div class="card-value">{{ fluctResult.summary.unmatched_subjects }}</div>
              </el-card>
            </el-col>
          </el-row>

          <el-table :data="fluctResult.items" stripe border size="small" style="margin-top:12px">
            <el-table-column prop="code" label="科目编码" width="100" />
            <el-table-column prop="name" label="科目名称" min-width="130" />
            <el-table-column prop="category" label="分类" width="60" />
            <el-table-column label="当前余额" width="120" align="right">
              <template #default="{ row }">¥{{ (row.current_balance || 0).toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="对比余额" width="120" align="right">
              <template #default="{ row }">¥{{ (row.compare_balance || 0).toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="变化额" width="120" align="right">
              <template #default="{ row }">
                <span :class="row.change_amount > 0 ? 'change-up' : 'change-down'">
                  ¥{{ (row.change_amount || 0).toLocaleString() }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="变化率" width="100" align="right">
              <template #default="{ row }">
                <span v-if="row.change_pct !== null" :class="riskColor(row.risk_level)">
                  {{ row.change_pct > 0 ? '+' : '' }}{{ row.change_pct }}%
                </span>
                <el-tag v-else size="small" type="danger">新增</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险等级" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="riskTagType(row.risk_level)" size="small" effect="dark">
                  {{ riskLabel(row.risk_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="risk_reason" label="风险说明" min-width="200" show-overflow-tooltip />
          </el-table>

          <el-pagination
            v-if="fluctResult.items.length > 0"
            v-model:current-page="fluctPage"
            :page-size="fluctPageSize"
            :total="fluctResult.summary.anomaly_count"
            layout="prev, pager, next"
            size="small"
            background
            style="margin-top:12px"
            @current-change="searchFluctuation"
          />
        </template>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════ -->
      <!-- Tab 3: 毛利率分析 -->
      <!-- ════════════════════════════════════════════ -->
      <el-tab-pane label="毛利率分析" name="gross-margin">
        <el-form :model="gmForm" inline size="small" class="risk-form">
          <el-form-item label="对比账套（可选）">
            <el-select v-model="gmForm.compare_book" placeholder="不选则仅当期" style="width:180px" clearable>
              <el-option v-for="b in bookList" :key="b.name" :label="b.name" :value="b.name"
                         :disabled="b.name === currentBookName" />
            </el-select>
          </el-form-item>
          <el-form-item label="收入科目">
            <el-select v-model="gmForm.revenue_subjects" multiple filterable allow-create
                       default-first-option placeholder="默认从模板匹配" style="width:260px" collapse-tags>
              <el-option value="主营业务收入" />
              <el-option value="其他业务收入" />
            </el-select>
          </el-form-item>
          <el-form-item label="成本科目">
            <el-select v-model="gmForm.cost_subjects" multiple filterable allow-create
                       default-first-option placeholder="默认从模板匹配" style="width:260px" collapse-tags>
              <el-option value="主营业务成本" />
              <el-option value="其他业务成本" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="searchGrossMargin" :loading="gmLoading">
              <el-icon><DataAnalysis /></el-icon> 分析
            </el-button>
          </el-form-item>
        </el-form>

        <template v-if="gmResult">
          <el-row :gutter="16">
            <!-- 当期 -->
            <el-col :span="gmResult.compare ? 12 : 24">
              <el-card shadow="never" class="gm-card">
                <template #header>
                  <span class="gm-card-title">📊 当期（{{ gmResult.book_name }}）</span>
                </template>
                <div class="gm-metric-grid">
                  <div class="gm-metric">
                    <div class="gm-label">营业收入</div>
                    <div class="gm-value">¥{{ (gmResult.current.revenue || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric">
                    <div class="gm-label">营业成本</div>
                    <div class="gm-value">¥{{ (gmResult.current.cost || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric">
                    <div class="gm-label">毛利</div>
                    <div class="gm-value gm-profit">¥{{ (gmResult.current.gross_profit || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric" :class="marginClass(gmResult.current.gross_margin)">
                    <div class="gm-label">毛利率</div>
                    <div class="gm-value gm-margin-pct">{{ (gmResult.current.gross_margin || 0).toFixed(2) }}%</div>
                  </div>
                </div>
                <div class="gm-subjects">
                  <el-tag size="small" v-for="s in gmResult.current.revenue_subjects" :key="s" type="success" style="margin:2px">{{ s }}</el-tag>
                  <el-tag size="small" v-for="s in gmResult.current.cost_subjects" :key="s" type="warning" style="margin:2px">{{ s }}</el-tag>
                </div>
              </el-card>
            </el-col>

            <!-- 对比 -->
            <el-col :span="12" v-if="gmResult.compare">
              <el-card shadow="never" class="gm-card">
                <template #header>
                  <span class="gm-card-title">📊 对比（{{ gmResult.compare_book }}）</span>
                </template>
                <div class="gm-metric-grid">
                  <div class="gm-metric">
                    <div class="gm-label">营业收入</div>
                    <div class="gm-value">¥{{ (gmResult.compare.revenue || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric">
                    <div class="gm-label">营业成本</div>
                    <div class="gm-value">¥{{ (gmResult.compare.cost || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric">
                    <div class="gm-label">毛利</div>
                    <div class="gm-value gm-profit">¥{{ (gmResult.compare.gross_profit || 0).toLocaleString() }}</div>
                  </div>
                  <div class="gm-metric" :class="marginClass(gmResult.compare.gross_margin)">
                    <div class="gm-label">毛利率</div>
                    <div class="gm-value gm-margin-pct">{{ (gmResult.compare.gross_margin || 0).toFixed(2) }}%</div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 变动 -->
          <el-row v-if="gmResult.change" :gutter="12" style="margin-top:12px">
            <el-col :span="24">
              <el-card shadow="never" class="gm-change-card">
                <template #header>
                  <span class="gm-card-title">📈 变动分析</span>
                </template>
                <el-row :gutter="16">
                  <el-col :span="6">
                    <div class="change-metric">
                      <div class="change-label">收入变动</div>
                      <div class="change-value" :class="gmResult.change.revenue_change_pct > 0 ? 'up' : 'down'">
                        {{ gmResult.change.revenue_change_pct > 0 ? '+' : '' }}{{ (gmResult.change.revenue_change_pct || 0).toFixed(2) }}%
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="change-metric">
                      <div class="change-label">成本变动</div>
                      <div class="change-value" :class="gmResult.change.cost_change_pct > 0 ? 'up' : 'down'">
                        {{ gmResult.change.cost_change_pct > 0 ? '+' : '' }}{{ (gmResult.change.cost_change_pct || 0).toFixed(2) }}%
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="change-metric">
                      <div class="change-label">毛利变动</div>
                      <div class="change-value" :class="gmResult.change.gross_profit_change_pct > 0 ? 'up' : 'down'">
                        {{ gmResult.change.gross_profit_change_pct > 0 ? '+' : '' }}{{ (gmResult.change.gross_profit_change_pct || 0).toFixed(2) }}%
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="change-metric">
                      <div class="change-label">毛利率变动(百分点)</div>
                      <div class="change-value" :class="gmResult.change.gross_margin_change_ppt > 0 ? 'up' : 'down'">
                        {{ gmResult.change.gross_margin_change_ppt > 0 ? '+' : '' }}{{ (gmResult.change.gross_margin_change_ppt || 0).toFixed(2) }}pp
                      </div>
                    </div>
                  </el-col>
                </el-row>
              </el-card>
            </el-col>
          </el-row>

          <!-- 风险警报 -->
          <el-row v-if="gmResult.risk_assessment?.alerts?.length" style="margin-top:12px">
            <el-col :span="24">
              <el-card shadow="never" class="gm-alert-card">
                <template #header>
                  <span class="gm-card-title">🚨 风险信号</span>
                </template>
                <el-alert
                  v-for="(alert, i) in gmResult.risk_assessment.alerts"
                  :key="i"
                  :title="alert.message"
                  :type="alert.severity === 'critical' ? 'error' : alert.severity === 'high' ? 'warning' : 'info'"
                  :description="`类型: ${alert.type}`"
                  show-icon
                  :closable="false"
                  style="margin-bottom:8px"
                />
              </el-card>
            </el-col>
          </el-row>
        </template>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Search, DataAnalysis } from '@element-plus/icons-vue'
import {
  getLargeTransactions,
  getBalanceFluctuation,
  getGrossMarginAnalysis,
  listBooks,
  getCurrentBook,
} from '../api/index.js'

const emit = defineEmits(['view-voucher'])

// ── 子 Tab ──
const activeSubTab = ref('large')

// ── 账套列表 ──
const bookList = ref([])
const currentBookName = computed(() => getCurrentBook())

// ── 大额交易 ──
const largeForm = reactive({
  threshold: 100000,
  threshold_side: 'either',
  period: '',
  subject_prefix: '',
  min_entries: null,
  max_entries: null,
})
const largeCollapse = ref([])
const largeLoading = ref(false)
const largeResult = ref(null)
const largePage = ref(1)
const largePageSize = 50

// ── 波动分析 ──
const fluctForm = reactive({
  compare_book: '',
  balance_type: 'end',
  threshold_pct: 30,
  amount_threshold: 0,
  category: '',
  subject_prefix: '',
})
const fluctLoading = ref(false)
const fluctResult = ref(null)
const fluctPage = ref(1)
const fluctPageSize = 50

// ── 毛利率 ──
const gmForm = reactive({
  compare_book: '',
  revenue_subjects: [],
  cost_subjects: [],
})
const gmLoading = ref(false)
const gmResult = ref(null)

// ── 生命周期 ──
onMounted(async () => {
  try {
    const data = await listBooks()
    bookList.value = data.books || []
  } catch {
    bookList.value = []
  }
})

// ── 大额交易 ──
async function searchLarge() {
  if (!largeForm.threshold || largeForm.threshold <= 0) return
  largeLoading.value = true
  largePage.value = 1
  try {
    const params = {
      book_name: getCurrentBook(),
      threshold: largeForm.threshold,
      threshold_side: largeForm.threshold_side,
      page: largePage.value,
      page_size: largePageSize,
    }
    if (largeForm.period) params.period = largeForm.period
    if (largeForm.subject_prefix) params.subject_prefix = largeForm.subject_prefix
    if (largeForm.min_entries !== null && largeForm.min_entries !== undefined) params.min_entries = largeForm.min_entries
    if (largeForm.max_entries !== null && largeForm.max_entries !== undefined) params.max_entries = largeForm.max_entries
    largeResult.value = await getLargeTransactions(params)
  } catch {
    largeResult.value = null
  } finally {
    largeLoading.value = false
  }
}

function resetLarge() {
  largeForm.threshold = 100000
  largeForm.threshold_side = 'either'
  largeForm.period = ''
  largeForm.subject_prefix = ''
  largeForm.min_entries = null
  largeForm.max_entries = null
  largeResult.value = null
  largePage.value = 1
}

async function handleLargePageChange(page) {
  largePage.value = page
  await searchLarge()
}

// ── 波动分析 ──
async function searchFluctuation() {
  if (!fluctForm.compare_book) return
  fluctLoading.value = true
  try {
    const params = {
      book_name: getCurrentBook(),
      compare_book: fluctForm.compare_book,
      compare_type: 'mom',
      balance_type: fluctForm.balance_type,
      threshold_pct: fluctForm.threshold_pct,
      amount_threshold: fluctForm.amount_threshold || 0,
      page: fluctPage.value,
      page_size: fluctPageSize,
    }
    if (fluctForm.category) params.category = fluctForm.category
    if (fluctForm.subject_prefix) params.subject_prefix = fluctForm.subject_prefix

    fluctResult.value = await getBalanceFluctuation(params)
  } catch {
    fluctResult.value = null
  } finally {
    fluctLoading.value = false
  }
}

// ── 毛利率 ──
async function searchGrossMargin() {
  gmLoading.value = true
  try {
    const params = { book_name: getCurrentBook() }
    if (gmForm.compare_book) params.compare_book = gmForm.compare_book
    if (gmForm.revenue_subjects.length > 0) params.revenue_subjects = gmForm.revenue_subjects.join(',')
    if (gmForm.cost_subjects.length > 0) params.cost_subjects = gmForm.cost_subjects.join(',')
    gmResult.value = await getGrossMarginAnalysis(params)
  } catch {
    gmResult.value = null
  } finally {
    gmLoading.value = false
  }
}

// ── 工具函数 ──
function riskColor(level) {
  return {
    medium: 'risk-warning',
    high: 'risk-danger',
    critical: 'risk-critical',
  }[level] || ''
}

function riskTagType(level) {
  return {
    normal: 'info',
    medium: 'warning',
    high: 'danger',
    critical: 'danger',
  }[level] || 'info'
}

function riskLabel(level) {
  return {
    normal: '正常',
    medium: '关注',
    high: '重点',
    critical: '高风险',
  }[level] || '未知'
}

function marginClass(margin) {
  if (margin < 0) return 'margin-negative'
  if (margin < 10) return 'margin-low'
  return 'margin-healthy'
}

function viewVoucher(voucher) {
  emit('view-voucher', { voucherNo: voucher.voucher_no, period: voucher.period })
}

function handleTabChange(tab) {
  // no-op for now
}
</script>

<style scoped>
.risk-analysis {
  padding: 4px 0;
  height: 100%;
}

.risk-form {
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.risk-collapse {
  margin-bottom: 8px;
}

.risk-collapse :deep(.el-collapse-item__header) {
  font-size: 12px;
  padding-left: 16px;
}

.risk-summary {
  padding: 8px 0;
  font-size: 13px;
  color: #666;
}

.risk-summary-cards {
  margin-bottom: 8px;
}

.summary-card {
  text-align: center;
}

.summary-card .card-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.summary-card .card-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
}

.summary-card .card-value.anomaly {
  color: #e6a23c;
}

.large-entry-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  border-bottom: 1px dashed #eee;
  font-size: 12px;
}

.large-entry-row:last-child {
  border-bottom: none;
}

.entry-subject {
  color: #333;
  margin-right: 8px;
}

.entry-amount {
  font-weight: 600;
  white-space: nowrap;
}

.entry-amount.debit {
  color: #cf4444;
}

.entry-amount.credit {
  color: #409eff;
}

.change-up {
  color: #cf4444;
}

.change-down {
  color: #409eff;
}

.risk-warning {
  color: #e6a23c;
  font-weight: 600;
}

.risk-danger {
  color: #f56c6c;
  font-weight: 600;
}

.risk-critical {
  color: #f56c6c;
  font-weight: 700;
  font-size: 1.1em;
}

/* 毛利率卡片 */
.gm-card {
  height: 100%;
}

.gm-card :deep(.el-card__header) {
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.gm-card-title {
  font-weight: 600;
  font-size: 14px;
}

.gm-metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.gm-metric {
  text-align: center;
  padding: 12px 8px;
  background: #fafafa;
  border-radius: 6px;
}

.gm-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.gm-value {
  font-size: 18px;
  font-weight: 700;
  color: #333;
}

.gm-profit {
  color: #67c23a;
}

.gm-margin-pct {
  font-size: 24px;
}

.margin-healthy .gm-margin-pct {
  color: #67c23a;
}

.margin-low .gm-margin-pct {
  color: #e6a23c;
}

.margin-negative .gm-margin-pct {
  color: #f56c6c;
}

.gm-subjects {
  margin-top: 8px;
  text-align: center;
}

.gm-change-card :deep(.el-card__header),
.gm-alert-card :deep(.el-card__header) {
  padding: 10px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.change-metric {
  text-align: center;
  padding: 8px;
}

.change-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.change-value {
  font-size: 16px;
  font-weight: 700;
}

.change-value.up {
  color: #cf4444;
}

.change-value.down {
  color: #409eff;
}
</style>
