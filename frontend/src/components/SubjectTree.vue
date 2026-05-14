<template>
  <div class="subject-tree" v-loading="loading">
    <div class="tree-search">
      <el-input
        v-model="searchText"
        placeholder="搜索科目..."
        size="small"
        clearable
        :prefix-icon="Search"
      />
    </div>

    <div v-if="!treeData || treeData.length === 0" class="empty-state">
      <el-icon :size="36"><FolderOpened /></el-icon>
      <p>暂未导入科目余额表</p>
    </div>

    <el-tree
      v-else
      ref="treeRef"
      :data="treeData"
      :props="treeProps"
      node-key="code"
      highlight-current
      :expand-on-click-node="false"
      :filter-node-method="filterNode"
      @node-click="handleNodeClick"
      @node-dblclick="handleNodeDblclick"
    >
      <template #default="{ data }">
        <span class="tree-node">
          <span class="node-label">{{ data.name }}</span>
          <span class="node-code">{{ data.code }}</span>
          <span v-if="data.end_debit || data.end_credit" class="node-amount">
            {{ formatAmount(data.end_debit || data.end_credit) }}
          </span>
        </span>
      </template>
    </el-tree>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'

const props = defineProps({
  treeData: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'dblclick'])

const treeRef = ref(null)
const searchText = ref('')
const treeProps = { children: 'children', label: 'name' }

function filterNode(value, data) {
  if (!value) return true
  return data.name.includes(value) || data.code.includes(value)
}

watch(searchText, (val) => {
  treeRef.value?.filter(val)
})

function handleNodeClick(data) {
  emit('select', data)
}

function handleNodeDblclick(data) {
  emit('dblclick', data)
}
</script>

<style scoped>
.subject-tree {
  flex: 1;
  overflow: auto;
  padding-bottom: 8px;
}

.tree-search {
  padding: 10px 14px;
  background: #fff;
  border-bottom: 1px solid var(--border-color, #ebeef5);
}

.tree-search :deep(.el-input__wrapper) {
  border-radius: 8px;
  background: var(--bg-color, #f0f2f5);
  box-shadow: none;
  transition: var(--transition, all 0.25s);
}
.tree-search :deep(.el-input__wrapper:hover),
.tree-search :deep(.el-input__wrapper.is-focus) {
  background: #fff;
  box-shadow: 0 0 0 1px var(--primary, #409eff) inset;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: #c0c4cc;
}

.empty-state p {
  margin-top: 10px;
  font-size: 13px;
}

.tree-node {
  display: flex;
  align-items: center;
  width: 100%;
  font-size: 13px;
  gap: 8px;
  padding-right: 6px;
}

.node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary, #303133);
  font-weight: 500;
}

.node-code {
  color: #a8abb2;
  font-size: 11px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  flex-shrink: 0;
}

.node-amount {
  color: var(--primary, #409eff);
  font-size: 11px;
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 72px;
  text-align: right;
}

:deep(.el-tree-node__content) {
  height: 34px;
  padding-right: 10px;
  border-radius: 6px;
  margin: 2px 6px;
  transition: var(--transition, all 0.2s);
}

:deep(.el-tree-node__content:hover) {
  background-color: #eef3fc;
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: linear-gradient(135deg, #e8f0fe, #dce8fa);
  color: var(--primary, #409eff);
}

:deep(.el-tree-node.is-current > .el-tree-node__content .node-label) {
  color: var(--primary, #409eff);
  font-weight: 600;
}

:deep(.el-tree-node.is-current > .el-tree-node__content .node-code) {
  color: #7a8ba8;
}
</style>