import api from './index'
import { clearIdempotencyKey, resolveIdempotencyKey } from '@/utils/idempotency'

const subOrderCreateState = { key: '', signature: '' }

function toCamelCase(str) {
    return str.replace(/([-_][a-z])/g, (group) =>
        group.toUpperCase().replace('-', '').replace('_', '')
    )
}

function toSnakeCase(str) {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

function convertKeys(obj, converter) {
    if (obj === null || obj === undefined) {
        return obj
    }
    if (Array.isArray(obj)) {
        return obj.map(v => convertKeys(v, converter))
    } else if (obj.constructor === Object) {
        return Object.keys(obj).reduce((result, key) => {
            result[converter(key)] = convertKeys(obj[key], converter)
            return result
        }, {})
    }
    return obj
}

export const getSubOrders = (params) => {
    return api.get('/sub-orders/', { params }).then(res => convertKeys(res, toCamelCase))
}

export const getSubOrdersByProject = (projectId) => {
    return api.get(`/sub-orders/project/${projectId}`).then(res => convertKeys(res, toCamelCase))
}

export const getSubOrder = (id) => {
    return api.get(`/sub-orders/${id}`).then(res => convertKeys(res, toCamelCase))
}

export const createSubOrder = async (data) => {
    const payload = convertKeys(data, toSnakeCase)
    const key = resolveIdempotencyKey(subOrderCreateState, payload)
    const response = await api.post('/sub-orders/', payload, {
        headers: { 'X-Idempotency-Key': key },
    })
    clearIdempotencyKey(subOrderCreateState, key)
    return convertKeys(response, toCamelCase)
}

export const updateSubOrder = (id, data) => {
    return api.put(`/sub-orders/${id}`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const deleteSubOrder = (id) => {
    return api.delete(`/sub-orders/${id}`)
}
