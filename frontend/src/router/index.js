import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../layout/index.vue'

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
      {
        path: 'project-files',
        name: 'ProjectFiles',
        component: () => import('../views/ProjectFiles.vue'),
        meta: { title: '项目文件管理' }
      },
      {
        path: 'project-details',
        name: 'ProjectDetails',
        component: () => import('../views/ProjectDetails.vue'),
        meta: { title: '项目详情' }
      },
      // 项目管理 - 嵌套路由
      {
        path: 'project-management',
        component: () => import('../views/ProjectManagement.vue'),
        redirect: '/project-management/translation',
        meta: { title: '项目管理' },
        children: [
          {
            path: 'translation',
            name: 'TranslationProjects',
            component: () => import('../views/TranslationProjects.vue'),
            meta: { title: '笔译项目管理' }
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
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path === '/login') {
    next()
  } else if (!token) {
    next('/login')
  } else {
    next()
  }
})

export default router
