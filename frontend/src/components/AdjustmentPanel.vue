<template>
  <div class="adjustment-panel">
    <div class="adjustment-toolbar">
      <div class="toolbar-left">
        <el-button type="primary" size="small" @click="openCreateDialog">
          <el-icon><Plus /></el-icon> 新建调整分录
        </el-button>
        <el-input
          v-model="filterVoucher"
          placeholder="凭证号快速筛选"
          size="small"
          clearable
          style="width: 160px"
          @input="fetchData"
        />
      </div>
      <div class="toolbar-right">
        <el-button
          type="danger"
          size="small"
          plain
          :disabled="adjustments.length === 0"
          @click="handleClearAll"
        >
          <el-icon><Delete /></el-icon> 批量清空
        </el-button>
      </div>
    </div>

    <el-table
      :data="filteredAdjustments"
      stripe
      size="small"
      max-height="calc(100vh - 340px)"
      style="width: 100%"
      v-loading="loading"
    >
      <el-table-column type="index" label="#" width="50" />
      <el-table-column prop="voucher_no" label="凭证号" width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.voucher_no }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
      <el-table-column prop="subject_code" label="科目编码" width="110" />
      <el-table-column prop="subject_name" label="科目名称" min-width="140" show-overflow-tooltip />
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
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openEditDialog(row)">
            编辑
          </el-button>
          <el-button size="small" type="danger" link @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="adjustments.length === 0 && !loading" class="empty-state">
      <p>暂无调整分录</p>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑调整分录' : '新建调整分录'"
      width="520px"
      top="12vh"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px" size="small">
        <el-form-item label="凭证号">
          <el-input v-model="form.voucher_no" placeholder="如 TZ001" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="调整摘要说明" />
        </el-form-item>
        <el-form-item label="科目编码">
          <el-input v-model="form.subject_code" placeholder="科目编码" />
        </el-form-item>
        <el-form-item label="科目名称">
          <el-input v-model="form.subject_name" placeholder="科目名称" />
        </el-form-item>
        <el-form-item label="借方金额">
          <el-input-number
            v-model="form.debit"
            :min="0"
            :precision="2"
            style="width: 100%"
            placeholder="0.00"
          />
        </el-form-item>
        <el-form-item label="贷方金额">
          <el-input-number
            v-model="form.credit"
            :min="0"
            :precision="2"
            style="width: 100%"
            placeholder="0.00"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="dialogVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'
import {
  getAdjustments,
  createAdjustment,
  updateAdjustment,
  deleteAdjustment,
  clearAdjustments,
} from '../api/index.js'

const adjustments = ref([])
const loading = ref(false)
const filterVoucher = ref('')

const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const saving = ref(false)

const defaultForm = () => ({
  voucher_no: '',
  summary: '',
  subject_code: '',
  subject_name: '',
  debit: 0,
  credit: 0,
})

const form = ref(defaultForm())

const filteredAdjustments = computed(() => {
  if (!filterVoucher.value) return adjustments.value
  const q = filterVoucher.value.toLowerCase()
  return adjustments.value.filter((a) =>
    (a.voucher_no || '').toLowerCase().includes(q)
  )
})

async function fetchData() {
  loading.value = true
  try {
    const data = await getAdjustments()
    adjustments.value = data?.adjustments || data || []
  } catch {
    adjustments.value = []
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  form.value = defaultForm()
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEditing.value = true
  editingId.value = row.id
  form.value = {
    voucher_no: row.voucher_no || '',
    summary: row.summary || '',
    subject_code: row.subject_code || '',
    subject_name: row.subject_name || '',
    debit: row.debit || 0,
    credit: row.credit || 0,
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.voucher_no) {
    ElMessage.warning('请输入凭证号')
    return
  }
  saving.value = true
  try {
    if (isEditing.value) {
      await updateAdjustment(editingId.value, form.value)
      ElMessage.success('调整分录已更新')
    } else {
      await createAdjustment(form.value)
      ElMessage.success('调整分录已创建')
    }
    dialogVisible.value = false
    await fetchData()
  } catch {
    // error already handled by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除凭证号为「${row.voucher_no}」的调整分录吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await deleteAdjustment(row.id)
    ElMessage.success('已删除')
    await fetchData()
  } catch {
    // cancelled or error
  }
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空当前账套的所有调整分录吗？此操作不可恢复。',
      '确认批量清空',
      { type: 'warning', confirmButtonText: '确认清空', confirmButtonClass: 'el-button--danger' }
    )
    await clearAdjustments()
    ElMessage.success('已清空所有调整分录')
    await fetchData()
  } catch {
    // cancelled or error
  }
}

onMounted(fetchData)
onActivated(fetchData)
</script>

<style scoped>
.adjustment-panel { height: 100%; }

.adjustment-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  gap: 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
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

.amount-debit { color: #e6a23c; font-weight: 600; }
.amount-credit { color: #409eff; font-weight: 600; }
</style>
