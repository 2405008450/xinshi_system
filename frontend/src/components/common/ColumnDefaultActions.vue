<template>
  <div class="column-default-actions">
    <el-dropdown trigger="click" :teleported="false" @visible-change="opened => opened && refresh()" @command="handleCommand">
      <el-button link type="primary" :aria-label="`${title}：我的默认设置`">我的默认设置<el-icon class="column-default-actions__arrow"><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="save">保存当前字段为我的默认</el-dropdown-item>
          <el-dropdown-item command="restore" :disabled="!hasMyDefault">恢复我的默认</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
    <el-button link type="primary" @click="$emit('reset')">恢复系统默认</el-button>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createTableColumnDefaults } from '@/utils/tableColumnDefaults'
import { useTableColumnOrder } from '@/composables/useTableColumnOrder'

const props = defineProps({
  settingsKey: { type: String, required: true },
  section: { type: String, default: 'main' },
  title: { type: String, default: '主表字段' },
  columns: { type: Array, required: true },
  selectedKeys: { type: Array, required: true },
})
const emit = defineEmits(['apply', 'reset'])
const hasMyDefault = ref(false)
const { order, setOrder, resetOrder } = useTableColumnOrder(computed(() => props.settingsKey), computed(() => props.section))
function defaults() {
  return createTableColumnDefaults({
    moduleKey: props.settingsKey, section: props.section,
    userKey: localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous',
  })
}
function refresh() { try { hasMyDefault.value = defaults().has() } catch { hasMyDefault.value = false } }
function handleCommand(command) {
  try {
    if (command === 'save') {
      defaults().save(props.selectedKeys, props.columns, order.value)
      hasMyDefault.value = true
      ElMessage.success(`${props.title}已保存为我的默认设置`)
    } else if (command === 'restore') {
      const keys = defaults().restore(props.columns)
      if (keys === null) { refresh(); ElMessage.info('请先保存我的默认设置'); return }
      const savedOrder = defaults().restoreOrder()
      if (savedOrder) setOrder(savedOrder)
      else resetOrder()
      emit('apply', keys)
      ElMessage.success(`已恢复${props.title}的我的默认设置`)
    }
  } catch { ElMessage.error('无法读写我的默认设置，请检查浏览器存储后重试') }
}
watch(() => [props.settingsKey, props.section], refresh, { immediate: true })
</script>

<style scoped>
.column-default-actions{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px 12px}
.column-default-actions>.el-button+.el-button{margin-left:0}
.column-default-actions__arrow{margin-left:4px}
</style>
