<template><TableColumnSettings v-model="selectedKeys" :columns="columns" :column-count="2" @reset="reset" /></template>
<script setup>
import { computed, watch } from 'vue'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import { useTableColumns } from '@/composables/useTableColumns'
const props = defineProps({ columns: { type: Array, required: true }, defaults: { type: Array, required: true } })
const emit = defineEmits(['change'])
const { selectedKeys, reset } = useTableColumns('talent-overview', computed(() => props.columns), computed(() => props.defaults))
watch(selectedKeys, keys => emit('change', keys), { deep: true, immediate: true })
</script>
