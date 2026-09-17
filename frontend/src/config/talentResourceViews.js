export const TALENT_RESOURCE_VIEWS = Object.freeze([
  {
    label: '人才概览',
    path: '/resource-management/talent-overview',
    permissions: ['talents:read', 'translators:read'],
  },
  {
    label: '人才总库',
    path: '/resource-management/talents',
    permissions: ['talents:read', 'translators:read'],
  },
  {
    label: '笔译资源',
    path: '/resource-management/translators',
    permissions: ['talents:read', 'translators:read'],
  },
  {
    label: '口译资源',
    path: '/resource-management/interpreters',
    permissions: ['talents:read', 'translators:read'],
  },
  {
    label: '标注员',
    path: '/resource-management/annotators',
    permissions: ['talents:read', 'translators:read'],
  },
  {
    label: '招聘人才库',
    path: '/resource-management/recruitment-talents',
    permissions: ['recruitment_talents:read'],
  },
])
