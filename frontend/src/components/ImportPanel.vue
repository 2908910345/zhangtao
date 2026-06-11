<template>
  <div class="import-panel">
    <div class="import-cards">
      <div class="import-card">
        <div class="card-header">
            <span>科目余额表</span>
            <el-link type="primary" underline="never" class="tpl-link" @click="downloadTemplate('balance')">
              <el-icon><Download /></el-icon> 下载模板
            </el-link>
          </div>
        <div class="card-body">
          <template v-if="!balanceStatus.imported">
            <div
              class="upload-zone"
              :class="{ dragover: dragTarget === 'balance' }"
              @click="triggerUpload('balance')"
              @dragover.prevent="dragTarget = 'balance'"
              @dragleave.prevent="dragTarget = ''"
              @drop.prevent="handleDrop($event, 'balance')"
            >
              <el-icon class="upload-icon" :size="40"><UploadFilled /></el-icon>
              <p>点击或拖拽上传科目余额表</p>
              <p class="upload-hint">支持 .xlsx / .xls 格式</p>
            </div>
            <input ref="balInput" type="file" accept=".xlsx,.xls" style="display:none" @change="handleFile($event, 'balance')" />
          </template>
          <template v-else>
            <div class="import-success">
              <el-icon class="success-icon" :size="32" :color="balanceStatus.pending ? '#E6A23C' : '#67c23a'">
                <component :is="balanceStatus.pending ? 'Clock' : 'CircleCheck'" />
              </el-icon>
              <p v-if="balanceStatus.pending">
                已选择文件：<strong>{{ balanceStatus.count > 0 ? balanceStatus.count + ' 条科目' : '等待保存到数据库' }}</strong>
              </p>
              <p v-else>
                已保存到数据库 <strong>{{ balanceStatus.count }}</strong> 条科目
              </p>
              <p class="import-time">{{ balanceStatus.time }}</p>
              <el-button size="small" @click="clearBalance">重新选择</el-button>
            </div>
          </template>
        </div>
      </div>

      <div class="import-card">
        <div class="card-header">
            <span>序时账（凭证）</span>
            <el-link type="primary" underline="never" class="tpl-link" @click="downloadTemplate('journal')">
              <el-icon><Download /></el-icon> 下载模板
            </el-link>
          </div>
        <div class="card-body">
          <template v-if="!journalStatus.imported">
            <div
              class="upload-zone"
              :class="{ dragover: dragTarget === 'journal' }"
              @click="triggerUpload('journal')"
              @dragover.prevent="dragTarget = 'journal'"
              @dragleave.prevent="dragTarget = ''"
              @drop.prevent="handleDrop($event, 'journal')"
            >
              <el-icon class="upload-icon" :size="40"><UploadFilled /></el-icon>
              <p>点击或拖拽上传序时账</p>
              <p class="upload-hint">支持 .xlsx / .xls 格式</p>
            </div>
            <input ref="jnlInput" type="file" accept=".xlsx,.xls" style="display:none" @change="handleFile($event, 'journal')" />
          </template>
          <template v-else>
            <div class="import-success">
              <el-icon class="success-icon" :size="32" :color="journalStatus.pending ? '#E6A23C' : '#67c23a'">
                <component :is="journalStatus.pending ? 'Clock' : 'CircleCheck'" />
              </el-icon>
              <p v-if="journalStatus.pending">
                已选择文件：<strong>{{ journalStatus.count > 0 ? journalStatus.count + ' 行分录' : '等待保存到数据库' }}</strong>
              </p>
              <p v-else>
                已保存到数据库 <strong>{{ journalStatus.count }}</strong> 行分录
              </p>
              <p v-if="!journalStatus.pending && journalStatus.subject_count">同步 <strong>{{ journalStatus.subject_count }}</strong> 个科目</p>
              <p class="import-time">{{ journalStatus.time }}</p>
              <el-button size="small" @click="clearJournal">重新选择</el-button>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div v-if="balanceStatus.imported || journalStatus.imported" class="import-summary">
      <div class="summary-header">导入概览</div>
      <div class="summary-body">
        <div class="summary-item">
          <div class="value">{{ balanceStatus.count }}</div>
          <div class="label">科目数</div>
        </div>
        <div class="summary-item">
          <div class="value">{{ journalStatus.count }}</div>
          <div class="label">分录行数</div>
        </div>
        <div class="summary-item">
          <div class="value">{{ journalStatus.voucher_count || '-' }}</div>
          <div class="label">凭证数</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, UploadFilled, CircleCheck, Clock } from '@element-plus/icons-vue'
import { downloadBalanceTemplate, downloadJournalTemplate } from '../api/index.js'

const props = defineProps({
  balanceStatus: { type: Object, required: true },
  journalStatus: { type: Object, required: true },
})

const emit = defineEmits([
  'upload-balance', 'upload-journal',
  'update:balance-status', 'update:journal-status',
])

const dragTarget = ref('')
const balInput = ref(null)
const jnlInput = ref(null)

function triggerUpload(type) {
  (type === 'balance' ? balInput : jnlInput).value?.click()
}

function handleDrop(event, type) {
  dragTarget.value = ''
  const file = event.dataTransfer.files[0]
  if (file) processFile(file, type)
}

function handleFile(event, type) {
  const file = event.target.files[0]
  if (file) processFile(file, type)
  event.target.value = ''
}

function processFile(file, type) {
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  if (!['.xlsx', '.xls'].includes(ext)) {
    ElMessage.error('请上传 .xlsx 或 .xls 格式的文件')
    return
  }
  emit(type === 'balance' ? 'upload-balance' : 'upload-journal', file)
}

function clearBalance() {
  emit('update:balance-status', { imported: false, count: 0, time: '', pending: false })
}
function clearJournal() {
  emit('update:journal-status', { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false })
}

async function downloadTemplate(type) {
  try {
    const blob = type === 'balance' ? await downloadBalanceTemplate() : await downloadJournalTemplate()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = type === 'balance' ? '科目余额表模板.xlsx' : '序时账模板.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('模板已下载')
  } catch {
    ElMessage.error('下载失败')
  }
}
</script>

<style scoped>
.import-cards { display: flex; gap: 24px; margin-bottom: 24px; }
.import-card {
  flex: 1;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: var(--shadow-sm, 0 1px 4px rgba(0,0,0,0.06));
  transition: var(--transition, all 0.25s);
}
.import-card:hover {
  box-shadow: var(--shadow-md, 0 4px 12px rgba(0,0,0,0.08));
  transform: translateY(-2px);
}
.card-header {
  padding: 12px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  background: linear-gradient(135deg, #f8f9fb, #f0f2f5);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tpl-link { font-size: 12px; font-weight: 400; }
.card-body { padding: 28px 24px; }
.upload-zone {
  border: 2px dashed #dcdfe6;
  border-radius: 10px;
  padding: 36px 20px;
  text-align: center;
  cursor: pointer;
  color: var(--text-secondary, #909399);
  transition: var(--transition, all 0.25s);
  background: #fafbfc;
}
.upload-zone:hover, .upload-zone.dragover {
  border-color: var(--primary, #409eff);
  color: var(--primary, #409eff);
  background: #f0f7ff;
  transform: scale(1.01);
}
.upload-icon { margin-bottom: 12px; }
.upload-zone p { font-size: 14px; }
.upload-hint { font-size: 12px; margin-top: 8px; color: #c0c4cc; }
.import-success { text-align: center; padding: 16px; color: var(--text-regular, #606266); }
.success-icon { margin-bottom: 8px; }
.import-time { font-size: 12px; color: #c0c4cc; margin: 4px 0 12px; }
.import-summary {
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: var(--shadow-sm, 0 1px 4px rgba(0,0,0,0.06));
}
.summary-header {
  padding: 12px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  background: linear-gradient(135deg, #f8f9fb, #f0f2f5);
}
.summary-body { display: flex; padding: 24px; gap: 40px; justify-content: center; }
.summary-item { text-align: center; }
.summary-item .value {
  font-size: 30px;
  font-weight: 700;
  color: var(--primary, #409eff);
  font-family: var(--font-number);
}
.summary-item .label { font-size: 13px; color: var(--text-secondary, #909399); margin-top: 6px; }
</style>