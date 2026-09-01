import Schema from 'async-validator'

const validationMessages = {
  default: '字段校验失败',
  required: '此项为必填项',
  enum: '请选择有效值',
  whitespace: '内容不能为空',
  date: {
    format: '日期格式不正确',
    parse: '日期无法解析',
    invalid: '日期无效'
  },
  types: {
    string: '请输入文本',
    method: '内容格式不正确',
    array: '请选择有效内容',
    object: '内容格式不正确',
    number: '请输入数字',
    date: '请选择有效日期',
    boolean: '请选择有效状态',
    integer: '请输入整数',
    float: '请输入数字',
    regexp: '内容格式不正确',
    email: '请输入有效的邮箱地址',
    url: '请输入有效的网址',
    hex: '请输入有效的十六进制值'
  },
  string: {
    len: '内容长度必须为 %s 个字符',
    min: '内容不能少于 %s 个字符',
    max: '内容不能超过 %s 个字符',
    range: '内容长度必须在 %s 到 %s 个字符之间'
  },
  number: {
    len: '数值必须等于 %s',
    min: '数值不能小于 %s',
    max: '数值不能大于 %s',
    range: '数值必须在 %s 到 %s 之间'
  },
  array: {
    len: '必须选择 %s 项',
    min: '至少选择 %s 项',
    max: '最多选择 %s 项',
    range: '请选择 %s 到 %s 项'
  },
  pattern: {
    mismatch: '内容格式不正确'
  }
}

const mergeMessages = (target, source) => {
  Object.entries(source).forEach(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      target[key] = target[key] || {}
      mergeMessages(target[key], value)
    } else {
      target[key] = value
    }
  })
}

export function installChineseValidationMessages() {
  mergeMessages(Schema.messages, validationMessages)
}

export { validationMessages }
