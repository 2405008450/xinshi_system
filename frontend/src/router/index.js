import { createRouter, createWebHistory } from 'vue-router'
import {
  canAccessRoute,
  hasPermission,
  getDefaultRoute,
  MANUSCRIPT_VIEW_ROLES,
  setStoredAccess, setStoredHrAccess
} from '../utils/permission'
import { getCurrentSession } from '../api/auth'
import { refreshIssueAccess } from '@/composables/useResourceIssues'
import { refreshTechnicalDevelopmentAccess } from '@/composables/useTechnicalDevelopmentAccess'
import { resourceRequestsLocation, resolveDevelopmentSection } from '@/utils/resourceDevelopmentNavigation'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/auth/Login.vue')
  },
  {
    path: '/',
    component: () => import('../layout/index.vue'),
    children: [
      {
        path: 'company-management',
        name: 'CompanyManagement',
        component: () => import('../views/system/CompanyManagement.vue'),
        meta: { title: '公司管理', roles: ['*'] },
        children: [
          { path: 'development-feedback', name: 'DevelopmentFeedback', component: () => import('../views/technology/DevelopmentFeedback.vue'), meta: { title: '开发反馈', roles: ['*'] } }
        ]
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('../views/profile/Profile.vue'),
        meta: { title: '个人中心', roles: ['*'] }
      },
      {
        path: 'users',
        name: 'Users',
        redirect: to => ({path:'/hr-management/organization',query:to.query,hash:to.hash}),
        meta: { title: '组织架构', organizationManagement: true }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('../views/system/Roles.vue'),
        meta: { title: '角色管理', permissions: ['system:roles:read'] }
      },
      // 项目管理 - 翻译路由
      {
        path: 'departments',
        name: 'Departments',
        redirect: to => ({path:'/hr-management/organization',query:to.query,hash:to.hash}),
        meta: { title: '组织架构', organizationManagement: true }
      },
      {
        path: 'translation',
        name: 'TranslationProjects',
        component: () => import('../views/project/translation/TranslationProjects.vue'),
        meta: { title: '项目流程', permissions: ['projects:read'] }
      },
      {
        path: 'translation-details',
        name: 'TranslationProjectDetails',
        component: () => import('../views/project/ProjectWorkspace.vue'),
        props: { module: 'translation' },
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
        path: 'project-operation-audits',
        name: 'ProjectOperationAudits',
        component: () => import('../views/system/ProjectOperationAudits.vue'),
        meta: { title: '项目操作审计', permissions: ['system:audit:read'] }
      },
      {
        path: 'interpretation-details',
        name: 'InterpretationProjectDetails',
        component: () => import('../views/project/ProjectWorkspace.vue'),
        props: { module: 'interpretation' },
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
          chatContext: 'annotation',
          title: '标注项目管理',
          permissions: ['projects:read', 'annotation_accounts:read', 'annotation_accounts:write']
        }
      },
      {
        path: 'annotation-child-orders',
        name: 'AnnotationChildOrders',
        component: () => import('../views/project/AnnotationChildOrders.vue'),
        meta: { title: '标注子订单管理', permissions: ['projects:read'], chatContext: 'annotation' }
      },
      {
        path: 'annotation-arrangements',
        redirect: to => ({
          name: 'AnnotationProjectDetails',
          query: { ...to.query, section: 'arrangements' }
        })
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
        redirect: resourceRequestsLocation,
      },
      {
        path: 'recruitment',
        redirect: '/recruitment-details'
      },
      {
        path: 'recruitment-details',
        name: 'RecruitmentProjectDetails',
        component: () => import('../views/project/ProjectWorkspace.vue'),
        props: { module: 'recruitment' },
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
        redirect: '/resource-management/talent-overview',
        meta: {
          chatContext: 'resource',
          title: '资源管理',
          roles: ['*']
        },
        children: [
          {
            path: 'talent-overview',
            name: 'TalentOverview',
            component: () => import('../views/resource/TalentOverview.vue'),
            meta: { title: '人才概览', roles: ['*'] }
          },
          {
            path: 'development-notices',
            name: 'DevelopmentNotices',
            component: () => import('../views/resource/DevelopmentNotices.vue'),
            meta: { title: '开拓须知', roles: ['*'] }
          },
          {
            path: 'referral-development',
            name: 'ReferralDevelopment',
            component: () => import('../views/resource/ReferralDevelopment.vue'),
            meta: { title: '推荐拓展', roles: ['*'], permissions: ['talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'] }
          },
          {
            path: 'resource-development',
            name: 'ResourceDevelopment',
            component: () => import('../views/resource/ResourceDevelopment.vue'),
            meta: { title: '资源开拓', roles: ['*'], permissions: ['projects:read', 'talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'] }
          },
          {
            path: 'resource-channels',
            name: 'ResourceChannels',
            component: () => import('../views/resource/ResourceChannels.vue'),
            meta: { title: '渠道管理', roles: ['*'], permissions: ['talents:read', 'talents:write', 'translators:read', 'translators:write', 'resource_development:delegate'] }
          },
          {
            path: 'talents',
            name: 'Talents',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '人才总库', roles: ['*'] }
          },
          {
            path: 'talent-duplicate-review',
            name: 'TalentDuplicateReview',
            component: () => import('../views/resource/TalentDuplicateReview.vue'),
            meta: { title: '同名核重', roles: ['*'] }
          },
          {
            path: 'translators',
            name: 'Translators',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '笔译资源', capabilityType: 'written_translation', roles: ['*'] }
          },
          {
            path: 'interpreters',
            name: 'Interpreters',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '口译资源', capabilityType: 'interpretation', roles: ['*'] }
          },
          {
            path: 'annotators',
            name: 'Annotators',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '标注员', capabilityType: 'annotation', roles: ['*'] }
          },
          {
            path: 'recruitment-talents',
            name: 'RecruitmentTalents',
            component: () => import('../views/resource/TalentPool.vue'),
            meta: { title: '招聘人才库', talentApiScope: 'recruitment', roles: ['*'] }
          },
          {
            path: 'suppliers',
            name: 'Suppliers',
            component: () => import('../views/resource/Suppliers.vue'),
            meta: { title: '供应商' }
          },
          {
            path: 'teams',
            name: 'TeamResources',
            component: () => import('../views/resource/TeamResources.vue'),
            meta: { title: '团队资源', roles: ['*'] }
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
        redirect: '/hr-management/organization',
        meta: { title: '人事管理', hrManagement: true },
        children: [
          {path:'organization',name:'HROrganization',component:()=>import('../views/system/Organization.vue'),meta:{title:'组织架构',organizationManagement:true}},
          {path:'shifts',name:'MonthlyShiftManagement',component:()=>import('../views/hr/MonthlyShiftManagement.vue'),meta:{title:'排班管理',hrManagement:true}},
          {
            path: 'attendance',
            name: 'Attendance',
            component: () => import('../views/hr/Attendance.vue'),
            meta: { title: '考勤管理' }
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
            path: 'recruitment',
            name: 'HRRecruitment',
            component: () => import('../views/hr/RecruitmentManagement.vue'),
            meta: { title: '招聘管理', hrManagement: true }
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
        redirect: '/technology-management/development',
        meta: { title: '技术管理', technicalDevelopment: true },
        children: [
          {
            path: 'development',
            name: 'TechnicalDevelopment',
            component: () => import('../views/technology/TechnicalDevelopment.vue'),
            meta: { title: '技术开发', technicalDevelopment: true }
          }
        ]
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
    setStoredHrAccess(session.can_manage_hr)
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

  if (to.name === 'ResourceDevelopment') {
    let access
    try {
      access = await refreshIssueAccess(true)
    } catch {
      // 开拓权限接口不可用时，需求入口仍可按自身读取权限访问。
      access = { can_resource: false, can_enter: false }
    }
    const section = resolveDevelopmentSection(to.query.section, {
      canRequests: hasPermission('projects:read'),
      canResource: access.can_resource,
      canIssues: access.can_enter,
    })
    if (!section) { next(getDefaultRoute()); return }
    if (section !== to.query.section && !(section === 'logs' && !to.query.section)) {
      next({ path: to.path, query: { ...to.query, section }, hash: to.hash, replace: true }); return
    }
    next(); return
  }

  if (to.meta?.technicalDevelopment) {
    try { await refreshTechnicalDevelopmentAccess() }
    catch { next(getDefaultRoute()); return }
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
