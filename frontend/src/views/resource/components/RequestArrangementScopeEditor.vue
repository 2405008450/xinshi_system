<template>
  <DraggableFormDialog v-model="visible" width="min(760px, calc(100vw - 32px))" top="5vh" class="request-arrangement-dialog" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="编辑安排内容" placeholder="搜索字段，如语言、城市、备注" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-alert v-if="invalidSelection" title="项目语言或城市已变化，请清除失效项后重新选择" type="warning" :closable="false"><el-button link type="primary" @click="clearInvalid">清除失效项</el-button></el-alert>
        <el-form-item label="语言／方言＋城市" prop="selected_scope_keys">
          <el-checkbox-group v-model="form.selected_scope_keys" class="request-scope-options">
            <el-checkbox v-for="item in options" :key="item.key" :value="item.key">{{ item.label }}</el-checkbox>
          </el-checkbox-group>
          <span v-if="!options.length" class="muted">未配置语种与城市，可填写安排备注</span>
        </el-form-item>
        <el-form-item label="安排备注" prop="arrangement_note"><el-input v-model="form.arrangement_note" type="textarea" :rows="5" maxlength="20000" show-word-limit placeholder="填写本次安排的补充要求" /></el-form-item>
      </AppForm>
    </div>
    <template #footer><el-button @click="beforeClose(() => visible = false)">取消</el-button><el-button type="primary" @click="confirm">确认</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
const props = defineProps({ options: { type: Array, default: () => [] } }), emit = defineEmits(['confirm'])
const visible = ref(false), bodyRef = ref(), formRef = ref()
const form = reactive({ selected_scope_keys: [], arrangement_note: '' })
const invalidSelection = computed(() => form.selected_scope_keys.some(key => !props.options.some(o => o.key === key)))
function clearInvalid() { form.selected_scope_keys = form.selected_scope_keys.filter(key => props.options.some(o => o.key === key)); formRef.value?.clearValidate() }
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, clearFieldSearch } = useDialogFieldSearch(bodyRef)
let baseline = ''
const rules = { selected_scope_keys: [{ validator: (_r, value, cb) => cb((props.options.length && !value.length) || invalidSelection.value ? new Error('请选择当前项目的语言与城市；已失效选项请重新选择') : undefined), trigger: 'change' }] }
function open(value) { Object.assign(form, { selected_scope_keys: [...value.selected_scope_keys], arrangement_note: value.arrangement_note }); baseline = JSON.stringify(form); clearFieldSearch(); visible.value = true }
async function beforeClose(done) { if (JSON.stringify(form) !== baseline) { try { await ElMessageBox.confirm('安排内容尚未确认，是否放弃修改？', '关闭安排内容', { type: 'warning' }) } catch { return } } done() }
async function confirm() { if (!await formRef.value.validate().catch(() => false)) return; emit('confirm', { selected_scope_keys: [...form.selected_scope_keys], arrangement_note: form.arrangement_note }); visible.value = false }
defineExpose({ open })
</script>
<style>
.request-scope-options { display: flex; flex-direction: column; width: 100%; }
.request-scope-options .el-checkbox { height: auto; min-height: 32px; margin-right: 0; }
.request-scope-options .el-checkbox__label { white-space: normal; overflow-wrap: anywhere; }
</style>
