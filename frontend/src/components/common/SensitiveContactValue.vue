<template>
  <el-tooltip
    v-if="restricted && hasValue"
    content="联系方式仅超级管理员可见"
    placement="top"
  >
    <span
      class="sensitive-contact-value is-restricted"
      aria-label="联系方式已隐藏"
      @copy.prevent.stop
      @cut.prevent.stop
      @dragstart.prevent.stop
      @contextmenu.prevent.stop
    >{{ maskedValue }}</span>
  </el-tooltip>
  <span v-else class="sensitive-contact-value">{{ displayValue }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: [String, Number], default: '' },
  restricted: { type: Boolean, default: false },
})

const hasValue = computed(() => props.value !== null && props.value !== undefined && props.value !== '')
const maskedValue = computed(() => hasValue.value ? '******' : '-')
const displayValue = computed(() => hasValue.value ? String(props.value) : '-')
</script>

<style scoped>
.sensitive-contact-value.is-restricted {
  cursor: not-allowed;
  user-select: none;
  -webkit-user-select: none;
}
</style>
