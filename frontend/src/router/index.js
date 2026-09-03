import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/auth/Login.vue'
import Layout from '../layout/index.vue'
import {
  canAccessRoute,
  getDefaultRoute,
  MANUSCRIPT_VIEW_ROLES,
  setStoredAccess
} from '../utils/permission'
import { getCurrentSession } from '../api/auth'

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
        path: 'profile',
        name: 'Profile',
        component: () => import('../views/profile/Profile.vue'),
        meta: { title: '个人中心', roles: ['*'] }
      },
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
        meta: { title: '笔译项目管理', permissions: ['projects:read'] }
      },
      {
        path: 'manuscript-arrangements',
        name: 'ManuscriptArrangements',
        component: () => import('../views/manuscript/ManuscriptArrangements.vue'),
        meta: {
          title: '稿件安排',
          permissions: ['projects:read'],
          roles: MANUSCRIPT_VIEW_ROLES
        }
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
        redirect: '/interpretation-details'
      },
      {
        path: 'mail-settings',
        name: 'MailSettings',
        component: () => import('../views/system/MailSettings.vue'),
        meta: { title: '项目邮件设置', permissions: ['system:mail_settings:read'] }
      },
      {
        path: 'interpretation-details',
        name: 'InterpretationProjectDetails',
        component: () => import('../views/project/interpretation/InterpretationProjectDetails.vue'),
        meta: { title: '口译项目管理', permissions: ['projects:read'] }
      },
      {
        path: 'annotation',
        redirect: '/annotation-details'
      },
      {
        path: 'annotation-details',
        name: 'AnnotationProjectDetails',
        component: () => import('../views/project/AnnotationWorkspace.vue'),
        meta: {
          title: '标注项目管理',
          permissions: ['projects:read', 'annotation_accounts:read', 'annotation_accounts:write']
        }
      },
      {
        path: 'annotation-accounts',
        name: 'AnnotationAccounts',
        redirect: to => ({
          name: 'AnnotationProjectDetails',
          query: { ...to.query, section: 'accounts' }
        })
      },
      {
        path: 'annotation-trials',
        name: 'AnnotationTrials',
        redirect: { path: '/annotation-details', query: { section: 'trials' } }
      },
      {
        path: 'resource-requests',
        name: 'ResourceRequests',
        component: () => import('../views/resource/ResourceRequests.vue'),
        meta: { title: '资源需求管理', permissions: ['projects:read'] }
      },
      {
        path: 'recruitment',
        redirect: '/recruitment-details'
      },
      {
        path: 'recruitment-details',
        name: 'RecruitmentProjectDetails',
        component: () => import('../views/project/RecruitmentProjects.vue'),
        meta: { title: '招聘项目管理', permissions: ['projects:read'] }
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
        redirect: '/resource-management/talents',
        meta: {
          title: '资源管理',
          permissions: ['talents:read', 'translators:read', 'recruitment_talents:read']
        },
        children: [
          {
            path: 'talents',
            name: 'Talents',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '人才总库', permissions: ['talents:read', 'translators:read'] }
          },
          {
            path: 'translators',
            name: 'Translators',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '笔译资源', capabilityType: 'written_translation', permissions: ['talents:read', 'translators:read'] }
          },
          {
            path: 'interpreters',
            name: 'Interpreters',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '口译资源', capabilityType: 'interpretation', permissions: ['talents:read', 'translators:read'] }
          },
          {
            path: 'annotators',
            name: 'Annotators',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '标注员', capabilityType: 'annotation', permissions: ['talents:read', 'translators:read'] }
          },
          {
            path: 'recruitment-talents',
            name: 'RecruitmentTalents',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '招聘人才库', talentApiScope: 'recruitment', permissions: ['recruitment_talents:read'] }
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

let sessionPermissionSyncAt = 0

const syncSessionPermissions = async (force = false) => {
  if (!force && Date.now() - sessionPermissionSyncAt < 60_000) return true
  try {
    const session = await getCurrentSession()
    localStorage.setItem('user_id', session.user_id || '')
    localStorage.setItem('user_name', session.username || '')
    localStorage.setItem('user_full_name', session.full_name || session.username || '')
    setStoredAccess(session.roles, session.permissions)
    sessionPermissionSyncAt = Date.now()
    return true
  } catch {
    return false
  }
}

// 路由守卫：认证 + 角色权限
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.path === '/login') {
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  if (!await syncSessionPermissions()) {
    next('/login')
    return
  }

  if (to.path === '/') {
    next(getDefaultRoute())
    return
  }

  if (!canAccessRoute(to)) {
    // 权限可能刚被管理员调整，拒绝导航前强制再同步一次。
    if (!await syncSessionPermissions(true) || !canAccessRoute(to)) {
      next(getDefaultRoute())
      return
    }
  }

  next()
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} - 综合业务项目管理平台` : '综合业务项目管理平台'
})

export default router




