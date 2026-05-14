<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-left">
        <span class="header-title">账套管理系统</span>
        <el-tag size="small" type="warning" effect="dark">
          {{ currentBookName === 'default' ? '默认账套' : currentBookName }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button size="small" @click="openBookManager('manage')">
          <el-icon><FolderOpened /></el-icon> 账套列表
        </el-button>
        <el-button size="small" type="success" @click="openBookManager('save')">
          <el-icon><Upload /></el-icon> 保存到数据库
        </el-button>
        <el-button size="small" @click="handleExport">
          <el-icon><Download /></el-icon> 导出底稿
        </el-button>
        <el-button size="small" @click="settingsVisible = true">
          <el-icon><Setting /></el-icon> 设置
        </el-button>
        <el-button size="small" type="danger" plain @click="handleClear">
          <el-icon><Delete /></el-icon> 清除数据
        </el-button>
      </div>
    </el-header>

    <el-main class="app-main">
      <el-container class="main-container">
        <el-aside width="320px" class="tree-panel">
          <div class="panel-header clickable" @click="handleBalanceReset">科目总览</div>
          <SubjectTree
            :tree-data="subjectTree"
            :loading="treeLoading"
            @select="handleSubjectSelect"
            @dblclick="handleSubjectDblclick"
          />
        </el-aside>

        <el-main class="detail-panel">
          <div class="panel-header">
            <span v-if="activeTab === 'balance'">科目余额表</span>
            <span v-else-if="activeTab === 'journal'">序时账明细</span>
            <span v-else-if="activeTab === 'dimension'">核算维度</span>
            <span v-else>数据导入</span>
          </div>

          <div class="tab-bar">
            <el-radio-group v-model="activeTab" size="small">
              <el-radio-button value="balance">科目余额表</el-radio-button>
              <el-radio-button value="journal">序时账</el-radio-button>
              <el-radio-button value="dimension">核算维度</el-radio-button>
              <el-radio-button value="import">数据导入</el-radio-button>
            </el-radio-group>
          </div>

          <div class="tab-content">
            <transition name="fade" mode="out-in">
              <KeepAlive>
                <BalanceSheet
                  v-if="activeTab === 'balance'"
                  :subjects="balanceSubjects"
                  :loading="balanceLoading"
                  :parent-code="balanceFilterCode"
                  @dblclick="handleBalanceDblclick"
                  @reset="handleBalanceReset"
                />

                <JournalDetail
                  v-else-if="activeTab === 'journal'"
                  ref="journalRef"
                  :selected-subject="selectedSubject"
                  @view-voucher="handleViewVoucher"
                />

                <DimensionPanel
                  v-else-if="activeTab === 'dimension'"
                  :selected-subject="selectedSubject"
                />

                <div v-else class="import-container">
                  <ImportPanel
                    v-model:balance-status="importStatus.balance"
                    v-model:journal-status="importStatus.journal"
                    @upload-balance="handleUploadBalance"
                    @upload-journal="handleUploadJournal"
                  />
                  <div class="import-actions" v-if="importStatus.balance.pending || importStatus.journal.pending">
                    <el-button type="primary" size="large" @click="handleSaveToDatabase">
                      <el-icon><Upload /></el-icon> 保存到数据库
                    </el-button>
                  </div>
                </div>
              </KeepAlive>
            </transition>
          </div>
        </el-main>
      </el-container>
    </el-main>

    <el-footer class="app-footer">
      <span>
        科目 <strong>{{ stats.subject_count }}</strong> 个，
        凭证 <strong>{{ stats.voucher_count }}</strong> 张
      </span>
      <span v-if="stats.period_range" style="margin-left:16px">
        期间：{{ stats.period_range }}
      </span>
      <span style="margin-left:auto">账套管理系统 v2.0</span>
    </el-footer>

    <BookManager
      v-model:visible="bookDialogVisible"
      :type="bookDialogType"
      @book-changed="handleBookChanged"
      @import-to-book="handleImportToBook"
      @switch-and-import="handleSwitchAndImport"
    />

    <el-dialog v-model="voucherVisible" title="记账凭证" width="860px" top="8vh" class="voucher-dialog">
      <VoucherView :voucher-no="currentVoucherNo" :period="currentVoucherPeriod" />
    </el-dialog>

    <SettingsDialog v-model:visible="settingsVisible" />
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SubjectTree from './components/SubjectTree.vue'
import BalanceSheet from './components/BalanceSheet.vue'
import JournalDetail from './components/JournalDetail.vue'
import DimensionPanel from './components/DimensionPanel.vue'
import ImportPanel from './components/ImportPanel.vue'
import BookManager from './components/BookManager.vue'
import VoucherView from './components/VoucherView.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import {
  getSubjectTree, getAllSubjects, getStatistics,
  uploadBalance, uploadJournal, clearAllData,
  getActiveBook, setCurrentBook, getCurrentBook,
  exportBalanceDraft, downloadBalanceTemplate,
  switchBook, saveToDatabase,
} from './api/index.js'

const activeTab = ref('balance')

const subjectTree = ref([])
const treeLoading = ref(false)

const balanceSubjects = ref([])
const balanceLoading = ref(false)
const balanceFilterCode = ref('')

const selectedSubject = ref(null)

const stats = ref({ subject_count: 0, voucher_count: 0, period_range: '' })

const bookDialogVisible = ref(false)
const bookDialogType = ref('save')
const currentBookName = ref(getCurrentBook())

const importStatus = ref({
  balance: { imported: false, count: 0, time: '', pending: false },
  journal: { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false },
})

const pendingFiles = ref({
  balance: null,
  journal: null,
})

const voucherVisible = ref(false)
const currentVoucherNo = ref('')
const currentVoucherPeriod = ref('')

const settingsVisible = ref(false)

const journalRef = ref(null)

function openBookManager(type) {
  bookDialogType.value = type
  bookDialogVisible.value = true
}

async function loadAllData() {
  await Promise.all([loadSubjectTree(), loadBalanceSubjects(), loadStats()])
}

async function loadSubjectTree() {
  treeLoading.value = true
  try {
    subjectTree.value = await getSubjectTree() || []
  } catch { subjectTree.value = [] }
  finally { treeLoading.value = false }
}

async function loadBalanceSubjects() {
  balanceLoading.value = true
  try {
    const data = await getAllSubjects()
    balanceSubjects.value = data.subjects || []
  } catch { balanceSubjects.value = [] }
  finally { balanceLoading.value = false }
}

async function loadStats() {
  try {
    stats.value = await getStatistics()
  } catch {}
}

function handleSubjectSelect(subject) {
  selectedSubject.value = { code: subject.code, name: subject.name }
  balanceFilterCode.value = subject.code
}

function handleBalanceReset() {
  balanceFilterCode.value = ''
}

function handleSubjectDblclick(subject) {
  selectedSubject.value = { code: subject.code, name: subject.name }
  activeTab.value = 'journal'
}

function handleBalanceDblclick(row) {
  selectedSubject.value = { code: row.code, name: row.name }
  activeTab.value = 'journal'
}

function handleViewVoucher({ voucherNo, period }) {
  currentVoucherNo.value = voucherNo
  currentVoucherPeriod.value = period || ''
  voucherVisible.value = true
}

async function handleUploadBalance(file) {
  pendingFiles.value.balance = file
  const fileName = file.name
  ElMessage.info(`已选择科目余额表：${fileName}，点击"保存到数据库"按钮保存`)
  importStatus.value.balance = {
    imported: true, count: 0,
    time: new Date().toLocaleString('zh-CN'),
    pending: true,
  }
}

async function handleUploadJournal(file) {
  pendingFiles.value.journal = file
  const fileName = file.name
  ElMessage.info(`已选择序时账：${fileName}，点击"保存到数据库"按钮保存`)
  importStatus.value.journal = {
    imported: true, count: 0,
    time: new Date().toLocaleString('zh-CN'),
    subject_count: 0, voucher_count: 0,
    pending: true,
  }
}

async function handleSaveToDatabase() {
  if (!pendingFiles.value.balance && !pendingFiles.value.journal) {
    ElMessage.warning('请先导入科目余额表或序时账')
    return
  }

  const loading = ElMessage.info('正在保存到数据库...')

  try {
    if (pendingFiles.value.balance) {
      const res = await uploadBalance(pendingFiles.value.balance)
      importStatus.value.balance = {
        imported: true, count: res.count,
        time: new Date().toLocaleString('zh-CN'),
        pending: false,
      }
      pendingFiles.value.balance = null
      ElMessage.success(`科目余额表已保存到数据库（${res.count} 条科目）`)
    }

    if (pendingFiles.value.journal) {
      const res = await uploadJournal(pendingFiles.value.journal)
      importStatus.value.journal = {
        imported: true, count: res.count,
        time: new Date().toLocaleString('zh-CN'),
        subject_count: res.subject_count || 0,
        voucher_count: res.voucher_count || 0,
        pending: false,
      }
      pendingFiles.value.journal = null
      ElMessage.success(`序时账已保存到数据库（${res.count} 行分录）`)
    }

    await saveToDatabase()
    await loadAllData()
  } catch (error) {
    ElMessage.error('保存失败：' + (error.message || '未知错误'))
  }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定要清除当前账套的所有数据吗？', '确认清除', { type: 'warning' })
    await clearAllData()
    subjectTree.value = []
    balanceSubjects.value = []
    balanceFilterCode.value = ''
    selectedSubject.value = null
    importStatus.value = {
      balance: { imported: false, count: 0, time: '', pending: false },
      journal: { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false },
    }
    pendingFiles.value = { balance: null, journal: null }
    stats.value = { subject_count: 0, voucher_count: 0, period_range: '' }
    ElMessage.success('数据已清除')
  } catch {}
}

async function handleBookChanged() {
  currentBookName.value = getCurrentBook()
  balanceFilterCode.value = ''
  selectedSubject.value = null
  importStatus.value = {
    balance: { imported: false, count: 0, time: '', pending: false },
    journal: { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false },
  }
  pendingFiles.value = { balance: null, journal: null }
  await loadAllData()
}

async function handleSwitchAndImport(bookName) {
  try {
    await switchBook(bookName)
    setCurrentBook(bookName)
    currentBookName.value = bookName
    balanceFilterCode.value = ''
    selectedSubject.value = null
    importStatus.value = {
      balance: { imported: false, count: 0, time: '', pending: false },
      journal: { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false },
    }
    pendingFiles.value = { balance: null, journal: null }
    await loadAllData()
    activeTab.value = 'import'
    ElMessage.success(`账套「${bookName}」已创建，现在可以导入数据`)
  } catch { ElMessage.error('切换账套失败') }
}

async function handleImportToBook(bookName) {
  try {
    await switchBook(bookName)
    setCurrentBook(bookName)
    currentBookName.value = bookName
    importStatus.value = {
      balance: { imported: false, count: 0, time: '', pending: false },
      journal: { imported: false, count: 0, time: '', subject_count: 0, voucher_count: 0, pending: false },
    }
    pendingFiles.value = { balance: null, journal: null }
    await loadAllData()
    activeTab.value = 'import'
    ElMessage.success(`已切换到账套「${bookName}」，请导入数据`)
  } catch { ElMessage.error('切换账套失败') }
}

async function handleExport() {
  try {
    const blob = await exportBalanceDraft()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `科目余额表_${currentBookName.value}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('底稿已导出')
  } catch {
    ElMessage.warning('导出失败')
  }
}

onMounted(async () => {
  try {
    const active = await getActiveBook()
    if (active && active.name) {
      setCurrentBook(active.name)
      currentBookName.value = active.name
    }
  } catch {}

  await loadAllData()
})
</script>

<style>
:root {
  --primary: #409eff;
  --primary-light: #ecf5ff;
  --primary-dark: #337ecc;
  --success: #67c23a;
  --warning: #e6a23c;
  --danger: #f56c6c;
  --info: #909399;
  --text-primary: #303133;
  --text-regular: #606266;
  --text-secondary: #909399;
  --text-placeholder: #c0c4cc;
  --border-color: #ebeef5;
  --bg-color: #f0f2f5;
  --bg-light: #f5f7fa;
  --shadow-sm: 0 1px 4px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  background: var(--bg-color);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d0d5dd; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #b0b5bd; }

.app-container { height: 100vh; display: flex; flex-direction: column; }

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #1a73e8 0%, #1557b0 50%, #0d47a1 100%);
  color: #fff;
  padding: 0 28px;
  height: 52px !important;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(21, 87, 176, 0.25);
  position: relative;
  z-index: 10;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.header-left .el-tag { border: none; }
.header-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #fff, rgba(255,255,255,0.85));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header-right { display: flex; gap: 8px; align-items: center; }
.header-right .el-button {
  color: rgba(255,255,255,0.9);
  border-color: rgba(255,255,255,0.3);
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(4px);
  transition: var(--transition);
  font-weight: 500;
  letter-spacing: 0.3px;
}
.header-right .el-button:hover {
  border-color: rgba(255,255,255,0.7);
  background: rgba(255,255,255,0.18);
  color: #fff;
  transform: translateY(-1px);
}
.header-right .el-button:active {
  transform: translateY(0);
}

.app-main { flex: 1; padding: 0; overflow: hidden; background: var(--bg-color); }
.main-container { height: 100%; background: #fff; margin: 10px; border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-md); }

.tree-panel {
  border-right: 1px solid var(--border-color);
  background: #fafbfc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}

.panel-header {
  padding: 14px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
  background: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: 0.5px;
}
.panel-header.clickable {
  cursor: pointer;
  user-select: none;
  transition: var(--transition);
}
.panel-header.clickable:hover {
  background: var(--primary-light);
  color: var(--primary);
}

.detail-panel { display: flex; flex-direction: column; padding: 0; overflow: hidden; }
.tab-bar {
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-color);
  background: #fcfcfd;
}
.tab-content { flex: 1; overflow: auto; padding: 18px; }
.import-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.import-actions {
  padding: 20px;
  text-align: center;
  border-top: 1px solid var(--border-color, #ebeef5);
  background: linear-gradient(180deg, #f8f9fb, #f0f2f5);
}
.import-actions .el-button {
  padding: 16px 40px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  border-radius: 8px;
}

.app-footer {
  display: flex;
  align-items: center;
  background: #fff;
  border-top: 1px solid var(--border-color);
  padding: 0 28px;
  height: 38px !important;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  box-shadow: 0 -1px 4px rgba(0,0,0,0.03);
}

.el-table .cell {
  -webkit-user-select: all;
  user-select: all;
}

.el-dialog {
  border-radius: var(--radius-lg);
}
.el-dialog__header {
  padding: 18px 24px;
  margin: 0;
  border-bottom: 1px solid var(--border-color);
  background: #fcfcfd;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.el-dialog__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.el-dialog__body {
  padding: 20px 24px;
}
.el-dialog__footer {
  padding: 14px 24px;
  border-top: 1px solid var(--border-color);
  background: #fafbfc;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.voucher-dialog .el-dialog__body {
  padding: 4px 0 0 0;
}
.voucher-dialog .el-dialog__header {
  border-bottom: none;
  background: #fff;
}
.voucher-dialog .el-dialog__headerbtn {
  font-size: 18px;
}

.voucher-tooltip {
  max-width: 400px;
}
</style>