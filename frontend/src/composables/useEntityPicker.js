import { computed, reactive, ref } from 'vue'

import { getProjects } from '@/api/projects'
import { getSubOrders } from '@/api/subOrders'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

const DEFAULT_PICKER_PAGE_SIZE = 10

function parseOrderNoParts(orderNo) {
  const matched = String(orderNo || '').match(/^[A-Z]+-(\d{6})-(\d+)$/i)
  return matched ? [parseInt(matched[1], 10), parseInt(matched[2], 10)] : [0, 0]
}

function orderNoComparator(getOrderNo) {
  return (left, right) => {
    const [leftDate, leftSeq] = parseOrderNoParts(getOrderNo(left))
    const [rightDate, rightSeq] = parseOrderNoParts(getOrderNo(right))
    return leftDate !== rightDate ? leftDate - rightDate : leftSeq - rightSeq
  }
}

export function useEntityPicker({
  currentEntityKey,
  currentEntityType,
  currentProjectId,
  currentSubOrder,
  selectedProjectRow,
  projectList,
  mixedEntityList
}) {
  const entityPickerVisible = ref(false)
  const entityPickerLoading = ref(false)
  const entityPickerTableRef = ref(null)
  const entityPickerRows = ref([])
  const entityPickerCurrentRow = ref(null)
  const entityPickerFilters = reactive({
    keyword: '',
    entityType: '',
    clientShortName: '',
    projectStatus: '',
    dateType: 'createdAt',
    dateRange: []
  })
  const entityPickerPagination = reactive({
    page: 1,
    pageSize: DEFAULT_PICKER_PAGE_SIZE
  })
  const pickerStatusOptions = [
    { label: '待启动', value: 'pending' },
    { label: '进行中', value: 'in_progress' },
    { label: '已完成', value: 'completed' },
    { label: '已暂停', value: 'paused' },
    { label: '已终止', value: 'terminated' }
  ]

  function buildEntityKey(entity) {
    return entity?._type && entity?.id ? `${entity._type}:${entity.id}` : ''
  }

  function getEntityDisplayText(entity) {
    if (!entity) return ''

    if (entity._type === 'suborder') {
      const orderNo = entity.subOrderNo || entity.sub_order_no || '-'
      const projectName = entity.subProjectName || entity.sub_project_name || entity.projectName || entity.project_name || ''
      return `[子订单] ${orderNo}${projectName ? ` · ${projectName}` : ''}`
    }

    const orderNo = entity.orderNo || entity.order_no || '-'
    const projectName = entity.projectName || entity.project_name || ''
    return `[母订单] ${orderNo}${projectName ? ` · ${projectName}` : ''}`
  }

  function normalizeEntityRow(entity, type) {
    const row = { ...entity, _type: type }
    return {
      ...row,
      entityKey: `${type}:${row.id}`,
      orderNoDisplay: type === 'suborder'
        ? (row.subOrderNo || row.sub_order_no || row.orderNo || row.order_no || '-')
        : (row.orderNo || row.order_no || '-'),
      projectNameDisplay: type === 'suborder'
        ? (row.subProjectName || row.sub_project_name || row.projectName || row.project_name || '-')
        : (row.projectName || row.project_name || '-'),
      clientShortName: row.clientShortName || row.client_short_name || '-',
      projectStatus: row.projectStatus || row.project_status || 'pending',
      createdAt: formatDateTime(row.createdAt || row.created_at),
      customerDeadlineTime: formatDateTime(row.customerDeadlineTime || row.customer_deadline_time)
    }
  }

  function mergeProjectOptions(list) {
    const merged = Array.isArray(list) ? [...list] : []
    const current = selectedProjectRow.value || projectList.value.find((item) => String(item.id) === String(currentProjectId.value))
    if (current && !merged.some((item) => String(item.id) === String(current.id))) {
      merged.unshift({ ...current, _type: 'project' })
    }
    return merged
  }

  async function loadMixedOptions(query = '') {
    entityPickerLoading.value = true
    try {
      const projectParams = { skip: 0, limit: 50 }
      const subOrderParams = { skip: 0, limit: 50 }

      if (query) {
        if (/^TP[-\w]/i.test(query)) {
          projectParams.order_no = query
        } else {
          projectParams.project_name = query
        }

        if (/^SO[-\w]/i.test(query) || /^子/i.test(query)) {
          subOrderParams.sub_order_no = query
        } else {
          subOrderParams.project_name = query
        }
      }

      const [projectsRes, subOrdersRes] = await Promise.allSettled([
        getProjects(projectParams),
        getSubOrders(subOrderParams)
      ])

      const projects = (projectsRes.status === 'fulfilled' ? (Array.isArray(projectsRes.value) ? projectsRes.value : []) : [])
        .map((item) => ({ ...item, _type: 'project' }))
        .sort(orderNoComparator((item) => item.orderNo || item.order_no))

      const subOrders = (subOrdersRes.status === 'fulfilled' ? (Array.isArray(subOrdersRes.value) ? subOrdersRes.value : []) : [])
        .map((item) => ({ ...item, _type: 'suborder' }))
        .sort(orderNoComparator((item) => item.subOrderNo || item.sub_order_no))

      projectList.value = mergeProjectOptions(projects)

      const mergedEntities = [...projects, ...subOrders]
      if (currentEntityType.value === 'suborder' && currentSubOrder.value) {
        if (!mergedEntities.some((item) => item._type === 'suborder' && String(item.id) === String(currentSubOrder.value.id))) {
          mergedEntities.unshift({ ...currentSubOrder.value, _type: 'suborder' })
        }
      } else if (currentEntityType.value === 'project' && currentProjectId.value) {
        if (!mergedEntities.some((item) => item._type === 'project' && String(item.id) === String(currentProjectId.value))) {
          const current = selectedProjectRow.value || projectList.value.find((item) => String(item.id) === String(currentProjectId.value))
          if (current) {
            mergedEntities.unshift({ ...current, _type: 'project' })
          }
        }
      }

      mixedEntityList.value = mergedEntities
    } catch {
      projectList.value = mergeProjectOptions([])
      mixedEntityList.value = []
    } finally {
      entityPickerLoading.value = false
    }
  }

  async function loadEntityPickerOptions() {
    entityPickerLoading.value = true
    try {
      const keyword = (entityPickerFilters.keyword || '').trim()
      const projectParams = { skip: 0, limit: 200 }
      const subOrderParams = { skip: 0, limit: 200 }

      if (keyword) {
        if (/^TP[-\w]/i.test(keyword)) {
          projectParams.order_no = keyword
        } else {
          projectParams.project_name = keyword
        }

        if (/^SO[-\w]/i.test(keyword)) {
          subOrderParams.sub_order_no = keyword
        } else {
          subOrderParams.project_name = keyword
        }
      }

      if (entityPickerFilters.clientShortName) {
        projectParams.client_short_name = entityPickerFilters.clientShortName.trim()
      }

      if (entityPickerFilters.projectStatus) {
        projectParams.project_status = entityPickerFilters.projectStatus
      }

      const [projectsRes, subOrdersRes] = await Promise.allSettled([
        getProjects(projectParams),
        getSubOrders(subOrderParams)
      ])

      const projects = (projectsRes.status === 'fulfilled' ? (Array.isArray(projectsRes.value) ? projectsRes.value : []) : [])
        .map((item) => normalizeEntityRow(item, 'project'))
        .sort(orderNoComparator((item) => item.orderNoDisplay))

      const subOrders = (subOrdersRes.status === 'fulfilled' ? (Array.isArray(subOrdersRes.value) ? subOrdersRes.value : []) : [])
        .map((item) => normalizeEntityRow(item, 'suborder'))
        .sort(orderNoComparator((item) => item.orderNoDisplay))

      entityPickerRows.value = [...projects, ...subOrders]
      entityPickerPagination.page = 1
      entityPickerCurrentRow.value = entityPickerRows.value.find((item) => item.entityKey === currentEntityKey.value) || null
    } catch {
      entityPickerRows.value = []
      entityPickerCurrentRow.value = null
    } finally {
      entityPickerLoading.value = false
    }
  }

  function handleEntityPickerCurrentChange(row) {
    entityPickerCurrentRow.value = row || null
  }

  function resetEntityPickerFilters() {
    entityPickerFilters.keyword = ''
    entityPickerFilters.entityType = ''
    entityPickerFilters.clientShortName = ''
    entityPickerFilters.projectStatus = ''
    entityPickerFilters.dateType = 'createdAt'
    entityPickerFilters.dateRange = []
    entityPickerPagination.page = 1
    loadEntityPickerOptions()
  }

  async function openEntityPicker() {
    entityPickerVisible.value = true
    if (!entityPickerRows.value.length) {
      await loadEntityPickerOptions()
    } else {
      entityPickerCurrentRow.value = entityPickerRows.value.find((item) => item.entityKey === currentEntityKey.value) || null
    }
  }

  const entityPickerFilteredRows = computed(() => {
    const keyword = (entityPickerFilters.keyword || '').trim().toLowerCase()
    const clientShortName = (entityPickerFilters.clientShortName || '').trim().toLowerCase()
    const projectStatus = entityPickerFilters.projectStatus
    const entityType = entityPickerFilters.entityType
    const [startDate, endDate] = Array.isArray(entityPickerFilters.dateRange) ? entityPickerFilters.dateRange : []
    const dateField = entityPickerFilters.dateType || 'createdAt'

    return entityPickerRows.value.filter((row) => {
      if (entityType && row._type !== entityType) return false
      if (keyword) {
        const haystack = [row.orderNoDisplay, row.projectNameDisplay, row.clientShortName].join(' ').toLowerCase()
        if (!haystack.includes(keyword)) return false
      }
      if (clientShortName && !String(row.clientShortName || '').toLowerCase().includes(clientShortName)) return false
      if (projectStatus && row.projectStatus !== projectStatus) return false
      if (startDate && endDate) {
        const value = String(row[dateField] || '')
        const dateOnly = value && value !== '-' ? value.slice(0, 10) : ''
        if (!dateOnly || dateOnly < startDate || dateOnly > endDate) return false
      }
      return true
    })
  })

  const entityPickerTotal = computed(() => entityPickerFilteredRows.value.length)

  const entityPickerPagedRows = computed(() => {
    const start = (entityPickerPagination.page - 1) * entityPickerPagination.pageSize
    return entityPickerFilteredRows.value.slice(start, start + entityPickerPagination.pageSize)
  })

  return {
    pickerStatusOptions,
    entityPickerVisible,
    entityPickerLoading,
    entityPickerTableRef,
    entityPickerRows,
    entityPickerCurrentRow,
    entityPickerFilters,
    entityPickerPagination,
    entityPickerFilteredRows,
    entityPickerPagedRows,
    entityPickerTotal,
    buildEntityKey,
    getEntityDisplayText,
    loadMixedOptions,
    loadEntityPickerOptions,
    handleEntityPickerCurrentChange,
    resetEntityPickerFilters,
    openEntityPicker
  }
}
