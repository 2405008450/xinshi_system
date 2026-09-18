<template>
  <el-popover
    trigger="click"
    placement="bottom-start"
    :width="420"
    title="人才储备"
    popper-class="annotation-language-reserve-popover"
  >
    <template #reference>
      <el-button type="primary" link class="language-reserve-link" @click.stop>
        {{ languageItem.display || fallbackDisplay }}
      </el-button>
    </template>

    <div v-loading="loading" class="language-reserve-content">
      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        title="人才储备加载失败"
        :description="error"
      />
      <div v-else class="language-reserve-list">
        <div v-for="endpoint in endpoints" :key="endpoint.id" class="language-reserve-item">
          <div v-if="endpoints.length > 1" class="language-reserve-name">{{ endpoint.role }}</div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="项目原始语种">
              {{ endpoint.label || '-' }}
            </el-descriptions-item>
            <template v-if="reserve(endpoint.id)?.matched">
              <el-descriptions-item label="人才概览语种">
                {{ reserve(endpoint.id).overviewLanguage }}
              </el-descriptions-item>
              <el-descriptions-item label="储备合计">
                <strong>{{ formatTalentCount(reserve(endpoint.id).total) }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="更新日期">
                {{ reserve(endpoint.id).updatedAt || '-' }}
              </el-descriptions-item>
            </template>
          </el-descriptions>
          <el-empty
            v-if="!loading && !reserve(endpoint.id)?.matched"
            :image-size="42"
            description="人才概览暂无可确定的对应语种"
          />
        </div>
      </div>
      <div v-if="!error" class="language-reserve-note">
        合计为人才概览各来源数量相加，不代表去重后的人才人数。
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { computed } from 'vue'
import { formatTalentCount } from '@/utils/talentOverview'

const props = defineProps({
  languageItem: { type: Object, required: true },
  reserves: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const endpoints = computed(() => [
  {
    id: props.languageItem.sourceLanguageId,
    label: props.languageItem.sourceLanguageLabel,
    role: props.languageItem.targetLanguageId ? '源语种' : '语种',
  },
  ...(props.languageItem.targetLanguageId ? [{
    id: props.languageItem.targetLanguageId,
    label: props.languageItem.targetLanguageLabel,
    role: '目标语种',
  }] : []),
].filter(item => item.id))

const fallbackDisplay = computed(() => endpoints.value.map(item => item.label).filter(Boolean).join('→') || '-')
const reserve = id => props.reserves[id]
</script>

<style scoped>
.language-reserve-link {
  height: auto;
  padding: 0;
  white-space: normal;
  text-align: left;
  line-height: 1.45;
}

.language-reserve-content {
  min-height: 72px;
}

.language-reserve-list {
  display: grid;
  gap: 12px;
}

.language-reserve-item + .language-reserve-item {
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.language-reserve-name {
  margin-bottom: 7px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.language-reserve-note {
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
</style>
