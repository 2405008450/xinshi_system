import { computed, ref, unref, watch } from 'vue'
import { getCustomFields } from '@/api/annotationOps'

export function useAnnotationCustomFields(tableCode, projectId = ref(null)) {
  const fields = ref([])
  const loading = ref(false)

  const load = async () => {
    loading.value = true
    try {
      fields.value = await getCustomFields(tableCode, unref(projectId) || null)
    } finally {
      loading.value = false
    }
  }

  const tableColumns = computed(() => fields.value.map((field) => ({
    key: `custom:${field.id}`,
    label: field.fieldLabel,
    minWidth: field.dataType === 'text' || field.dataType === 'url' ? 160 : 110,
    customField: field,
  })))

  const valueFor = (row, field) => row?.customValues?.[field.id] ?? '-'
  watch(() => projectId?.value, load)
  return { fields, tableColumns, loading, load, valueFor }
}
