import { draftStringify } from './autoDraftStore.js'
import { copySavedValue } from './savedDataMerge.js'

const metadata = new Set([
  'id', 'nameGroup', 'attachments', 'wechatAccount', 'wechatAccountsOriginal', 'wechatAccountsRevision',
  'wecomSmallGroupStatus', 'wecomLargeGroupStatus', 'evaluationMeta', 'evaluationOriginal',
])
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const withoutRowKeys = value => Array.isArray(value) ? value.map(withoutRowKeys) : isObject(value)
  ? Object.fromEntries(Object.entries(value).filter(([key]) => key !== '_key').map(([key, item]) => [key, withoutRowKeys(item)]))
  : value
const comparable = value => draftStringify(withoutRowKeys(value == null || value === '' ? null : value))
const equal = (left, right) => comparable(left) === comparable(right)

export function talentEditValues(form, fields, excluded = []) {
  return Object.fromEntries(fields.filter(key => Object.hasOwn(form, key) && !metadata.has(key) && !excluded.includes(key)).map(key => {
    const value = copySavedValue(form[key])
    if (['settlement', 'resumeProfile'].includes(key) && value) delete value.revision
    return [key, value]
  }))
}

export function mergeTalentEdit(latest, mine, original, unresolved = []) {
  const changes = []
  const unresolvedPaths = new Set(unresolved)
  function merge(saved, draft, base, path) {
    if (equal(draft, saved)) return saved
    const hasBase = Boolean(original)
    const pending = unresolvedPaths.has(path.join('.'))
    if (!pending && hasBase && equal(draft, base)) return saved
    if (!pending && isObject(saved) && isObject(draft) && (isObject(base) || base === undefined || !hasBase)) {
      const result = { ...saved }
      for (const key of new Set([...Object.keys(draft), ...Object.keys(base || {})])) {
        if (['__proto__', 'constructor', 'prototype', 'revision'].includes(key)) continue
        const value = merge(saved[key], draft[key], base?.[key], [...path, key])
        if (value === undefined) delete result[key]
        else result[key] = value
      }
      return result
    }
    if (pending || !hasBase || !equal(saved, base)) {
      changes.push({ path: path.join('.'), keys: path, current: draft, latest: saved })
    }
    return draft
  }
  const values = { ...latest }
  for (const key of Object.keys(latest)) {
    if (!Object.hasOwn(mine, key)) continue
    values[key] = merge(latest[key], mine[key], original?.[key], [key])
  }
  return { values, changes }
}
