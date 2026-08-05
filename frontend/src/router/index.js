import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/auth/Login.vue'
import Layout from '../layout/index.vue'
import { canAccessRoute, getDefaultRoute } from '../utils/permission'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/system/Users.vue'),
        meta: { title: '用户管理', permissions: ['system:users:read'] }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('../views/system/Roles.vue'),
        meta: { title: '角色管理', permissions: ['system:roles:read'] }
      },
      // 项目管理 - 翻译路由
      {
        path: 'translation',
        name: 'TranslationProjects',
        component: () => import('../views/project/translation/TranslationProjects.vue'),
        meta: { title: '项目流程', permissions: ['projects:read'] }
      },
      {
        path: 'translation-details',
        name: 'TranslationProjectDetails',
        component: () => import('../views/project/translation/ProjectDetails.vue'),
        meta: { title: '项目详情', permissions: ['projects:read'] }
      },
      {
        path: 'manuscript-arrangements',
        name: 'ManuscriptArrangements',
        component: () => import('../views/manuscript/ManuscriptArrangements.vue'),
        meta: { title: '稿件安排', permissions: ['projects:read'] }
      },
      {
        path: 'translation-files',
        redirect: '/translation-details'
      },
      {
        path: 'translation-sub-orders/:projectId',
        name: 'TranslationSubOrderManagement',
        component: () => import('../views/project/translation/SubOrderManagement.vue'),
        meta: { title: '子订单管理', permissions: ['projects:read'] }
      },
      // 项目管理 - 其他类型
      {
        path: 'interpretation',
        name: 'InterpretationProjects',
        component: () => import('../views/project/InterpretationProjects.vue'),
        meta: { title: '口译项目管理' }
      },
      {
        path: 'annotation',
        name: 'AnnotationProjects',
        component: () => import('../views/project/AnnotationProjects.vue'),
        meta: { title: '标注项目管理' }
      },
      {
        path: 'recruitment',
        name: 'RecruitmentProjects',
        component: () => import('../views/project/RecruitmentProjects.vue'),
        meta: { title: '招聘项目管理' }
      },
      {
        path: 'other',
        name: 'OtherProjects',
        component: () => import('../views/project/OtherProjects.vue'),
        meta: { title: '其他项目管理' }
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/Dashboard.vue'),
        meta: { title: '\u6570\u636E\u770B\u677F', roles: ['*'] }
      },
      {
        path: 'workbench',
        name: 'WorkDashboard',
        component: () => import('../views/schedule/WorkDashboard.vue'),
        meta: { title: '工作台', permissions: ['projects:read', 'tasks:read'] }
      },
      {
        path: 'admin/schedule',
        name: 'WorkScheduleAdmin',
        component: () => import('../views/schedule/WorkSchedule.vue'),
        meta: { title: '排班管理', permissions: ['schedule:read'] }
      },
      {
        path: 'work-schedule',
        name: 'WorkSchedule',
        component: () => import('../views/schedule/WorkSchedule.vue'),
        meta: { title: '排班管理', permissions: ['schedule:read'] }
      },
      // 资源管理 - 翻译路由
      {
        path: 'resource-management',
        component: () => import('../views/resource/ResourceManagement.vue'),
        redirect: '/resource-management/translators',
        meta: { title: '资源管理', permissions: ['translators:read'] },
        children: [
          {
            path: 'translators',
            name: 'Translators',
            component: () => import('../views/resource/Translators.vue'),
            meta: { title: '译者信息', permissions: ['translators:read'] }
          },
          {
            path: 'annotators',
            name: 'Annotators',
            component: () => import('../views/resource/Annotators.vue'),
            meta: { title: '标注员' }
          },
          {
            path: 'suppliers',
            name: 'Suppliers',
            component: () => import('../views/resource/Suppliers.vue'),
            meta: { title: '供应商' }
          }
        ]
      },
      // 客户管理 - 翻译路由
      {
        path: 'clients',
        name: 'Clients',
        component: () => import('../views/client/Clients.vue'),
        meta: { title: '客户信息', permissions: ['clients:read'] }
      },
      {
        path: 'subsidiary-clients',
        redirect: '/clients'
      },
      {
        path: 'client-contacts',
        name: 'ClientContacts',
        component: () => import('../views/client/ClientContacts.vue'),
        meta: { title: '客户联系人及回复', permissions: ['clients:read'] }
      },
      {
        path: 'consultations',
        name: 'Consultations',
        component: () => import('../views/client/Consultations.vue'),
        meta: { title: '新咨询管理', permissions: ['consultations:read'] }
      },
      // 财务管理
      {
        path: 'finance',
        name: 'FinanceManagement',
        component: () => import('../views/finance/FinanceManagement.vue'),
        meta: { title: '财务管理', permissions: ['finance:read'] }
      },
      {
        path: 'pending-modules',
        name: 'PendingModules',
        component: () => import('../views/PendingModules.vue'),
        meta: { title: '待完善模块', roles: ['*'] }
      },
      // 营销管理
      {
        path: 'marketing',
        name: 'MarketingManagement',
        component: () => import('../views/marketing/MarketingManagement.vue'),
        meta: { title: '营销管理' }
      },
      // 人力资源管理 - 翻译路由
      {
        path: 'hr-management',
        component: () => import('../views/hr/HRManagement.vue'),
        redirect: '/hr-management/attendance',
        meta: { title: '人力资源管理' },
        children: [
          {
            path: 'attendance',
            name: 'Attendance',
            component: () => import('../views/hr/Attendance.vue'),
            meta: { title: '考核管理' }
          },
          {
            path: 'kpi',
            name: 'KPI',
            component: () => import('../views/hr/KPI.vue'),
            meta: { title: 'KPI管理' }
          },
          {
            path: 'salary',
            name: 'Salary',
            component: () => import('../views/hr/Salary.vue'),
            meta: { title: '薪酬管理' }
          },
          {
            path: 'onboarding',
            name: 'Onboarding',
            component: () => import('../views/hr/Onboarding.vue'),
            meta: { title: '入职管理' }
          },
          {
            path: 'offboarding',
            name: 'Offboarding',
            component: () => import('../views/hr/Offboarding.vue'),
            meta: { title: '离职管理' }
          }
        ]
      },
      // 内部管理 - 翻译路由
      {
        path: 'administration-management',
        component: () => import('../views/administration/AdministrationManagement.vue'),
        redirect: '/administration-management/office',
        meta: { title: '内部管理' },
        children: [
          {
            path: 'office',
            name: 'Office',
            component: () => import('../views/administration/Office.vue'),
            meta: { title: '办公室管理' }
          },
          {
            path: 'office-equipment',
            name: 'OfficeEquipment',
            component: () => import('../views/administration/OfficeEquipment.vue'),
            meta: { title: '办公设备管理' }
          }
        ]
      },
      // 采购管理
      {
        path: 'procurement',
        name: 'ProcurementManagement',
        component: () => import('../views/procurement/ProcurementManagement.vue'),
        meta: { title: '采购管理' }
      },
      {
        path: 'technology-management',
        name: 'TechnologyManagement',
        component: () => import('../views/technology/TechnologyManagement.vue'),
        meta: { title: '技术管理' }
      },

    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：认证 + 角色权限
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.path === '/login') {
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  if (to.path === '/') {
    next(getDefaultRoute())
    return
  }

  if (!canAccessRoute(to)) {
    next(getDefaultRoute())
    return
  }

  next()
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} - ` : '翻译项目管理平台'
})

export default router




