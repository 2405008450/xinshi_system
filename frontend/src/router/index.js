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
        path: 'projects',
        name: 'Projects',
        component: () => import('../views/Projects.vue'),
        meta: { title: '项目管理' }
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
      {
        path: 'translators',
        name: 'Translators',
        component: () => import('../views/Translators.vue'),
        meta: { title: '译员信息' }
      },
      {
        path: 'clients',
        name: 'Clients',
        component: () => import('../views/Clients.vue'),
        meta: { title: '客户信息' }
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
