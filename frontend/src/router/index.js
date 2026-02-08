import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/auth/Login.vue'
import Layout from '../layout/index.vue'
import { TRANSLATION_PROJECT_ROLES, WORK_SCHEDULE_ROLES, canAccessRoute, isSuperAdmin, getStoredRoles } from '../utils/permission'

/** 仅笔译项目管理可访问的角色（客户专员、项目专员、项目经理） */
const translationRoles = TRANSLATION_PROJECT_ROLES
/** 工作安排可访问的角色（超级管理员、项目经理） */
const workScheduleRoles = WORK_SCHEDULE_ROLES

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    component: Layout,
    redirect: '/users',
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
      // 项目管理 - 嵌套路由
      {
        path: 'project-management',
        component: () => import('../views/project/ProjectManagement.vue'),
        redirect: '/project-management/translation',
        meta: { title: '项目管理', roles: translationRoles },
        children: [
          {
            path: 'translation',
            name: 'TranslationProjects',
            component: () => import('../views/project/translation/TranslationProjects.vue'),
            meta: { title: '项目流程', roles: translationRoles }
          },
          {
            path: 'translation/project-details',
            name: 'TranslationProjectDetails',
            component: () => import('../views/project/translation/ProjectDetails.vue'),
            meta: { title: '项目详情', roles: translationRoles }
          },
          {
            path: 'translation/project-files',
            name: 'TranslationProjectFiles',
            component: () => import('../views/project/translation/ProjectFiles.vue'),
            meta: { title: '项目文件', roles: translationRoles }
          },

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
          }
        ]
      },
      {
        path: 'work-schedule',
        name: 'WorkSchedule',
        component: () => import('../views/schedule/WorkSchedule.vue'),
        meta: { title: '工作安排', roles: workScheduleRoles }
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
  if (to.path === '/login') {
    next()
    return
  }
  if (!token) {
    next('/login')
    return
  }
  // 已登录但未存储角色（如旧会话）：强制重新登录以获取角色
  if (getStoredRoles().length === 0) {
    next('/login')
    return
  }
  // 根路径按角色重定向到首页
  if (to.path === '/') {
    next(isSuperAdmin() ? '/users' : '/project-management/translation')
    return
  }
  // 检查当前用户是否有权访问目标路由
  if (!canAccessRoute(to)) {
    next(isSuperAdmin() ? '/users' : '/project-management/translation')
    return
  }
  next()
})

export default router
