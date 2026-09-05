import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'
import { invalidateOptionCache } from '@/utils/optionCache'

const projectCreateState = { key: '', signature: '' }

function toCamelCase(str) {
    return str.replace(/([-_][a-z])/g, (group) =>
        group.toUpperCase().replace('-', '').replace('_', '')
    )
}

function toSnakeCase(str) {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function convertKeys(obj, converter) {
    if (Array.isArray(obj)) {
        return obj.map(v => convertKeys(v, converter))
    } else if (obj !== null && obj.constructor === Object) {
        return Object.keys(obj).reduce((result, key) => {
            // API expects/returns strings and simple objects mostly, just recursively convert
            result[converter(key)] = convertKeys(obj[key], converter)
            return result
        }, {})
    }
    return obj
}

export const getProjects = (params, config = {}) => {
    return api.get('/projects/translation/', { ...config, params }).then(res => convertKeys(res, toCamelCase))
}

export const getProjectCount = (params, config = {}) => {
    return api.get('/projects/translation/count', { ...config, params })
}

export const getProjectPage = (params, config = {}) => {
    return api.get('/projects/translation/page', { ...config, params }).then(res => convertKeys(res, toCamelCase))
}

export const exportTranslationProjects = async (params) => {
    try {
        return await api.get('/projects/translation/export', {
            params,
            responseType: 'blob',
            timeout: 120000,
        })
    } catch (error) {
        const blob = error?.response?.data
        if (typeof Blob !== 'undefined' && blob instanceof Blob && blob.type?.includes('json')) {
            try {
                const payload = JSON.parse(await blob.text())
                if (payload?.detail) {
                    error.rawDetail = payload.detail
                    error.detail = payload.detail
                    error.message = payload.detail
                }
            } catch {
                // 保留统一错误处理给出的回退文案。
            }
        }
        throw error
    }
}

export const getProject = (id) => {
    return api.get(`/projects/translation/${id}`).then(res => convertKeys(res, toCamelCase))
}

export const createProject = async (data, idempotencyKey) => {
    const payload = convertKeys(data, toSnakeCase)
    const key = resolveIdempotencyKey(projectCreateState, payload, idempotencyKey)
    const response = await api.post('/projects/translation/', payload, {
        headers: { 'X-Idempotency-Key': key },
    })
    clearIdempotencyKey(projectCreateState, key)
    invalidateOptionCache('source-projects:translation:')
    return convertKeys(response, toCamelCase)
}

export const updateProject = (id, data) => {
    return api.put(`/projects/translation/${id}`, convertKeys(data, toSnakeCase)).then(res => {
        invalidateOptionCache('source-projects:translation:')
        return convertKeys(res, toCamelCase)
    })
}

export const deleteProject = (id) => {
    return api.delete(`/projects/translation/${id}`).then((res) => {
        invalidateOptionCache('source-projects:translation:')
        return res
    })
}

export const getNextOrderNo = () => {
    return api.get('/projects/translation/next-order-no').then(res => res.orderNo)
}

export const updateProjectTextField = (id, field, value, expectedUpdatedAt) => (
    api.patch(`/projects/translation/${id}/text-field`, {
        field: toSnakeCase(field),
        value,
        expected_updated_at: expectedUpdatedAt,
    }).then(res => convertKeys(res, toCamelCase))
)

let languageVariantsPromise

export const getLanguageVariants = () => {
    if (!languageVariantsPromise) {
        languageVariantsPromise = api
            .get('/projects/translation/language-variants')
            .catch((error) => {
                languageVariantsPromise = null
                throw error
            })
    }
    return languageVariantsPromise
}
