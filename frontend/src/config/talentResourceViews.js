export const TALENT_RESOURCE_VIEWS = Object.freeze([
  {
    label: '人才概览',
    path: '/resource-management/talent-overview',
  },
  {
    label: '人才总库',
    path: '/resource-management/talents',
    children: [
      {
        label: '笔译资源',
        path: '/resource-management/translators',
      },
      {
        label: '口译资源',
        path: '/resource-management/interpreters',
      },
      {
        label: '标注资源',
        path: '/resource-management/annotators',
      },
      {
        label: '全职资源',
        path: '/resource-management/recruitment-talents',
      },
    ],
  },
])
