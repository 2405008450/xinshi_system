<template>
  <el-container class="layout-container">
    <el-aside :width="sidebarWidth" class="sidebar" :class="{ 'sidebar--collapsed': isCollapse }">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="28"><OfficeBuilding /></el-icon>
        </div>
        <transition name="logo-text">
          <div v-show="!isCollapse" class="logo-text">
            <h2>翻译</h2>
            <span class="logo-subtitle">翻译项目管理平台</span>
          </div>
        </transition>
      </div>
      <div class="sidebar-extra" :class="{ 'sidebar-extra--collapsed': isCollapse }">
      </div>
      <el-menu
        :default-active="activeMenu"
        :unique-opened="false"
        router
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
      >
        <!-- 仅超级管理员可见：用户/角色/用户角色关联 -->
        <template v-if="showSystemMenu">
          <el-menu-item v-if="canViewUsers" index="/users">
            <el-icon><User /></el-icon>
            <template #title>用户管理</template>
          </el-menu-item>
          <el-menu-item v-if="canViewRoles" index="/roles">
            <el-icon><Key /></el-icon>
            <template #title>角色管理</template>
          </el-menu-item>
          <el-menu-item v-if="canViewMailSettings" index="/mail-settings">
            <el-icon><Setting /></el-icon>
            <template #title>项目邮件设置</template>
          </el-menu-item>
          <el-divider class="menu-divider" />
        </template>
        <!-- 工作台 -->
        <el-menu-item v-if="showWorkbench" index="/workbench">
          <el-icon><ChatLineRound /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>
        <el-menu-item v-if="showConsultations" index="/consultations">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>新咨询管理</template>
        </el-menu-item>
        
        <!-- 项目管理：扁平菜单 -->
        <el-menu-item v-if="showTranslationMenu" index="/translation-details">
          <el-icon><Document /></el-icon>
          <template #title>笔译项目详情</template>
        </el-menu-item>
        <el-menu-item v-if="showTranslationMenu" index="/interpretation-details">
          <el-icon><Document /></el-icon>
          <template #title>口译项目详情</template>
        </el-menu-item>
        <el-menu-item v-if="showTranslationMenu" index="/annotation-details">
          <el-icon><Document /></el-icon>
          <template #title>标注项目详情</template>
        </el-menu-item>
        <el-menu-item v-if="showTranslationMenu" index="/resource-requests">
          <el-icon><UserFilled /></el-icon>
          <template #title>资源需求管理</template>
        </el-menu-item>
        <el-menu-item v-if="showTranslationMenu" index="/recruitment-details">
          <el-icon><Document /></el-icon>
          <template #title>招聘项目详情</template>
        </el-menu-item>
        <el-menu-item v-if="showTranslationMenu" index="/manuscript-arrangements">
          <el-icon><Tickets /></el-icon>
          <template #title>稿件安排</template>
        </el-menu-item>
        <!-- 排班管理：所有员工可查看（编辑权限在页面内控制） -->
        <el-menu-item v-if="showSchedule" index="/work-schedule">
          <el-icon><Calendar /></el-icon>
          <template #title>排班管理</template>
        </el-menu-item>
        <!-- 译员信息：所有员工可查看 -->
        <el-menu-item v-if="showResourceManagement" index="/resource-management/talents">
          <el-icon><Avatar /></el-icon>
          <template #title>人才资源库</template>
        </el-menu-item>
        <!-- 客户管理：所有员工可查看 -->
        <el-menu-item v-if="showClients" index="/clients">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>客户信息</template>
        </el-menu-item>
        <template v-if="showPendingModules">
          <el-divider class="menu-divider" />
          <el-menu-item index="/pending-modules">
            <el-icon><QuestionFilled /></el-icon>
            <template #title>待完善模块</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-tooltip :content="isCollapse ? '展开菜单' : '收起菜单'" placement="bottom">
            <el-button
              class="collapse-btn"
              :icon="isCollapse ? Expand : Fold"
              circle
              text
              @click="toggleCollapse"
            />
          </el-tooltip>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <UiZoomControl />
          <NotificationBell />
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="User" />
              <span class="username">{{ displayName }}</span>
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view v-slot="{ Component, route }">
          <transition name="fade-transform" mode="out-in">
            <component v-if="Component" :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { User, UserFilled, Key, Setting, Document, Tickets, Avatar, OfficeBuilding, ArrowDown, ChatLineRound, Calendar, QuestionFilled, Fold, Expand } from '@element-plus/icons-vue'
import { isSuperAdmin, hasPermission } from '../utils/permission'
import NotificationBell from '../components/NotificationBell.vue'
import UiZoomControl from '../components/UiZoomControl.vue'
import { useUiZoom } from '../composables/useUiZoom'

const route = useRoute()
const router = useRouter()
const { openPanel, syncFromStorage } = useUiZoom()

const STORAGE_COLLAPSE_KEY = 'sidebar_collapse'

/** 侧边栏是否折叠 */
const isCollapse = ref(false)
const isMobileViewport = ref(false)
const preferredCollapse = ref(false)

/** 侧边栏宽度 */
const sidebarWidth = computed(() => (isCollapse.value ? '64px' : '240px'))

function toggleCollapse() {
  isCollapse.value = !isCollapse.value
  if (isMobileViewport.value) return
  preferredCollapse.value = isCollapse.value
  try {
    localStorage.setItem(STORAGE_COLLAPSE_KEY, isCollapse.value ? '1' : '0')
  } catch {}
}

function syncResponsiveSidebar() {
  isMobileViewport.value = window.innerWidth <= 768
  isCollapse.value = isMobileViewport.value ? true : preferredCollapse.value
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_COLLAPSE_KEY)
    if (saved !== null) preferredCollapse.value = saved === '1'
  } catch {}
  syncFromStorage()
  syncResponsiveSidebar()
  window.addEventListener('resize', syncResponsiveSidebar)
})

onBeforeUnmount(() => window.removeEventListener('resize', syncResponsiveSidebar))

/** 是否显示完整菜单（超级管理员） */
const showFullMenu = computed(() => isSuperAdmin())
const canViewUsers = computed(() => hasPermission('system:users:read'))
const canViewRoles = computed(() => hasPermission('system:roles:read'))
const canViewMailSettings = computed(() => hasPermission('system:mail_settings:read'))
const showSystemMenu = computed(() => canViewUsers.value || canViewRoles.value || canViewMailSettings.value)

/** 是否显示「工作台」（所有员工） */
const showWorkbench = computed(() => hasPermission(['projects:read', 'tasks:read']))
/** 是否显示「排班管理」（所有员工可以查看） */
const showSchedule = computed(() => hasPermission('schedule:read'))

/** 是否显示笔译相关菜单（所有员工都可以进入工作台，内部操作权限后置判断） */
const showTranslationMenu = computed(() => hasPermission('projects:read'))

/** 是否显示「客户管理」（所有员工） */
const showClients = computed(() => hasPermission('clients:read'))
const showConsultations = computed(() => hasPermission('consultations:read'))
/** 是否显示「客户联系人及回复」（仅超级管理员） */
const showClientContacts = computed(() => hasPermission('clients:read'))
/** 是否显示「资源管理」（所有员工） */
const showResourceManagement = computed(() => hasPermission(['talents:read', 'translators:read']))
const showFinance = computed(() => hasPermission('finance:read'))
// 数据看板已移入待完善模块，因此所有登录用户都保留该入口。
const showPendingModules = computed(() => true)

/** 当前用户名（优先显示真实姓名，其次用户名，最后回退到用户） */
const displayName = computed(() => {
  const fullName = localStorage.getItem('user_full_name')
  if (fullName) return fullName
  const userName = localStorage.getItem('user_name')
  if (userName) return userName
  return '用户'
})

/** 当前激活的菜单项 */
const pendingModulePaths = new Set([
  '/dashboard',
  '/translation',
  '/other',
  '/client-contacts',
  '/finance',
  '/technology-management',
  '/marketing',
  '/hr-management/attendance',
  '/hr-management/kpi',
  '/hr-management/salary',
  '/hr-management/onboarding',
  '/hr-management/offboarding',
  '/administration-management/office',
  '/administration-management/office-equipment',
  '/procurement',
])
const resolveActiveMenu = (path) => pendingModulePaths.has(path) ? '/pending-modules' : path
const activeMenu = ref(resolveActiveMenu(route.path))

/** 监听路由变化，更新激活菜单 */
watch(
  () => route.path,
  (newPath) => {
    // 使用 nextTick 确保 DOM 更新后再设置激活菜单
    nextTick(() => {
      activeMenu.value = resolveActiveMenu(newPath)
    })
  },
  { immediate: true }
)

const currentPageTitle = computed(() => {
  return route.meta?.title || '首页'
})

const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'profile') {
    // 跳转到个人中心
    console.log('个人中心')
  } else if (command === 'settings') {
    setTimeout(() => {
      openPanel()
    }, 50)
  }
}

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    localStorage.removeItem('token')
    localStorage.removeItem('user_roles')
    localStorage.removeItem('user_permissions')
    localStorage.removeItem('user_name')
    localStorage.removeItem('user_id')
    localStorage.removeItem('user_full_name')
    router.push('/login')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.layout-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.sidebar {
  background: linear-gradient(180deg, var(--color-sidebar) 0%, var(--color-sidebar-deep) 100%);
  color: #fff;
  box-shadow: 2px 0 8px rgba(15, 23, 42, 0.08);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 220ms ease;
}

.sidebar--collapsed .logo {
  padding: 0 12px;
  justify-content: center;
}

.sidebar--collapsed .logo-icon {
  margin-right: 0;
}

.sidebar-extra {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px 12px;
  min-height: 40px;
}

.sidebar-extra--collapsed {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar-extra-label {
  white-space: nowrap;
}

.logo-text-enter-active,
.logo-text-leave-active {
  transition: opacity 0.2s ease;
}

.logo-text-enter-from,
.logo-text-leave-to {
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.sidebar::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.sidebar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  background: var(--color-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-md);
  margin-right: 12px;
  flex-shrink: 0;
}

.logo-text {
  flex: 1;
  min-width: 0;
}

.logo h2 {
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logo-subtitle {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-menu {
  border: none;
  background: transparent;
  padding: 10px 0;
}

.sidebar-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.72);
  height: 46px;
  line-height: 46px;
  margin: 4px 12px;
  border-radius: 8px;
  transition: color 180ms ease, background-color 180ms ease;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
}

.sidebar-menu :deep(.el-menu-item .el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu) {
  margin: 4px 12px;
}

.sidebar-menu :deep(.el-sub-menu__title) {
  color: rgba(255, 255, 255, 0.72);
  height: 46px;
  line-height: 46px;
  border-radius: 8px;
  transition: color 180ms ease, background-color 180ms ease;
}

.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #fff;
}

.sidebar-menu :deep(.el-sub-menu .el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  margin-top: 4px;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  margin: 2px 8px;
  padding-left: 40px !important;
}

/* 折叠状态下菜单项居中 */
.sidebar-menu.el-menu--collapse :deep(.el-menu-item),
.sidebar-menu.el-menu--collapse :deep(.el-sub-menu__title) {
  padding: 0 20px;
  text-align: center;
}

.sidebar-menu.el-menu--collapse :deep(.el-sub-menu__title .el-icon) {
  margin-right: 0;
}

.menu-divider {
  margin: 12px 20px;
  border-color: rgba(255, 255, 255, 0.1);
}

.header {
  height: 64px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 10;
}

.header-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  font-size: 18px;
  color: var(--color-text-secondary);
}

.collapse-btn:hover {
  color: var(--color-primary-hover);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
 
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 8px;
  transition: background-color 180ms ease;
}

.user-info:hover {
  background: var(--color-surface-muted);
}

.username {
  font-size: 14px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.user-info :deep(.el-avatar) {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.main-content {
  background: var(--color-page-bg);
  padding: 24px;
  overflow-y: auto;
}

/* 加载状态 */
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: var(--color-primary);
}

/* 页面切换动画 */
.fade-transform-leave-active,
.fade-transform-enter-active {
  transition: opacity 220ms ease, transform 220ms ease;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    width: 64px !important;
    flex: 0 0 64px;
  }

  .sidebar .logo {
    padding: 0 12px;
    justify-content: center;
  }

  .sidebar .logo-icon {
    margin-right: 0;
  }

  .sidebar .logo-text,
  .sidebar-extra-label,
  .sidebar-menu :deep(.el-menu-item span),
  .sidebar-menu :deep(.el-sub-menu__title span),
  .sidebar-menu :deep(.el-sub-menu__icon-arrow) {
    display: none;
  }

  .sidebar-extra {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
  }

  .sidebar-menu :deep(.el-menu-item),
  .sidebar-menu :deep(.el-sub-menu__title) {
    justify-content: center;
    margin-left: 8px;
    margin-right: 8px;
    padding: 0 !important;
  }

  .sidebar-menu :deep(.el-menu-item .el-icon),
  .sidebar-menu :deep(.el-sub-menu__title .el-icon) {
    margin-right: 0;
  }
  
  .logo h2 {
    font-size: 16px;
  }
  
  .header {
    padding: 0 16px;
  }
  
  .main-content {
    padding: 16px;
  }

  .username {
    display: none;
  }

  .user-info {
    padding: 6px;
  }
}
</style>
