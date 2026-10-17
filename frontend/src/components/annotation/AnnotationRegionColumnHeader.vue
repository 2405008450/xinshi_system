<template>
  <ConfiguredColumnHeaderFilter :definition="definition" :model="model" @update-field="(key,value) => $emit('update-field',key,value)" @text-input="$emit('text-input',$event)" @change="$emit('change')" @enter="$emit('enter')" @clear="$emit('clear')">
    <template #label>
      <el-dropdown trigger="click" @command="$emit('update:level',$event)">
        <button type="button" class="annotation-region-level-switch" aria-label="地区显示层级" title="切换列表默认显示的地区层级" @click.stop>
          {{ annotationRegionLevelLabel(level) }}<el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="item in annotationRegionLevels" :key="item.value" :command="item.value" :class="{ 'is-active-region-level': item.value === level }">{{ item.label }}</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
    </template>
  </ConfiguredColumnHeaderFilter>
</template>

<script setup>
import { ArrowDown } from '@element-plus/icons-vue'
import ConfiguredColumnHeaderFilter from '@/components/common/ConfiguredColumnHeaderFilter.vue'
import { annotationRegionLevels, annotationRegionLevelLabel } from '@/utils/annotationRegionDisplay'

defineProps({ level: { type: String, default: 'city' }, definition: { type: Object, required: true }, model: { type: Object, required: true } })
defineEmits(['update:level','update-field','text-input','change','enter','clear'])
</script>

<style scoped>
.annotation-region-level-switch { display:inline-flex; align-items:center; gap:5px; padding:0; border:0; color:inherit; background:transparent; cursor:pointer; font:inherit; }
.annotation-region-level-switch .el-icon { width:10px; font-size:10px; }
.annotation-region-level-switch:focus-visible { outline:2px solid var(--el-color-primary); outline-offset:2px; }
</style>
<style>
.is-active-region-level { color:var(--el-color-primary)!important; font-weight:600; }
</style>
