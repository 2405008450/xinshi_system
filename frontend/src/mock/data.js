// Mock 数据生成工具
// 使用简单的数据生成，不依赖外部库

// 简单的随机数据生成器
const random = {
  int: (min, max) => Math.floor(Math.random() * (max - min + 1)) + min,
  choice: (arr) => arr[Math.floor(Math.random() * arr.length)],
  uuid: () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
  date: {
    past: (years = 1) => {
      const date = new Date()
      date.setFullYear(date.getFullYear() - years)
      date.setDate(date.getDate() - random.int(0, 365))
      return date
    },
    recent: () => {
      const date = new Date()
      date.setDate(date.getDate() - random.int(0, 30))
      return date
    },
    between: ({ from, to }) => {
      const fromTime = from.getTime()
      const toTime = to.getTime()
      return new Date(fromTime + Math.random() * (toTime - fromTime))
    }
  },
  phone: () => `1${random.int(3, 9)}${random.int(100000000, 999999999)}`,
  email: (name) => `${name || random.string(8)}@${random.choice(['gmail', 'qq', '163', 'sina'])}.com`,
  string: (length) => {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
  },
  company: () => {
    const prefixes = ['科技', '贸易', '实业', '集团', '股份', '有限', '国际']
    const suffixes = ['公司', '企业', '集团', '有限公司']
    const names = ['华信', '天宇', '博达', '创新', '卓越', '恒通', '盛世', '宏图', '启航', '智联']
    return `${random.choice(names)}${random.choice(prefixes)}${random.choice(suffixes)}`
  },
  person: () => {
    const surnames = ['张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴']
    const names = ['伟', '芳', '娜', '敏', '静', '丽', '强', '磊', '军', '洋', '勇', '艳', '杰', '娟', '涛', '明', '超', '秀', '霞', '平']
    return `${random.choice(surnames)}${random.choice(names)}${random.choice(names)}`
  },
  lorem: {
    sentence: () => {
      const words = ['这是', '一个', '测试', '数据', '用于', '演示', '系统', '功能', '正常', '工作']
      return Array.from({ length: random.int(5, 10) }, () => random.choice(words)).join('') + '。'
    },
    paragraph: () => {
      return Array.from({ length: 3 }, () => random.lorem.sentence()).join('')
    }
  }
}

// 生成客户 Mock 数据
export const generateClients = (count = 20) => {
  const clients = []
  const statuses = ['active', 'inactive', 'pending']
  const provinces = ['北京', '上海', '广东', '江苏', '浙江', '山东', '四川', '湖北']
  const cities = {
    '北京': ['东城区', '西城区', '朝阳区', '海淀区'],
    '上海': ['黄浦区', '徐汇区', '长宁区', '静安区'],
    '广东': ['广州', '深圳', '珠海', '东莞'],
    '江苏': ['南京', '苏州', '无锡', '常州']
  }
  const fields1 = ['制造业', '服务业', '金融业', '科技', '教育', '医疗', '零售', '物流']
  const fields2 = {
    '制造业': ['汽车制造', '电子制造', '机械制造', '食品制造'],
    '服务业': ['咨询服务', '法律服务', '会计服务', '人力资源'],
    '金融业': ['银行', '保险', '证券', '投资'],
    '科技': ['软件开发', '互联网', '人工智能', '大数据']
  }

  for (let i = 0; i < count; i++) {
    const province = provinces[Math.floor(Math.random() * provinces.length)]
    const cityList = cities[province] || ['市辖区']
    const city = cityList[Math.floor(Math.random() * cityList.length)]
    const field1 = fields1[Math.floor(Math.random() * fields1.length)]
    const field2List = fields2[field1] || ['其他']
    const field2 = field2List[Math.floor(Math.random() * field2List.length)]
    
    const startDate = random.date.past(3)
    
    clients.push({
      id: random.uuid(),
      client_code: `CLI${String(i + 1).padStart(6, '0')}`,
      client_name: random.company(),
      client_short_name: random.company().substring(0, 8),
      client_manager: random.person(),
      manager_contact: random.phone(),
      field_level1: field1,
      field_level2: field2,
      country: '中国',
      province: province,
      city: city,
      district: random.choice(['区', '县', '市辖区']),
      client_status: random.choice(statuses),
      cooperation_start_date: startDate.toISOString().split('T')[0],
      remarks: random.lorem.sentence(),
      updated_at: random.date.recent().toISOString()
    })
  }
  return clients
}

// 生成译员 Mock 数据
export const generateTranslators = (count = 20) => {
  const translators = []
  const cooperationTypes = ['fulltime', 'parttime', 'freelance', 'outsource']
  const genders = ['male', 'female', 'other']
  const translatorTypes = ['interpreter', 'translator', 'simultaneous', 'consecutive']
  const languages = ['中英', '中日', '中韩', '中法', '中德', '中俄', '中意', '中西']
  const nationalities = ['中国', '美国', '英国', '日本', '韩国', '法国', '德国', '俄罗斯']

  for (let i = 0; i < count; i++) {
    const firstContact = random.date.past(2)
    
    translators.push({
      id: random.uuid(),
      translator_code: `TR${String(i + 1).padStart(6, '0')}`,
      name: random.person(),
      cooperation_type: random.choice(cooperationTypes),
      languages: random.choice(languages),
      gender: random.choice(genders),
      height: random.int(150, 190),
      appearance: random.choice(['优秀', '良好', '一般', '普通']),
      translator_type: random.choice(translatorTypes),
      nationality: random.choice(nationalities),
      ethnicity: random.choice(['汉族', '回族', '满族', '蒙古族', '其他']),
      overall_rating: random.choice(['优秀', '良好', '一般', '待评估']),
      overdue_count: random.int(0, 10),
      phone: random.phone(),
      phone2: random.phone(),
      email1: random.email(),
      email2: random.email(),
      resume_path: `/resumes/translator_${i + 1}.pdf`,
      other_contact: Math.random() > 0.7 ? random.phone() : '',
      first_contact_date: firstContact.toISOString().split('T')[0],
      remarks: random.lorem.sentence(),
      updated_at: random.date.recent().toISOString(),
      created_at: firstContact.toISOString()
    })
  }
  return translators
}

// 生成子公司客户 Mock 数据
export const generateSubsidiaryClients = (clients, count = 15) => {
  const subsidiaryClients = []
  const selectedClients = clients.slice(0, Math.min(count, clients.length))
  
  selectedClients.forEach((client, index) => {
    subsidiaryClients.push({
      id: random.uuid(),
      client_code: client.client_code,
      client_name: client.client_name,
      client_short_name: client.client_short_name
    })
  })
  
  return subsidiaryClients
}

// 生成客户联系人及回访 Mock 数据
export const generateClientContacts = (clients, count = 30) => {
  const contacts = []
  const visitTypes = ['phone', 'email', 'onsite', 'video', 'other']
  const attitudes = ['positive', 'neutral', 'negative', 'no_response']

  for (let i = 0; i < count; i++) {
    const client = random.choice(clients)
    const visitDate = random.date.past(1)
    const followUpDate = random.date.between({ 
      from: visitDate, 
      to: new Date() 
    })
    
    contacts.push({
      id: random.uuid(),
      client_code: client.client_code,
      client_name: client.client_name,
      client_short_name: client.client_short_name,
      client_manager: client.client_manager,
      manager_contact: client.manager_contact,
      visit_count: random.int(1, 20),
      visit_date: visitDate.toISOString().split('T')[0],
      visit_type: random.choice(visitTypes),
      client_attitude: random.choice(attitudes),
      description: random.lorem.paragraph(),
      follow_up_count: random.int(0, 10),
      follow_up_date: followUpDate.toISOString().split('T')[0],
      follow_up_status: random.lorem.sentence(),
      remarks: random.lorem.sentence(),
      updated_at: random.date.recent().toISOString()
    })
  }
  return contacts
}

// 生成咨询基本情况 Mock 数据
export const generateConsultations = (clients, count = 25) => {
  const consultations = []
  const methods = ['phone', 'email', 'online', 'onsite', 'other']
  const sources = ['website', 'search_engine', 'referral', 'social_media', 'exhibition', 'other']
  const statuses = ['pending', 'processing', 'converted', 'abandoned']
  const types = ['price', 'service', 'technical', 'cooperation', 'other']
  const keywords = ['翻译', '口译', '笔译', '同传', '本地化', '多语言']

  for (let i = 0; i < count; i++) {
    const client = random.choice(clients)
    const consultDate = random.date.past(1)
    
    consultations.push({
      id: random.uuid(),
      client_code: client.client_code,
      client_name: client.client_name,
      client_short_name: client.client_short_name,
      consultation_date: consultDate.toISOString().replace('T', ' ').substring(0, 19),
      consultation_method: random.choice(methods),
      client_source: random.choice(sources),
      source_keyword: random.choice(keywords),
      consultation_description: random.lorem.paragraph(),
      service_staff: random.person(),
      sales_staff: random.person(),
      consultation_status: random.choice(statuses),
      consultation_type: random.choice(types),
      remarks: random.lorem.sentence(),
      updated_at: random.date.recent().toISOString()
    })
  }
  return consultations
}

// 生成项目流程表 Mock 数据
export const generateTranslationProjects = (count = 30) => {
  const projects = []
  const projectStatuses = ['pending', 'in_progress', 'completed', 'paused']
  const cooperationTypes = ['全职', '兼职', '自由职业', '外包']
  const statMethods = ['按字数', '按页数', '按项目', '按小时']
  const fileTypes = ['合同', '技术文档', '法律文件', '商务文件', '学术论文', '其他']
  const progressStatuses = ['未开始', '进行中', '已完成', '待审核', '已审核']
  
  const clients = generateClients(20)
  
  for (let i = 0; i < count; i++) {
    const client = random.choice(clients)
    const receptionTime = random.date.past(0.5)
    const deadlineTime = random.date.between({
      from: receptionTime,
      to: new Date(receptionTime.getTime() + 30 * 24 * 60 * 60 * 1000)
    })
    const assignmentTime = random.date.between({
      from: receptionTime,
      to: deadlineTime
    })
    const sentTime = random.date.between({
      from: assignmentTime,
      to: deadlineTime
    })
    const createdAt = random.date.past(1)
    const updatedAt = random.date.between({
      from: createdAt,
      to: new Date()
    })
    
    const pad = (value) => String(value).padStart(2, '0')
    const formatDateTime = (date) => {
      const year = date.getFullYear()
      const month = pad(date.getMonth() + 1)
      const day = pad(date.getDate())
      const hour = pad(date.getHours())
      const minute = pad(date.getMinutes())
      const second = pad(date.getSeconds())
      return `${year}-${month}-${day} ${hour}:${minute}:${second}`
    }
    
    const generateOrderNo = () => {
      const now = new Date()
      const year = now.getFullYear()
      const month = pad(now.getMonth() + 1)
      const day = pad(now.getDate())
      const sequence = String(Math.floor(Math.random() * 10000)).padStart(4, '0')
      return `${year}${month}${day}${sequence}`
    }
    
    projects.push({
      id: random.uuid(),
      orderNo: generateOrderNo(),
      projectName: `${client.client_short_name}-${random.choice(['翻译项目', '文档翻译', '合同翻译', '技术文档翻译'])}-${i + 1}`,
      clientShortName: client.client_short_name,
      clientCode: client.client_code,
      projectStatus: random.choice(projectStatuses),
      customerReceptionTime: formatDateTime(receptionTime),
      customerDeadlineTime: formatDateTime(deadlineTime),
      translatorCooperationType: random.choice(cooperationTypes),
      translatorAssignee: random.person(),
      translatorAssignmentTime: formatDateTime(assignmentTime),
      translatorDeliveryProgress: random.choice(progressStatuses),
      review1Progress: random.choice(progressStatuses),
      preReviewQcProgress: random.choice(progressStatuses),
      layoutProgress: random.choice(progressStatuses),
      consolidationProgress: random.choice(progressStatuses),
      sentToClientTime: formatDateTime(sentTime),
      clientFeedback: random.choice(['满意', '基本满意', '需要修改', '待反馈', '']),
      postReviewQcProgress: random.choice(progressStatuses),
      review2Progress: random.choice(progressStatuses),
      reservedTranslatorStatMethod: random.choice(statMethods),
      reservedTranslatorWordCount: random.int(1000, 50000),
      fileTypeSecondary: random.choice(fileTypes),
      leadPmId: `PM${String(random.int(1, 10)).padStart(3, '0')}`,
      updatedAt: formatDateTime(updatedAt),
      createdAt: formatDateTime(createdAt)
    })
  }
  return projects
}

// 初始化所有 Mock 数据
let mockClients = null
let mockTranslators = null
let mockSubsidiaryClients = null
let mockClientContacts = null
let mockConsultations = null
let mockTranslationProjects = null

export const initMockData = () => {
  if (!mockClients) {
    mockClients = generateClients(30)
    mockTranslators = generateTranslators(25)
    mockSubsidiaryClients = generateSubsidiaryClients(mockClients, 15)
    mockClientContacts = generateClientContacts(mockClients, 40)
    mockConsultations = generateConsultations(mockClients, 35)
    mockTranslationProjects = generateTranslationProjects(30)
  }
}

export const getMockClients = () => {
  initMockData()
  return mockClients
}

export const getMockTranslators = () => {
  initMockData()
  return mockTranslators
}

export const getMockSubsidiaryClients = () => {
  initMockData()
  return mockSubsidiaryClients
}

export const getMockClientContacts = () => {
  initMockData()
  return mockClientContacts
}

export const getMockConsultations = () => {
  initMockData()
  return mockConsultations
}

export const getMockTranslationProjects = () => {
  initMockData()
  return mockTranslationProjects
}

// 模拟网络延迟
export const delay = (ms = 300) => {
  return new Promise(resolve => setTimeout(resolve, ms))
}
