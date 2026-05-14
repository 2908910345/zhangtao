<template>
  <div class="dimension-panel" v-loading="loading">
    <div v-if="!selectedSubject" class="empty-state">
      <el-icon :size="40"><Grid /></el-icon>
      <p>请在左侧选择一个科目查看核算维度</p>
    </div>

    <template v-else-if="Object.keys(groupedDimensions).length > 0">
      <div class="dim-subject-info">
        科目：<strong>{{ dimName }}</strong>
        <span class="dim-subject-code">{{ dimCode }}</span>
        <span class="dim-count">（{{ totalDimCount }} 条维度）</span>
      </div>

      <div class="dimension-groups">
        <div v-for="(group, type) in groupedDimensions" :key="type" class="dimension-group">
          <div class="group-header">{{ type }} ({{ group.length }})</div>
          <el-table :data="group" stripe size="small" style="width: 100%">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="value" label="维度值" show-overflow-tooltip>
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="filterByDim(type, row.value)">
                  {{ row.value }}
                </el-link>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </template>

    <div v-else-if="loaded" class="empty-state" style="padding: 32px">
      <p>该科目暂无核算维度数据</p>
    </div>

    <div v-else class="empty-state" style="padding: 32px">
      <p>加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getSubjectDimensions } from '../api/index.js'

const props = defineProps({
  selectedSubject: { type: Object, default: null },
})

const emit = defineEmits(['filter-dim'])

const dimensionData = ref(null)
const loading = ref(false)
const loaded = ref(false)
const dimCode = ref('')
const dimName = ref('')

watch(() => props.selectedSubject, (subject) => {
  if (subject) {
    loadDimensions(subject)
  } else {
    dimensionData.value = null
    loaded.value = false
  }
}, { immediate: true })

async function loadDimensions(subject) {
  loading.value = true
  loaded.value = false
  dimCode.value = subject.code
  dimName.value = subject.name
  try {
    const data = await getSubjectDimensions(subject.code)
    dimensionData.value = data
  } catch {
    dimensionData.value = null
  } finally {
    loading.value = false
    loaded.value = true
  }
}

const groupedDimensions = computed(() => {
  if (!dimensionData.value?.dimensions?.length) return {}
  const groups = {}
  for (const dim of dimensionData.value.dimensions) {
    if (!groups[dim.type]) groups[dim.type] = []
    groups[dim.type].push(dim)
  }
  return groups
})

const totalDimCount = computed(() => dimensionData.value?.dimensions?.length || 0)

function filterByDim(type, value) {
  emit('filter-dim', { code: dimCode.value, type, value })
}

defineExpose({ loadDimensions })
</script>

<style scoped>
.dimension-panel { height: 100%; }

.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 60px 20px; color: #c0c4cc;
}
.empty-state p { margin-top: 12px; font-size: 14px; }

.dim-subject-info {
  margin-bottom: 16px; font-size: 14px; color: var(--text-regular, #606266);
  display: flex; align-items: center; gap: 4px; font-weight: 500;
}
.dim-subject-code { color: var(--text-secondary, #909399); font-size: 12px; }
.dim-count { color: var(--primary, #409eff); font-size: 12px; }

.dimension-group {
  margin-bottom: 16px;
  border: 1px solid var(--border-color, #ebeef5);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: var(--shadow-sm, 0 1px 4px rgba(0,0,0,0.06));
}
.group-header {
  padding: 10px 14px; font-size: 13px; font-weight: 600;
  color: var(--primary, #409eff); background: #f0f6ff;
  border-bottom: 1px solid var(--border-color, #ebeef5);
  display: flex;
  align-items: center;
  gap: 6px;
}
.group-header::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 14px;
  background: var(--primary, #409eff);
  border-radius: 2px;
}

.dimension-group :deep(.el-table) {
  border: none;
  border-radius: 0;
}
</style>