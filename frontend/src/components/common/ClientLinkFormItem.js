import { defineComponent, h, inject } from 'vue'
import { ElFormItem, formContextKey } from 'element-plus'
// 通过包装组件加载时，按需解析器只引入表单容器样式；字段样式包含必填星号。
import 'element-plus/es/components/form-item/style/css'
import ClientManagementLink from './ClientManagementLink.vue'
import { formatClientWithSubClient, isClientShortName } from '@/utils/clientManagementWindow'

export default defineComponent({
  inheritAttrs: false,
  setup(_, { attrs, slots, expose }) {
    const form = inject(formContextKey, null)
    let item
    expose({
      validate: (...args) => item?.validate(...args),
      clearValidate: () => item?.clearValidate(),
      resetField: () => item?.resetField(),
    })
    return () => {
      const { 'show-sub-client': showSubClient, ...itemAttrs } = attrs
      const row = form?.model
      const key = attrs.prop || (attrs.label === '子客户简称' ? 'subClientShortName' : 'clientShortName')
      const path = Array.isArray(key) ? key : String(key).split('.')
      const value = path.reduce((current, part) => current?.[part], row) ?? row?.client_short_name ?? row?._client_short_name
      const fieldSlots = { ...slots }
      if (value && attrs.label && isClientShortName(attrs.label, attrs.prop) && !slots.label) {
        fieldSlots.label = () => h(ClientManagementLink, {
          value, row, label: attrs.label, subClient: attrs.label === '子客户简称' || /^sub_?client/i.test(String(key)),
        })
      }
      if ((showSubClient === '' || showSubClient === true) && (row?.subClientName || row?.subClientShortName)) {
        fieldSlots.default = () => [
          ...(slots.default?.() || []),
          h('small', {
            style: { flexBasis: '100%', lineHeight: '1.5', marginTop: '4px', color: 'var(--el-text-color-secondary)' },
          }, formatClientWithSubClient(row, value)),
        ]
      }
      return h(ElFormItem, { ...itemAttrs, ref: el => { item = el } }, fieldSlots)
    }
  },
})
