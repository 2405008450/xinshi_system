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

export const getSubOrdersByProject = (projectId, signal) => {
    return api.get(`/sub-orders/project/${projectId}`, { signal }).then(res => convertKeys(res, toCamelCase))
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

export const createSubOrdersBulk = (data, config = {}) => {
    return api.post('/sub-orders/bulk', convertKeys(data, toSnakeCase), config).then(res => convertKeys(res, toCamelCase))
}

export const readSubOrderSourceFiles = (storagePath, signal) =>
    api.post('/sub-orders/source-files', { storage_path: storagePath }, { signal })

export const updateSubOrder = (id, data) => {
    return api.put(`/sub-orders/${id}`, convertKeys(data, toSnakeCase)).then(res => convertKeys(res, toCamelCase))
}

export const replaceSubOrderPaths = (projectId, data) =>
    api.post(`/sub-orders/project/${projectId}/replace-paths`, convertKeys(data, toSnakeCase))
        .then(response => convertKeys(response, toCamelCase))

export const deleteSubOrder = (id) => {
    return api.delete(`/sub-orders/${id}`)
}

export const inspectSharedSubOrderFolder = (storagePath, config = {}) => api.get('/sub-orders/shared-folder/inspect', { ...config, params: { storage_path: storagePath } }).then(res => convertKeys(res, toCamelCase))

export const inspectSharedSubOrderTree = (storagePath,config={}) => api.get('/sub-orders/shared-folder/tree',{...config,params:{storage_path:storagePath}}).then(res=>convertKeys(res,toCamelCase))
const folderImportState={key:'',signature:''}
export const importSubOrderFolders = async (data,config={}) => {
 const payload=convertKeys(data,toSnakeCase)
 const key=resolveIdempotencyKey(folderImportState,payload)
 const result=await api.post('/sub-orders/folders/import',payload,{timeout:120000,...config,headers:{...config.headers,'X-Idempotency-Key':key}})
 clearIdempotencyKey(folderImportState,key)
 return convertKeys(result,toCamelCase)
}
export const exportSubOrderTree = projectId => api.get(`/sub-orders/project/${projectId}/export`,{responseType:'blob'})

export const getFolderImportRecords = projectId => api.get(`/sub-orders/project/${projectId}/folder-import-records`).then(res=>convertKeys(res,toCamelCase))
export const parseSubOrderListFile = (file,config={}) => {const data=new FormData();data.append('file',file);return api.post('/sub-orders/import-list/parse',data,{timeout:60000,...config,headers:{...config.headers,'Content-Type':undefined}}).then(res=>convertKeys(res,toCamelCase))}
export const previewSubOrderList = (data,config={}) => api.post('/sub-orders/import-list/preview',convertKeys(data,toSnakeCase),config).then(res=>convertKeys(res,toCamelCase))
