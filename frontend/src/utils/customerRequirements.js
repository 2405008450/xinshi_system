export const requirementModules = {
  translation: { label: '笔译', fields: {
    customerRequirementProfessional: '客户专业要求',
    customerRequirementSpecial: '客户特殊要求',
    remarks: '补充说明',
  } },
  interpretation: { label: '口译', fields: {
    taskDescription: '具体任务',
    interpreterSpecialRequirements: '客户要求',
    remarks: '补充说明',
  } },
  annotation: { label: '标注', fields: {
    taskDescription: '具体任务',
    potentialDemand: '（潜在）需求量',
  } },
  recruitment: { label: '招聘', fields: {
    jobDescription: '岗位职责及任职要求',
    remarks: '补充说明',
  } },
}

export const requirementPath = (clientId, module) => `/clients/${clientId}/requirements/${module}`
