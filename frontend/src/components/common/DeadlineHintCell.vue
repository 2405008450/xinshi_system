<template>
  <div class="deadline-cell" :title="formattedTime">
    <span class="deadline-cell__time">{{ formattedTime }}</span>
    <el-tag
      v-if="display.label"
      :type="display.type"
      size="small"
      :effect="tagEffect"
      class="deadline-cell__tag"
    >
      {{ display.label }}
    </el-tag>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatBusinessDateTime, getDeadlineHint } from '@/utils/deadlineDisplay'
import { useDeadlineNow } from '@/composables/useDeadlineNow'

const props = defineProps({
  deadline: { type: [String, Date, Number], default: '' },
  status: { type: String, default: '' },
  mode: { type: String, default: 'project' },
})

const nowTick = useDeadlineNow()
const formattedTime = computed(() => formatBusinessDateTime(props.deadline))
const display = computed(() => getDeadlineHint({
  deadline: props.deadline,
  status: props.status,
  mode: props.mode,
  now: nowTick.value,
}))
const tagEffect = computed(() => (
  display.value.type === 'danger' || display.value.type === 'warning' ? 'dark' : 'light'
))
</script>

<style scoped>
.deadline-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
  padding: 2px 0;
}

.deadline-cell__time {
  max-width: 100%;
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deadline-cell__tag {
  max-width: 100%;
  font-weight: 600;
}
</style>
