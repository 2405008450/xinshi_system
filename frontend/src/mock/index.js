// Mock 系统配置
import {
  getMockClients,
  getMockTranslators,
  getMockSubsidiaryClients,
  getMockClientContacts,
  getMockConsultations,
  delay
} from './data'

// 检查是否启用 Mock 模式
// 可以通过 localStorage 或环境变量控制
export const isMockEnabled = () => {
  // 优先检查 localStorage
  const mockSetting = localStorage.getItem('USE_MOCK')
  if (mockSetting !== null) {
    return mockSetting === 'true'
  }
  // 默认在开发环境启用
  return import.meta.env.MODE === 'development'
}

// Mock API 响应生成器
export const createMockResponse = (data, options = {}) => {
  const { delay: delayMs = 300, error = false, errorMessage = null } = options
  
  return delay(delayMs).then(() => {
    if (error) {
      return Promise.reject({ 
        detail: errorMessage || '模拟错误',
        message: errorMessage || '模拟错误'
      })
    }
    return data
  })
}

// 分页处理
export const paginate = (data, skip = 0, limit = 10) => {
  const start = skip
  const end = start + limit
  return data.slice(start, end)
}

// 搜索过滤
export const filter = (data, searchKey, searchValue) => {
  if (!searchValue) return data
  return data.filter(item => {
    const value = item[searchKey]
    return value && value.toString().toLowerCase().includes(searchValue.toLowerCase())
  })
}

// Mock API 实现
export const mockApi = {
  // 客户相关
  clients: {
    get: async (params = {}) => {
      let data = [...getMockClients()] // 创建副本避免修改原数组
      
      // 搜索过滤
      if (params.search) {
        data = filter(data, 'client_name', params.search)
      }
      
      // 保存总数
      const total = data.length
      
      // 分页
      const skip = params.skip || 0
      const limit = params.limit || 10
      const paginated = paginate(data, skip, limit)
      
      // 返回数据，前端会使用数组长度作为总数
      return createMockResponse(paginated, { delay: 200 })
    },
    
    getById: async (id) => {
      const data = getMockClients()
      const item = data.find(c => c.id === id)
      if (!item) {
        return createMockResponse(null, { error: true, errorMessage: '客户不存在' })
      }
      return createMockResponse(item, { delay: 150 })
    },
    
    create: async (data) => {
      const clients = getMockClients()
      const newClient = {
        id: `mock-${Date.now()}`,
        ...data,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      clients.push(newClient)
      return createMockResponse(newClient, { delay: 400 })
    },
    
    update: async (id, data) => {
      const clients = getMockClients()
      const index = clients.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '客户不存在' })
      }
      clients[index] = { ...clients[index], ...data, updated_at: new Date().toISOString() }
      return createMockResponse(clients[index], { delay: 400 })
    },
    
    delete: async (id) => {
      const clients = getMockClients()
      const index = clients.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '客户不存在' })
      }
      clients.splice(index, 1)
      return createMockResponse({ success: true }, { delay: 300 })
    }
  },
  
  // 译员相关
  translators: {
    get: async (params = {}) => {
      let data = [...getMockTranslators()] // 创建副本
      
      if (params.search) {
        data = filter(data, 'name', params.search)
      }
      
      const skip = params.skip || 0
      const limit = params.limit || 10
      const paginated = paginate(data, skip, limit)
      
      return createMockResponse(paginated, { delay: 200 })
    },
    
    getById: async (id) => {
      const data = getMockTranslators()
      const item = data.find(t => t.id === id)
      if (!item) {
        return createMockResponse(null, { error: true, errorMessage: '译员不存在' })
      }
      return createMockResponse(item, { delay: 150 })
    },
    
    create: async (data) => {
      const translators = getMockTranslators()
      const newTranslator = {
        id: `mock-${Date.now()}`,
        ...data,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      translators.push(newTranslator)
      return createMockResponse(newTranslator, { delay: 400 })
    },
    
    update: async (id, data) => {
      const translators = getMockTranslators()
      const index = translators.findIndex(t => t.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '译员不存在' })
      }
      translators[index] = { ...translators[index], ...data, updated_at: new Date().toISOString() }
      return createMockResponse(translators[index], { delay: 400 })
    },
    
    delete: async (id) => {
      const translators = getMockTranslators()
      const index = translators.findIndex(t => t.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '译员不存在' })
      }
      translators.splice(index, 1)
      return createMockResponse({ success: true }, { delay: 300 })
    }
  },
  
  // 子公司客户相关
  subsidiaryClients: {
    get: async (params = {}) => {
      let data = [...getMockSubsidiaryClients()] // 创建副本
      
      if (params.search) {
        data = filter(data, 'client_name', params.search)
      }
      
      const skip = params.skip || 0
      const limit = params.limit || 10
      const paginated = paginate(data, skip, limit)
      
      return createMockResponse(paginated, { delay: 200 })
    },
    
    getById: async (id) => {
      const data = getMockSubsidiaryClients()
      const item = data.find(c => c.id === id)
      if (!item) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      return createMockResponse(item, { delay: 150 })
    },
    
    create: async (data) => {
      const subsidiaryClients = getMockSubsidiaryClients()
      const newItem = {
        id: `mock-${Date.now()}`,
        ...data
      }
      subsidiaryClients.push(newItem)
      return createMockResponse(newItem, { delay: 400 })
    },
    
    update: async (id, data) => {
      const subsidiaryClients = getMockSubsidiaryClients()
      const index = subsidiaryClients.findIndex(item => item.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      subsidiaryClients[index] = { ...subsidiaryClients[index], ...data }
      return createMockResponse(subsidiaryClients[index], { delay: 400 })
    },
    
    delete: async (id) => {
      const subsidiaryClients = getMockSubsidiaryClients()
      const index = subsidiaryClients.findIndex(item => item.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      subsidiaryClients.splice(index, 1)
      return createMockResponse({ success: true }, { delay: 300 })
    }
  },
  
  // 客户联系人及回访相关
  clientContacts: {
    get: async (params = {}) => {
      let data = [...getMockClientContacts()] // 创建副本
      
      if (params.search) {
        data = filter(data, 'client_name', params.search)
      }
      
      const skip = params.skip || 0
      const limit = params.limit || 10
      const paginated = paginate(data, skip, limit)
      
      return createMockResponse(paginated, { delay: 200 })
    },
    
    getById: async (id) => {
      const data = getMockClientContacts()
      const item = data.find(c => c.id === id)
      if (!item) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      return createMockResponse(item, { delay: 150 })
    },
    
    create: async (data) => {
      const contacts = getMockClientContacts()
      const newContact = {
        id: `mock-${Date.now()}`,
        ...data,
        updated_at: new Date().toISOString()
      }
      contacts.push(newContact)
      return createMockResponse(newContact, { delay: 400 })
    },
    
    update: async (id, data) => {
      const contacts = getMockClientContacts()
      const index = contacts.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      contacts[index] = { ...contacts[index], ...data, updated_at: new Date().toISOString() }
      return createMockResponse(contacts[index], { delay: 400 })
    },
    
    delete: async (id) => {
      const contacts = getMockClientContacts()
      const index = contacts.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      contacts.splice(index, 1)
      return createMockResponse({ success: true }, { delay: 300 })
    }
  },
  
  // 咨询相关
  consultations: {
    get: async (params = {}) => {
      let data = [...getMockConsultations()] // 创建副本
      
      if (params.search) {
        data = filter(data, 'client_name', params.search)
      }
      
      const skip = params.skip || 0
      const limit = params.limit || 10
      const paginated = paginate(data, skip, limit)
      
      return createMockResponse(paginated, { delay: 200 })
    },
    
    getById: async (id) => {
      const data = getMockConsultations()
      const item = data.find(c => c.id === id)
      if (!item) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      return createMockResponse(item, { delay: 150 })
    },
    
    create: async (data) => {
      const consultations = getMockConsultations()
      const newConsultation = {
        id: `mock-${Date.now()}`,
        ...data,
        updated_at: new Date().toISOString()
      }
      consultations.push(newConsultation)
      return createMockResponse(newConsultation, { delay: 400 })
    },
    
    update: async (id, data) => {
      const consultations = getMockConsultations()
      const index = consultations.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      consultations[index] = { ...consultations[index], ...data, updated_at: new Date().toISOString() }
      return createMockResponse(consultations[index], { delay: 400 })
    },
    
    delete: async (id) => {
      const consultations = getMockConsultations()
      const index = consultations.findIndex(c => c.id === id)
      if (index === -1) {
        return createMockResponse(null, { error: true, errorMessage: '记录不存在' })
      }
      consultations.splice(index, 1)
      return createMockResponse({ success: true }, { delay: 300 })
    }
  }
}
