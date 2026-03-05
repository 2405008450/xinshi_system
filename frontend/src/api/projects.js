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

export const getProjects = (params) => {
    return api.get('/projects/translation/', { params }).then(res => convertKeys(res, toCamelCase))
}

export const getProject = (id) => {
    return api.get(`/projects/translation/${id}`).then(res => convertKeys(res, toCamelCase))
}

export const createProject = (data) => {
    return api.post('/projects/translation/', convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const updateProject = (id, data) => {
    return api.put(`/projects/translation/${id}`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const deleteProject = (id) => {
    return api.delete(`/projects/translation/${id}`)
}

export const getNextOrderNo = () => {
    return api.get('/projects/translation/next-order-no').then(res => res.orderNo)
}
