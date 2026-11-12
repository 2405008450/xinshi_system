import { defineComponent, h, inject } from 'vue'
import { ElFormItem, formContextKey } from 'element-plus'
import ClientManagementLink from './ClientManagementLink.vue'
import { isClientShortName } from '@/utils/clientManagementWindow'

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
      return h(ElFormItem, { ...attrs, ref: el => { item = el } }, fieldSlots)
    }
  },
})
