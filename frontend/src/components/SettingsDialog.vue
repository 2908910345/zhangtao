<template>
  <el-dialog :model-value="visible" title="设置" width="480px" top="25vh" @update:model-value="handleClose">
    <div class="settings-body">
      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">科目余额表显示带维度科目</div>
          <div class="setting-desc">开启后，科目余额表中会显示设有核算维度的科目行</div>
        </div>
        <el-switch
          :model-value="settings.showDimensionSubjects"
          @update:model-value="(v) => updateSetting('showDimensionSubjects', v)"
          active-text="显示"
          inactive-text="隐藏"
        />
      </div>

      <div class="setting-item">
        <div class="setting-info">
          <div class="setting-label">序时账与凭证显示对方科目</div>
          <div class="setting-desc">开启后，序时账和凭证中会显示同一凭证、同一摘要下的其他科目名称</div>
        </div>
        <el-switch
          :model-value="settings.showCounterpartSubject"
          @update:model-value="(v) => updateSetting('showCounterpartSubject', v)"
          active-text="显示"
          inactive-text="隐藏"
        />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { useSettings } from '../utils/settings.js'

defineProps({
  visible: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible'])

const { settings, updateSetting } = useSettings()

function handleClose() {
  emit('update:visible', false)
}
</script>

<style scoped>
.settings-body {
  padding: 8px 0;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: var(--transition, all 0.25s);
}
.setting-item:hover {
  background: #fafbfc;
  margin: 0 -12px;
  padding: 18px 12px;
  border-radius: 8px;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-info {
  flex: 1;
  margin-right: 24px;
}

.setting-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #303133);
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 12px;
  color: var(--text-secondary, #909399);
  line-height: 1.5;
}
</style>