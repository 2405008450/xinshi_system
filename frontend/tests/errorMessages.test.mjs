import test from 'node:test'
import assert from 'node:assert/strict'

import {
  formatValidationErrors,
  getLocalizedErrorMessage,
  normalizeApiError,
} from '../src/utils/errorMessages.js'

test('必填、类型和长度错误使用业务字段中文提示', () => {
  const message = formatValidationErrors([
    { type: 'missing', loc: ['body', 'project_intake', 'locations'], msg: 'Field required' },
    { type: 'int_parsing', loc: ['body', 'headcount_min'], msg: 'Input should be a valid integer' },
    { type: 'string_too_long', loc: ['body', 'project_name'], ctx: { max_length: 20 } },
  ])

  assert.equal(message, '地点为必填项；招聘人数应为有效数字；项目名称不能超过 20 个字符')
})

test('未知接口字段不暴露字段路径', () => {
  const message = formatValidationErrors([
    { type: 'missing', loc: ['body', 'internal_field_name'], msg: 'Field required' },
  ])

  assert.equal(message, '相关字段为必填项')
  assert.doesNotMatch(message, /internal_field_name/)
})

test('结构化业务错误保存在 rawDetail，展示字段保持中文字符串', () => {
  const rawDetail = { message: '发现重复人才', duplicate_ids: ['talent-1'] }
  const error = {
    response: { status: 409, data: { detail: rawDetail } },
    message: 'Request failed with status code 409',
  }

  const normalized = normalizeApiError(error)

  assert.equal(normalized.detail, '发现重复人才')
  assert.equal(normalized.message, '发现重复人才')
  assert.equal(normalized.rawDetail, rawDetail)
  assert.equal(normalized.response.data.detail, '发现重复人才')
})

test('HTTP、网络和超时异常使用统一中文兜底', () => {
  assert.equal(getLocalizedErrorMessage({ response: { status: 401 } }), '登录状态已失效，请重新登录')
  assert.equal(getLocalizedErrorMessage({ response: { status: 503 } }), '服务暂时不可用，请稍后重试')
  assert.equal(normalizeApiError({ code: 'ERR_NETWORK', message: 'Network Error' }).message, '网络异常，请检查网络后重试')
  assert.equal(normalizeApiError({ code: 'ECONNABORTED', message: 'timeout of 10000ms exceeded' }).message, '请求超时，请稍后重试')
})

test('数据库和未知技术信息不会直接展示', () => {
  const error = {
    response: { status: 500, data: { detail: '保存失败：SQLAlchemy IntegrityError duplicate key' } },
  }

  assert.equal(normalizeApiError(error).message, '服务暂时异常，请稍后重试')
})
