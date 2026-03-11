import api from './index'

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

export const createSubOrder = (data) => {
    return api.post('/sub-orders/', convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const updateSubOrder = (id, data) => {
    return api.put(`/sub-orders/${id}`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const deleteSubOrder = (id) => {
    return api.delete(`/sub-orders/${id}`)
}
