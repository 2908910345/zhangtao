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
      :data="filteredTree"
      :props="treeProps"
      node-key="code"
      highlight-current
      :expand-on-click-node="false"
      :filter-node-method="filterNode"
      @node-click="handleNodeClick"
      @node-dblclick="handleNodeDblclick"
      @node-contextmenu="handleContextMenu"
    >
      <template #default="{ data }">
        <span class="tree-node" :class="{ 'dim-node': data.is_dimension }">
          <el-icon v-if="data.is_dimension" class="dim-icon" :size="14"><PriceTag /></el-icon>
          <span class="node-label">{{ data.name }}</span>
          <span v-if="!data.is_dimension" class="node-code">{{ data.code }}</span>
          <span v-if="data.is_dimension && data.dimension" class="node-dim-type">
            维度
          </span>
          <span v-if="data.end_debit || data.end_credit" class="node-amount">
            {{ formatAmount(data.end_debit || data.end_credit) }}
          </span>
        </span>
      </template>
    </el-tree>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div
        v-if="contextMenuVisible"
        class="tree-context-menu"
        :style="{ left: contextMenuPos.x + 'px', top: contextMenuPos.y + 'px' }"
        @click.stop
        @mouseleave="closeContextMenu"
      >
        <div class="ctx-item" @click="expandAll">全部展开</div>
        <div class="ctx-item" @click="collapseAll">全部收缩</div>
      </div>
      <div
        v-if="contextMenuVisible"
        class="ctx-overlay"
        @click="closeContextMenu"
        @contextmenu.prevent="closeContextMenu"
      />
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Search, PriceTag } from '@element-plus/icons-vue'
import { formatAmount } from '../utils/format.js'

import { useSettings } from '../utils/settings.js'

const { settings } = useSettings()

const props = defineProps({
  treeData: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'dblclick'])

const treeRef = ref(null)
const searchText = ref('')
const treeProps = { children: 'children', label: 'name' }

function isAllZero(node) {
  return (!node.year_start_debit || node.year_start_debit === 0) &&
         (!node.year_start_credit || node.year_start_credit === 0) &&
         (!node.period_debit || node.period_debit === 0) &&
         (!node.period_credit || node.period_credit === 0) &&
         (!node.end_debit || node.end_debit === 0) &&
         (!node.end_credit || node.end_credit === 0)
}

function filterZeroNodes(nodes) {
  if (!nodes) return nodes
  const result = []
  for (const node of nodes) {
    // 浅拷贝，不修改原始对象
    const newNode = { ...node }
    let keep = !isAllZero(newNode)
    if (newNode.children && newNode.children.length > 0) {
      newNode.children = filterZeroNodes(newNode.children)
      if (newNode.children.length > 0) keep = true
    }
    if (keep) result.push(newNode)
  }
  return result
}

const filteredTree = computed(() => {
  if (!settings.hideZeroSubjects) return props.treeData
  return filterZeroNodes(props.treeData)
})

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

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuPos = ref({ x: 0, y: 0 })

function handleContextMenu(evt, data, node) {
  evt.preventDefault()
  contextMenuPos.value = { x: evt.clientX, y: evt.clientY }
  contextMenuVisible.value = true
}

function closeContextMenu() {
  contextMenuVisible.value = false
}

function getAllExpandableKeys(nodes) {
  const keys = []
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      keys.push(node.code)
      keys.push(...getAllExpandableKeys(node.children))
    }
  }
  return keys
}

function expandAll() {
  const keys = getAllExpandableKeys(filteredTree.value)
  treeRef.value.store.setDefaultExpandedKeys(keys)
  closeContextMenu()
}

function collapseAll() {
  Object.values(treeRef.value.store.nodesMap).forEach((node) => {
    if (node.childNodes && node.childNodes.length > 0) {
      node.collapse()
    }
  })
  closeContextMenu()
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

.tree-context-menu {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  padding: 4px 0;
  min-width: 120px;
}

.ctx-item {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  color: #303133;
  transition: background 0.15s;
}

.ctx-item:hover {
  background: #ecf5ff;
  color: #409eff;
}

.ctx-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
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
  gap: 6px;
  padding-right: 6px;
}

.tree-node.dim-node {
  font-size: 12px;
}

.dim-icon {
  color: #e6a23c;
  flex-shrink: 0;
}

.node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary, #303133);
  font-weight: 500;
}

.dim-node .node-label {
  font-weight: 400;
  color: #8c6d1f;
}

.node-code {
  color: #a8abb2;
  font-size: 11px;
  font-family: var(--font-number);
  flex-shrink: 0;
}

.node-dim-type {
  color: #e6a23c;
  font-size: 10px;
  background: #fdf6ec;
  padding: 1px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.node-amount {
  color: var(--primary, #409eff);
  font-size: 11px;
  font-family: var(--font-number);
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
