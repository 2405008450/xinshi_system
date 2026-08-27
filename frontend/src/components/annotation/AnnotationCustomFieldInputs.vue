<template>
  <el-form-item
    v-for="field in fields"
    :key="field.id"
    :label="field.fieldLabel"
    :required="field.isRequired"
  >
    <el-switch
      v-if="field.dataType === 'boolean'"
      v-model="values[field.id]"
    />
    <AnnotationCustomFieldImage
      v-else-if="field.dataType === 'image'"
      ref="imageEditors"
      v-model="values[field.id]"
      :project-id="projectId"
      :field-id="field.id"
    />
    <el-input-number
      v-else-if="field.dataType === 'number'"
      v-model="values[field.id]"
      style="width: 100%"
    />
    <el-date-picker
      v-else-if="field.dataType === 'date'"
      v-model="values[field.id]"
      value-format="YYYY-MM-DD"
      style="width: 100%"
    />
    <el-date-picker
      v-else-if="field.dataType === 'datetime'"
      v-model="values[field.id]"
      type="datetime"
      value-format="YYYY-MM-DDTHH:mm:ss"
      style="width: 100%"
    />
    <el-select
      v-else-if="field.dataType === 'single_select' || field.dataType === 'multi_select'"
      v-model="values[field.id]"
      :multiple="field.dataType === 'multi_select'"
      clearable
      style="width: 100%"
    >
      <el-option
        v-for="option in field.options || []"
        :key="option.value || option"
        :label="option.label || option"
        :value="option.value || option"
      />
    </el-select>
    <el-input
      v-else
      v-model="values[field.id]"
      :type="field.dataType === 'text' ? 'textarea' : 'text'"
      :rows="field.dataType === 'text' ? 3 : undefined"
    />
  </el-form-item>
</template>

<script setup>
import { ref } from 'vue'
import AnnotationCustomFieldImage from './AnnotationCustomFieldImage.vue'

const imageEditors = ref([])

defineProps({
  fields: { type: Array, default: () => [] },
  values: { type: Object, required: true },
  projectId: { type: String, default: '' },
})

const cleanupPending = async () => {
  await Promise.allSettled(imageEditors.value.map(editor => editor?.cleanupPending?.()))
}
const markSaved = () => imageEditors.value.forEach(editor => editor?.markSaved?.())

defineExpose({ cleanupPending, markSaved })
</script>
