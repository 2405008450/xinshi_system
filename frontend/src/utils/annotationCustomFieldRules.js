const empty = value => value == null || value === '' || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && !value.length)

export function customFieldRules(field) {
  return [{
    required: Boolean(field.isRequired),
    trigger: ['change', 'blur'],
    validator: (_rule, value, callback) => {
      const fail = message => callback(new Error(`${field.fieldLabel}：${message}`))
      if (empty(value)) return field.isRequired ? fail('请填写此字段') : callback()
      if (field.dataType === 'url' && !/^https?:\/\//i.test(String(value).trim())) return fail('必须是 http/https 地址')
      if (field.dataType === 'number' && (typeof value !== 'number' || !Number.isFinite(value))) return fail('必须是有效数字')
      if (field.dataType === 'boolean' && typeof value !== 'boolean') return fail('请选择是或否')
      const options = (field.options || []).map(option => typeof option === 'object' ? option.value : option)
      if (field.dataType === 'single_select' && !options.includes(value)) return fail('请选择有效选项')
      if (field.dataType === 'multi_select' && (!Array.isArray(value) || value.some(item => !options.includes(item)))) return fail('请选择有效选项')
      callback()
    },
  }]
}
