import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../layout/index.vue'
import { TRANSLATION_PROJECT_ROLES, WORK_SCHEDULE_ROLES, canAccessRoute, isSuperAdmin, getStoredRoles } from '../utils/permission'

/** 仅笔译项目管理可访问的角色（客户专员、项目专员、项目经理） */
const translationRoles = TRANSLATION_PROJECT_ROLES
/** 工作安排可访问的角色（项目经理） */
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
        component: () => import('../views/Users.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('../views/Roles.vue'),
        meta: { title: '角色管理' }
      },
      {
        path: 'user-roles',
        name: 'UserRoles',
        component: () => import('../views/UserRoles.vue'),
        meta: { title: '用户角色关联' }
      },
      // 项目管理 - 嵌套路由
      {
        path: 'project-management',
        component: () => import('../views/ProjectManagement.vue'),
        redirect: '/project-management/translation',
        meta: { title: '项目管理', roles: translationRoles },
        children: [
          {
            path: 'translation',
            name: 'TranslationProjects',
            component: () => import('../views/TranslationProjects.vue'),
            meta: { title: '项目流程表', roles: translationRoles }
          },
          {
            path: 'translation/project-details',
            name: 'TranslationProjectDetails',
            component: () => import('../views/ProjectDetails.vue'),
            meta: { title: '项目详情', roles: translationRoles }
          },
          {
            path: 'translation/project-files',
            name: 'TranslationProjectFiles',
            component: () => import('../views/ProjectFiles.vue'),
            meta: { title: '项目文件', roles: translationRoles }
          },

          {
            path: 'interpretation',
            name: 'InterpretationProjects',
            component: () => import('../views/InterpretationProjects.vue'),
            meta: { title: '口译项目管理' }
          },
          {
            path: 'annotation',
            name: 'AnnotationProjects',
            component: () => import('../views/AnnotationProjects.vue'),
            meta: { title: '标注项目管理' }
          },
          {
            path: 'recruitment',
            name: 'RecruitmentProjects',
            component: () => import('../views/RecruitmentProjects.vue'),
            meta: { title: '招聘项目管理' }
          },
          {
            path: 'other',
            name: 'OtherProjects',
            component: () => import('../views/OtherProjects.vue'),
            meta: { title: '其他项目管理' }
          }
        ]
      },
      {
        path: 'work-schedule',
        name: 'WorkSchedule',
        component: () => import('../views/WorkSchedule.vue'),
        meta: { title: '工作安排', roles: workScheduleRoles }
      },
      // 资源管理 - 嵌套路由
      {
        path: 'resource-management',
        component: () => import('../views/ResourceManagement.vue'),
        redirect: '/resource-management/translators',
        meta: { title: '资源管理' },
        children: [
          {
            path: 'translators',
            name: 'Translators',
            component: () => import('../views/Translators.vue'),
            meta: { title: '译员信息' }
          },
          {
            path: 'annotators',
            name: 'Annotators',
            component: () => import('../views/Annotators.vue'),
            meta: { title: '标注员' }
          },
          {
            path: 'suppliers',
            name: 'Suppliers',
            component: () => import('../views/Suppliers.vue'),
            meta: { title: '供应商' }
          }
        ]
      },
      // 客户管理 - 嵌套路由
      {
        path: 'client-management',
        component: () => import('../views/ClientManagement.vue'),
        redirect: '/client-management/clients',
        meta: { title: '客户管理' },
        children: [
          {
            path: 'clients',
            name: 'Clients',
            component: () => import('../views/Clients.vue'),
            meta: { title: '客户信息' }
          },
          {
            path: 'subsidiary-clients',
            name: 'SubsidiaryClients',
            component: () => import('../views/SubsidiaryClients.vue'),
            meta: { title: '子公司客户信息' }
          },
          {
            path: 'client-contacts',
            name: 'ClientContacts',
            component: () => import('../views/ClientContacts.vue'),
            meta: { title: '客户联系人及回访' }
          },
          {
            path: 'consultations',
            name: 'Consultations',
            component: () => import('../views/Consultations.vue'),
            meta: { title: '咨询基本情况' }
          }
        ]
      },
      // 财务管理
      {
        path: 'finance',
        name: 'FinanceManagement',
        component: () => import('../views/FinanceManagement.vue'),
        meta: { title: '财务管理' }
      },
      // 营销管理
      {
        path: 'marketing',
        name: 'MarketingManagement',
        component: () => import('../views/MarketingManagement.vue'),
        meta: { title: '营销管理' }
      },
      // 人力管理 - 嵌套路由
      {
        path: 'hr-management',
        component: () => import('../views/HRManagement.vue'),
        redirect: '/hr-management/attendance',
        meta: { title: '人力管理' },
        children: [
          {
            path: 'attendance',
            name: 'Attendance',
            component: () => import('../views/Attendance.vue'),
            meta: { title: '考勤管理' }
          },
          {
            path: 'kpi',
            name: 'KPI',
            component: () => import('../views/KPI.vue'),
            meta: { title: 'KPI管理' }
          },
          {
            path: 'salary',
            name: 'Salary',
            component: () => import('../views/Salary.vue'),
            meta: { title: '薪酬管理' }
          },
          {
            path: 'onboarding',
            name: 'Onboarding',
            component: () => import('../views/Onboarding.vue'),
            meta: { title: '入职管理' }
          },
          {
            path: 'offboarding',
            name: 'Offboarding',
            component: () => import('../views/Offboarding.vue'),
            meta: { title: '离职管理' }
          }
        ]
      },
      // 内务管理 - 嵌套路由
      {
        path: 'administration-management',
        component: () => import('../views/AdministrationManagement.vue'),
        redirect: '/administration-management/office',
        meta: { title: '内务管理' },
        children: [
          {
            path: 'office',
            name: 'Office',
            component: () => import('../views/Office.vue'),
            meta: { title: '办公室管理' }
          },
          {
            path: 'office-equipment',
            name: 'OfficeEquipment',
            component: () => import('../views/OfficeEquipment.vue'),
            meta: { title: '办公室设备管理' }
          }
        ]
      },
      // 采购管理
      {
        path: 'procurement',
        name: 'ProcurementManagement',
        component: () => import('../views/ProcurementManagement.vue'),
        meta: { title: '采购管理' }
      },
      {
        path: 'technology-management',
        name: 'TechnologyManagement',
        component: () => import('../views/TechnologyManagement.vue'),
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
