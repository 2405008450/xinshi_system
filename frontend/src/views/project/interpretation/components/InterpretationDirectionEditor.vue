<template>
  <div class="direction-panel">
    <div class="direction-header">
      <h4>
        口译方向
        <el-tag v-if="requiredTotal" size="small" type="info">合计 {{ requiredTotal }} 人</el-tag>
      </h4>
      <div class="direction-header__actions">
        <el-button link type="primary" @click="$emit('manage-languages')">管理语种</el-button>
        <el-button link type="primary" @click="$emit('create-language')">新增语种</el-button>
        <el-button type="primary" plain @click="addDirection">增加方向</el-button>
      </div>
    </div>

    <div v-for="(direction, directionIndex) in modelValue" :key="directionIndex" class="direction-row">
      <div class="language-chain" :aria-label="`口译方向 ${directionIndex + 1}`">
        <template v-for="(languageId, languageIndex) in direction.languageIds" :key="languageIndex">
          <span v-if="languageIndex" class="direction-arrow">↔</span>
          <div class="language-node">
            <el-select
              :model-value="languageId"
              filterable
              :placeholder="`语种 ${String.fromCharCode(65 + languageIndex)}`"
              @update:model-value="updateLanguage(directionIndex, languageIndex, $event)"
            >
              <el-option
                v-for="language in languages"
                :key="language.id"
                :label="language.label"
                :value="language.id"
                :disabled="language.isActive === false"
              >
                <span>{{ language.label }}</span>
                <el-tag v-if="language.isCustom" size="small" type="warning" class="language-tag">新</el-tag>
                <el-tag v-if="language.isActive === false" size="small" type="info" class="language-tag">已停用</el-tag>
              </el-option>
            </el-select>
            <el-button
              v-if="languageIndex >= 2"
              class="remove-language"
              link
              type="danger"
              :icon="CircleClose"
              :aria-label="`移除语种 ${languageIndex + 1}`"
              @click="removeLanguage(directionIndex, languageIndex)"
            />
          </div>
        </template>
        <el-button
          class="add-language"
          link
          type="primary"
          :icon="Plus"
          :disabled="direction.languageIds.length >= maxLanguages"
          @click="appendLanguage(directionIndex)"
        >
          {{ direction.languageIds.length >= maxLanguages ? `最多 ${maxLanguages} 个` : '增加语种' }}
        </el-button>
      </div>
      <div class="direction-actions">
        <el-input-number
          :model-value="direction.requiredCount"
          :min="1"
          :precision="0"
          class="direction-count"
          placeholder="需求人数"
          @update:model-value="updateCount(directionIndex, $event)"
        />
        <el-button link type="danger" @click="removeDirection(directionIndex)">删除</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { CircleClose, Plus } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  languages: { type: Array, default: () => [] },
  requiredTotal: { type: Number, default: 0 },
  maxLanguages: { type: Number, default: 5 },
})
const emit = defineEmits(['update:modelValue', 'manage-languages', 'create-language'])

const replaceDirection = (index, changes) => {
  const next = props.modelValue.map((item, itemIndex) => (
    itemIndex === index ? { ...item, ...changes } : item
  ))
  emit('update:modelValue', next)
}
const addDirection = () => emit('update:modelValue', [
  ...props.modelValue,
  { languageIds: ['', ''], requiredCount: null },
])
const removeDirection = (index) => emit(
  'update:modelValue', props.modelValue.filter((_item, itemIndex) => itemIndex !== index)
)
const updateLanguage = (directionIndex, languageIndex, value) => {
  const languageIds = [...props.modelValue[directionIndex].languageIds]
  languageIds[languageIndex] = value
  replaceDirection(directionIndex, { languageIds })
}
const appendLanguage = (directionIndex) => {
  const languageIds = [...props.modelValue[directionIndex].languageIds]
  if (languageIds.length >= props.maxLanguages) return
  languageIds.push('')
  replaceDirection(directionIndex, { languageIds })
}
const removeLanguage = (directionIndex, languageIndex) => {
  const languageIds = props.modelValue[directionIndex].languageIds.filter(
    (_item, itemIndex) => itemIndex !== languageIndex
  )
  replaceDirection(directionIndex, { languageIds })
}
const updateCount = (directionIndex, value) => replaceDirection(
  directionIndex, { requiredCount: value }
)
</script>

<style scoped>
.direction-header, .direction-row, .direction-actions, .language-chain, .language-node { display: flex; align-items: center; }
.direction-header { justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.direction-header h4 { margin: 0; }
.direction-header__actions, .direction-actions { display: flex; flex: none; align-items: center; gap: 8px; }
.direction-row { min-width: 0; gap: 10px; margin-bottom: 10px; }
.language-chain { min-width: 0; flex: 1; gap: 8px; overflow-x: auto; padding: 2px 2px 6px; }
.language-node { position: relative; flex: 0 0 180px; min-width: 180px; }
.language-node :deep(.el-select) { width: 100%; }
.language-node:has(.remove-language) :deep(.el-select__wrapper) { padding-right: 34px; }
.remove-language { position: absolute; right: 4px; z-index: 1; }
.add-language { flex: 0 0 auto; }
.direction-count { width: 140px; }
.direction-arrow { flex: 0 0 auto; color: var(--el-color-primary); font-size: 20px; font-weight: 700; }
.language-tag { margin-left: 6px; }

@media (max-width: 768px) {
  .direction-header { align-items: flex-start; flex-direction: column; }
  .direction-header__actions { width: 100%; flex-wrap: wrap; }
  .direction-row { align-items: stretch; flex-direction: column; }
  .direction-actions { justify-content: space-between; }
  .direction-count { width: min(220px, calc(100vw - 170px)); }
}
</style>
