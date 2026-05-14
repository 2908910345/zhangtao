<template>
  <div class="book-manager">
    <el-dialog v-model="saveDialog" title="保存到数据库" width="480px">
      <div class="save-tip">
        <el-icon color="#E6A23C"><WarningFilled /></el-icon>
        <span>提示：数据将直接保存到新账套，请先创建账套</span>
      </div>
      <el-form :model="saveForm" label-position="top">
        <el-form-item label="账套名称">
          <el-input v-model="saveForm.name" placeholder="如：2026年1-3期" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="saveForm.desc" type="textarea" :rows="2" placeholder="可选" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">创建并保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="manageDialog" title="管理账套" width="650px">
      <div class="book-actions">
        <el-button type="primary" size="small" @click="showCreateDialog">
          <el-icon><Plus /></el-icon> 新建账套
        </el-button>
      </div>
      <div v-if="books.length === 0" class="empty-books">
        <el-icon :size="36"><FolderOpened /></el-icon>
        <p>暂无已保存的账套</p>
      </div>
      <el-table v-else :data="books" stripe size="small">
        <el-table-column prop="name" label="名称" min-width="120">
          <template #default="{ row }">
            <span :class="{ 'current-book': row.name === currentBook }">
              {{ row.name }}{{ row.name === currentBook ? ' (当前)' : '' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="subject_count" label="科目数" width="80" align="center" />
        <el-table-column prop="voucher_count" label="凭证数" width="80" align="center" />
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">
            {{ row.updated_at ? new Date(row.updated_at).toLocaleString('zh-CN') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link :disabled="row.name === currentBook" @click="handleSwitch(row.name)">
              {{ row.name === currentBook ? '当前' : '切换' }}
            </el-button>
            <el-button size="small" type="success" link :disabled="row.name === currentBook" @click="handleImportToBook(row.name)">
              导入数据
            </el-button>
            <el-button size="small" type="danger" link @click="handleDelete(row.name)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="manageDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDialog" title="创建新账套" width="400px">
      <el-form :model="createForm" label-position="top">
        <el-form-item label="账套名称" required>
          <el-input v-model="createForm.name" placeholder="如：2026年1-3期" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.desc" type="textarea" :rows="2" placeholder="可选" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, Plus, WarningFilled } from '@element-plus/icons-vue'
import { createBook, switchBook, deleteBook, setCurrentBook, getCurrentBook, listBooks } from '../api/index.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  type: { type: String, default: 'save' },
})

const emit = defineEmits(['update:visible', 'book-changed', 'import-to-book', 'switch-and-import'])

const saveDialog = ref(false)
const manageDialog = ref(false)
const createDialog = ref(false)
const books = ref([])
const currentBook = ref(getCurrentBook())
const saving = ref(false)
const creating = ref(false)
const saveForm = ref({ name: '', desc: '' })
const createForm = ref({ name: '', desc: '' })

watch(() => props.visible, (val) => {
  if (val) {
    if (props.type === 'save') {
      saveDialog.value = true
      saveForm.value = { name: '', desc: '' }
    } else {
      manageDialog.value = true
      loadBooks()
    }
  }
})

watch([saveDialog, manageDialog, createDialog], ([s, m, c]) => {
  if (!s && !m && !c) emit('update:visible', false)
})

async function loadBooks() {
  try {
    const data = await listBooks()
    books.value = data.books || []
    currentBook.value = data.current || 'default'
  } catch { books.value = [] }
}

function showCreateDialog() {
  createForm.value = { name: '', desc: '' }
  createDialog.value = true
}

async function handleCreate() {
  if (!createForm.value.name.trim()) { ElMessage.warning('请输入账套名称'); return }
  creating.value = true
  try {
    await createBook(createForm.value.name.trim(), createForm.value.desc.trim())
    await switchBook(createForm.value.name.trim())
    setCurrentBook(createForm.value.name.trim())
    currentBook.value = createForm.value.name.trim()
    ElMessage.success(`账套「${createForm.value.name}」已创建`)
    createDialog.value = false
    manageDialog.value = false
    emit('update:visible', false)
    emit('switch-and-import', createForm.value.name.trim())
  } catch {} finally { creating.value = false }
}

async function handleSave() {
  if (!saveForm.value.name.trim()) { ElMessage.warning('请输入账套名称'); return }
  saving.value = true
  try {
    await createBook(saveForm.value.name.trim(), saveForm.value.desc.trim())
    await switchBook(saveForm.value.name.trim())
    setCurrentBook(saveForm.value.name.trim())
    currentBook.value = saveForm.value.name.trim()
    ElMessage.success(`账套「${saveForm.value.name}」已创建`)
    saveDialog.value = false
    emit('update:visible', false)
    emit('switch-and-import', saveForm.value.name.trim())
  } catch { saving.value = false }
}

async function handleSwitch(name) {
  try {
    await switchBook(name)
    setCurrentBook(name)
    currentBook.value = name
    ElMessage.success('已切换账套')
    emit('update:visible', false)
    emit('book-changed')
  } catch {}
}

function handleImportToBook(name) {
  ElMessage.info(`请切换到账套「${name}」后，在"数据导入"页面导入数据`)
  emit('import-to-book', name)
  manageDialog.value = false
  emit('update:visible', false)
}

async function handleDelete(name) {
  try {
    await ElMessageBox.confirm(`确定删除账套「${name}」？`, '确认', { type: 'warning' })
    await deleteBook(name)
    ElMessage.success('已删除')
    await loadBooks()
    if (currentBook.value === name) {
      setCurrentBook('default')
      currentBook.value = 'default'
      emit('book-changed')
    }
  } catch {}
}
</script>

<style scoped>
.book-actions {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color, #ebeef5);
}
.save-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 16px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 6px;
  color: #e6a23c;
  font-size: 13px;
}
.empty-books { display: flex; flex-direction: column; align-items: center; padding: 40px; color: #c0c4cc; }
.empty-books p { margin-top: 8px; }
.current-book { font-weight: 600; color: var(--primary, #409eff); }

:deep(.el-dialog__body) {
  padding: 16px 24px;
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
  letter-spacing: 0.3px;
}

:deep(.el-table th.el-table__cell > .cell) {
  color: #515a6e;
}
</style>