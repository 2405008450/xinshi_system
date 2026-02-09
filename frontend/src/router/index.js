import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/auth/Login.vue'
import Layout from '../layout/index.vue'
import { TRANSLATION_PROJECT_ROLES, WORK_SCHEDULE_ROLES, SCHEDULE_VIEW_ROLES, SCHEDULE_ADMIN_ROLES, canAccessRoute, isSuperAdmin, getStoredRoles, hasRole } from '../utils/permission'

/** 仅笔译项目管理可访问的角色（客户专员、项目专员、项目经理） */
const translationRoles = TRANSLATION_PROJECT_ROLES
/** 工作台（我的任务）可访问角色 */
const workbenchRoles = WORK_SCHEDULE_ROLES
/** 排班管理查看权限（所有员工） */
const scheduleViewRoles = SCHEDULE_VIEW_ROLES
/** 排班管理编辑权限（仅项目经理与超级管理员） */
const scheduleAdminRoles = SCHEDULE_ADMIN_ROLES

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
        meta: { title: '用户管理' }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('../views/system/Roles.vue'),
        meta: { title: '角色管理' }
      },
      {
        path: 'user-roles',
        name: 'UserRoles',
        component: () => import('../views/system/UserRoles.vue'),
        meta: { title: '用户角色关联' }
      },
      // 项目管理 - 扁平路由（笔译）
      {
        path: 'translation',
        name: 'TranslationProjects',
        component: () => import('../views/project/translation/TranslationProjects.vue'),
        meta: { title: '项目流程', roles: translationRoles }
      },
      {
        path: 'translation-details',
        name: 'TranslationProjectDetails',
        component: () => import('../views/project/translation/ProjectDetails.vue'),
        meta: { title: '项目详情', roles: translationRoles }
      },
      {
        path: 'translation-files',
        name: 'TranslationProjectFiles',
        component: () => import('../views/project/translation/ProjectFiles.vue'),
        meta: { title: '项目文件', roles: translationRoles }
      },
      // 项目管理 - 其他类型（扁平）
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
        path: 'workbench',
        name: 'WorkDashboard',
        component: () => import('../views/schedule/WorkDashboard.vue'),
        meta: { title: '我的工作台', roles: workbenchRoles }
      },
      {
        path: 'admin/schedule',
        name: 'WorkScheduleAdmin',
        component: () => import('../views/schedule/WorkSchedule.vue'),
        meta: { title: '排班管理', roles: scheduleViewRoles }
      },
      {
        path: 'work-schedule',
        name: 'WorkSchedule',
        component: () => import('../views/schedule/WorkSchedule.vue'),
        meta: { title: '排班管理', roles: scheduleViewRoles }
      },
      // 资源管理 - 嵌套路由
      {
        path: 'resource-management',
        component: () => import('../views/resource/ResourceManagement.vue'),
        redirect: '/resource-management/translators',
        meta: { title: '资源管理' },
        children: [
          {
            path: 'translators',
            name: 'Translators',
            component: () => import('../views/resource/Translators.vue'),
            meta: { title: '译员信息' }
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
      // 客户管理 - 嵌套路由
      {
        path: 'client-management',
        component: () => import('../views/client/ClientManagement.vue'),
        redirect: '/client-management/clients',
        meta: { title: '客户管理' },
        children: [
          {
            path: 'clients',
            name: 'Clients',
            component: () => import('../views/client/Clients.vue'),
            meta: { title: '客户信息' }
          },
          {
            path: 'subsidiary-clients',
            name: 'SubsidiaryClients',
            component: () => import('../views/client/SubsidiaryClients.vue'),
            meta: { title: '子公司客户信息' }
          },
          {
            path: 'client-contacts',
            name: 'ClientContacts',
            component: () => import('../views/client/ClientContacts.vue'),
            meta: { title: '客户联系人及回访' }
          },
          {
            path: 'consultations',
            name: 'Consultations',
            component: () => import('../views/client/Consultations.vue'),
            meta: { title: '咨询基本情况' }
          }
        ]
      },
      // 财务管理
      {
        path: 'finance',
        name: 'FinanceManagement',
        component: () => import('../views/finance/FinanceManagement.vue'),
        meta: { title: '财务管理' }
      },
      // 营销管理
      {
        path: 'marketing',
        name: 'MarketingManagement',
        component: () => import('../views/marketing/MarketingManagement.vue'),
        meta: { title: '营销管理' }
      },
      // 人力管理 - 嵌套路由
      {
        path: 'hr-management',
        component: () => import('../views/hr/HRManagement.vue'),
        redirect: '/hr-management/attendance',
        meta: { title: '人力管理' },
        children: [
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
      // 内务管理 - 嵌套路由
      {
        path: 'administration-management',
        component: () => import('../views/administration/AdministrationManagement.vue'),
        redirect: '/administration-management/office',
        meta: { title: '内务管理' },
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
            meta: { title: '办公室设备管理' }
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
  
  // 1. 登录页面：无需权限检查，直接放行
  if (to.path === '/login') {
    next()
    return
  }
  
  // 2. 未登录：重定向到登录页
  if (!token) {
    next('/login')
    return
  }
  
  // 3. 已登录但未存储角色：强制重新登录以获取角色
  const userRoles = getStoredRoles()
  if (userRoles.length === 0) {
    next('/login')
    return
  }
  
  // 4. 根路径：按角色重定向到首页
  if (to.path === '/') {
    const homePath = isSuperAdmin() ? '/users' : '/translation'
    next(homePath)
    return
  }
  
  // 5. 权限检查：检查当前用户是否有权访问目标路由
  if (!canAccessRoute(to)) {
    // 特殊处理：无排班管理权限但有工作台权限时，重定向到工作台
    const isScheduleAdminRoute = to.path === '/work-schedule' || to.path === '/admin/schedule'
    if (isScheduleAdminRoute && hasRole(WORK_SCHEDULE_ROLES)) {
      next('/workbench')
      return
    }
    // 其他无权限访问：重定向到对应角色的首页
    const homePath = isSuperAdmin() ? '/users' : '/translation'
    next(homePath)
    return
  }
  
  // 6. 通过所有检查：允许访问
  next()
})

// 每次导航后同步浏览器标签标题，避免客户端跳转后 tab 不更新
router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} - 信实` : '信实翻译项目管理平台'
})

export default router
