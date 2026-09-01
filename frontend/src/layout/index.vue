<template>
  <el-container class="layout-container">
    <el-aside :width="sidebarWidth" class="sidebar" :class="{ 'sidebar--collapsed': isCollapse }">
      <div class="logo">
        <div class="logo-icon">
          <img src="/favicon.svg" alt="平台标识" class="logo-mark" />
        </div>
        <transition name="logo-text">
          <div v-show="!isCollapse" class="logo-text">
            <h2>项目管理</h2>
            <span class="logo-subtitle">综合业务项目管理平台</span>
          </div>
        </transition>
      </div>
      <el-menu
        ref="sidebarMenuRef"
        :default-active="activeMenu"
        :default-openeds="defaultOpeneds"
        :unique-opened="false"
        :show-timeout="isCollapse ? 86400000 : 300"
        :hide-timeout="isCollapse ? 86400000 : 300"
        router
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
      >
        <!-- 工作台 -->
        <el-menu-item v-if="showWorkbench" index="/workbench">
          <el-icon><ChatLineRound /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>

        <!-- 业务链路：从新咨询到项目执行 -->
        <li v-if="showBusinessGroup && !isCollapse" class="menu-group-label" role="presentation"><span>业务管理</span></li>
        <el-menu-item v-if="showConsultations" index="/consultations">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>新咨询管理</template>
        </el-menu-item>

        <el-menu-item index="/translation-details">
          <el-icon><Document /></el-icon>
          <template #title>笔译项目</template>
        </el-menu-item>
        <el-menu-item index="/interpretation-details">
          <el-icon><Headset /></el-icon>
          <template #title>口译项目</template>
        </el-menu-item>
        <el-menu-item index="/annotation-details">
          <el-icon><EditPen /></el-icon>
          <template #title>标注项目</template>
        </el-menu-item>
        <el-menu-item index="/recruitment-details">
          <el-icon><UserFilled /></el-icon>
          <template #title>招聘项目</template>
        </el-menu-item>
        <el-menu-item v-if="canViewManuscript" index="/manuscript-arrangements">
          <el-icon><Calendar /></el-icon>
          <template #title>稿件安排</template>
        </el-menu-item>

        <!-- 协作资源：客户、资源需求与人才资源池 -->
        <li v-if="showResourceGroup && !isCollapse" class="menu-group-label" role="presentation"><span>资源协作</span></li>
        <el-menu-item v-if="showClients" index="/clients">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>客户信息</template>
        </el-menu-item>
        <el-menu-item v-if="showResourceRequests" index="/resource-requests">
          <el-icon><Tickets /></el-icon>
          <template #title>资源需求管理</template>
        </el-menu-item>
        <el-menu-item v-if="showResourceManagement" index="/resource-management/talents">
          <el-icon><Avatar /></el-icon>
          <template #title>人才资源库</template>
        </el-menu-item>

        <!-- 账户、扩展能力和管理员入口统一归入平台设置 -->
        <li v-if="!isCollapse" class="menu-group-label" role="presentation"><span>平台设置</span></li>
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <template #title>个人中心</template>
        </el-menu-item>
        <el-menu-item v-if="showPendingModules" index="/pending-modules">
          <el-icon><QuestionFilled /></el-icon>
          <template #title>更多模块</template>
        </el-menu-item>

        <el-sub-menu v-if="showSystemMenu" :index="SYSTEM_MENU_INDEX" @click="handlePopupToggle(SYSTEM_MENU_INDEX, $event)">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item v-if="canViewUsers" index="/users">用户管理</el-menu-item>
          <el-menu-item v-if="canViewRoles" index="/roles">角色管理</el-menu-item>
          <el-menu-item v-if="canViewMailSettings" index="/mail-settings">项目邮件设置</el-menu-item>
        </el-sub-menu>
      </el-menu>
      <transition name="logo-text">
        <div v-show="!isCollapse" class="sidebar-version">{{ appVersion }} · 更新于 {{ appUpdatedAt }}</div>
      </transition>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-tooltip
            :content="isMobileViewport ? '窄屏模式下菜单保持收起' : (isCollapse ? '展开菜单' : '收起菜单')"
            placement="bottom"
          >
            <el-button
              class="collapse-btn"
              :icon="isCollapse ? Expand : Fold"
              :aria-label="isMobileViewport ? '窄屏模式下菜单保持收起' : (isCollapse ? '展开菜单' : '收起菜单')"
              :disabled="isMobileViewport"
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
                <el-dropdown-item command="profile">个人中心 / 发件邮箱</el-dropdown-item>
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
import { User, UserFilled, Setting, Document, Headset, EditPen, Calendar, Avatar, OfficeBuilding, ArrowDown, ChatLineRound, ChatDotRound, Tickets, QuestionFilled, Fold, Expand } from '@element-plus/icons-vue'
import {
  canViewClients,
  canViewConsultations,
  canViewManuscriptArrangements,
  hasPermission
} from '../utils/permission'
import NotificationBell from '../components/NotificationBell.vue'
import UiZoomControl from '../components/UiZoomControl.vue'
import { useUiZoom } from '../composables/useUiZoom'
import { logout } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const { openPanel, syncFromStorage } = useUiZoom()

const STORAGE_COLLAPSE_KEY = 'sidebar_collapse'
const SYSTEM_MENU_INDEX = 'system-management'
const appVersion = 'V1.3'
const appUpdatedAt = '2026-09-01 10:45'

/** 侧边栏是否折叠 */
const isCollapse = ref(false)
const isMobileViewport = ref(false)
const preferredCollapse = ref(false)
const sidebarMenuRef = ref()

/** 侧边栏宽度 */
const sidebarWidth = computed(() => (isCollapse.value ? '64px' : '240px'))

function toggleCollapse() {
  if (isMobileViewport.value) return
  isCollapse.value = !isCollapse.value
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

const canViewUsers = computed(() => hasPermission('system:users:read'))
const canViewRoles = computed(() => hasPermission('system:roles:read'))
const canViewMailSettings = computed(() => hasPermission('system:mail_settings:read'))
const showSystemMenu = computed(() => canViewUsers.value || canViewRoles.value || canViewMailSettings.value)

/** 是否显示「工作台」（所有员工） */
const showWorkbench = computed(() => hasPermission(['projects:read', 'tasks:read']))
/** 项目相关扩展模块仍按具体权限显示；四个基础业务表对所有登录用户开放。 */
const canViewProjects = computed(() => hasPermission('projects:read'))
const canViewManuscript = computed(() => canViewManuscriptArrangements())
const showClients = computed(() => canViewClients())
const showConsultations = computed(() => canViewConsultations())
const showResourceManagement = computed(() => hasPermission(['talents:read', 'translators:read']))
const showResourceRequests = computed(() => canViewProjects.value)
const showBusinessGroup = computed(() => true)
const showResourceGroup = computed(() => (
  showClients.value || showResourceManagement.value || showResourceRequests.value
))
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
  '/work-schedule',
  '/admin/schedule',
  '/dashboard',
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

const resolveActiveMenu = (path) => {
  if (pendingModulePaths.has(path)) return '/pending-modules'
  if (
    path === '/translation' ||
    path === '/translation-files' ||
    path.startsWith('/translation-details') ||
    path.startsWith('/translation-sub-orders/')
  ) return '/translation-details'
  if (path === '/interpretation' || path.startsWith('/interpretation-details')) {
    return '/interpretation-details'
  }
  if (path === '/annotation' || path.startsWith('/annotation-')) return '/annotation-details'
  if (path === '/recruitment' || path.startsWith('/recruitment-details')) return '/recruitment-details'
  if (path === '/resource-management' || path.startsWith('/resource-management/')) {
    return '/resource-management/talents'
  }
  return path
}

const resolveActiveGroup = (menuIndex) => {
  if (['/users', '/roles', '/mail-settings'].includes(menuIndex)) return SYSTEM_MENU_INDEX
  return ''
}

const activeMenu = ref(resolveActiveMenu(route.path))
const defaultOpeneds = computed(() => {
  const activeGroup = resolveActiveGroup(activeMenu.value)
  return activeGroup ? [activeGroup] : []
})

const openActiveGroup = () => {
  if (isCollapse.value) return
  const activeGroup = resolveActiveGroup(activeMenu.value)
  if (activeGroup) sidebarMenuRef.value?.open(activeGroup)
}

/** 折叠态下子菜单是弹层且不会因点击外部而关闭，路由跳转后需主动收起，避免滞留遮挡新页面。 */
const closePopupGroups = () => {
  sidebarMenuRef.value?.close(SYSTEM_MENU_INDEX)
}

/**
 * 折叠态（竖向弹层）下 Element Plus 忽略标题点击，弹层纯悬停驱动；
 * 配合超大的 show/hide-timeout 禁用悬停开合后，这里补上手动的点按切换：
 * 点图标开，再点关。以 li 的 is-opened 类为准，避免内部定时器与状态不同步。
 */
const handlePopupToggle = (index, event) => {
  if (!isCollapse.value) return
  const li = event.target?.closest?.('.el-sub-menu')
  if (!li || !event.target?.closest?.('.el-sub-menu__title')) return
  if (li.classList.contains('is-opened')) {
    sidebarMenuRef.value?.close(index)
  } else {
    sidebarMenuRef.value?.open(index)
  }
}

/** 监听路由变化，更新激活菜单 */
watch(
  () => route.path,
  (newPath) => {
    // 使用 nextTick 确保 DOM 更新后再设置激活菜单
    nextTick(() => {
      activeMenu.value = resolveActiveMenu(newPath)
      if (isCollapse.value) closePopupGroups()
      nextTick(openActiveGroup)
    })
  },
  { immediate: true }
)

watch(isCollapse, (collapsed) => {
  if (!collapsed) nextTick(openActiveGroup)
})

const currentPageTitle = computed(() => {
  return route.meta?.title || '首页'
})

const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'profile') {
    router.push('/profile')
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
    try {
      await logout()
    } catch {
      // 即使服务端暂时不可用，也要完成本地退出。
    }
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
  --sidebar-active-accent: #60a5fa;
  display: flex;
  flex-direction: column;
  background: var(--color-sidebar);
  color: #fff;
  box-shadow: 2px 0 8px rgba(15, 23, 42, 0.08);
  overflow: hidden;
  transition: width 220ms ease;
}

.sidebar--collapsed .logo {
  padding: 0 12px;
  justify-content: center;
}

.sidebar--collapsed .logo-icon {
  margin-right: 0;
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

.sidebar-menu::-webkit-scrollbar {
  width: 6px;
}

.sidebar-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.sidebar-menu::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.logo {
  flex: 0 0 64px;
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
  margin-right: 12px;
  flex-shrink: 0;
}

.logo-mark {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.24);
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

.sidebar-version {
  flex: none;
  padding: 10px 20px 14px;
  color: rgba(255, 255, 255, 0.36);
  font-size: 10px;
  line-height: 1.2;
  white-space: nowrap;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-menu {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  border: none;
  background: transparent;
  padding: 10px 0;
  overflow-x: hidden;
  overflow-y: auto;
  /* 子菜单展开导致内容超高时预留滚动条位置，避免菜单宽度瞬间变化。 */
  scrollbar-gutter: stable;
  /* 禁止浏览器在折叠动画中自动修正滚动位置，防止菜单上下跳动。 */
  overflow-anchor: none;
}

.sidebar-menu :deep(.el-menu-item) {
  position: relative;
  color: rgba(255, 255, 255, 0.72);
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 10px;
  transition: color 180ms ease, background-color 180ms ease, transform 180ms ease;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transform: translateX(2px);
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: rgba(96, 165, 250, 0.16);
  color: #fff;
  box-shadow: none;
}

.sidebar-menu :deep(.el-menu-item.is-active::before) {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sidebar-active-accent);
  box-shadow: 0 0 8px rgba(96, 165, 250, 0.7);
  content: '';
}

.sidebar-menu :deep(.el-menu-item .el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu) {
  margin: 2px 8px;
}

.sidebar-menu :deep(.el-sub-menu__title) {
  position: relative;
  color: rgba(255, 255, 255, 0.72);
  height: 44px;
  line-height: 44px;
  border-radius: 10px;
  transition: color 180ms ease, background-color 180ms ease, transform 180ms ease;
}

.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transform: translateX(2px);
}

.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #fff;
  background: rgba(255, 255, 255, 0.05);
}

.sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #fff;
}

.sidebar-menu :deep(.el-sub-menu .el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu .el-menu) {
  position: relative;
  background: rgba(0, 0, 0, 0.14);
  border-radius: 8px;
  margin-top: 4px;
  /*
   * Element Plus 会先清空内边距再按 scrollHeight 计算折叠高度。
   * 此处不设置纵向内边距，避免动画高度少算 8px 而裁掉最后一项。
   */
  padding: 0;
}

.sidebar-menu :deep(.el-sub-menu .el-menu)::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 14px;
  width: 1px;
  background: rgba(255, 255, 255, 0.12);
  content: '';
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  height: 40px;
  line-height: 40px;
  margin: 2px 6px;
  padding-left: 42px !important;
  font-size: 13px;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item.is-active::before) {
  top: 8px;
  bottom: 8px;
}

.sidebar-menu :deep(.el-menu-item:focus-visible),
.sidebar-menu :deep(.el-sub-menu__title:focus-visible) {
  outline: 2px solid rgba(147, 197, 253, 0.9);
  outline-offset: -2px;
}

.menu-group-label {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 20px 4px;
  color: rgba(255, 255, 255, 0.42);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  line-height: 18px;
  list-style: none;
  white-space: nowrap;
}

.menu-group-label::after {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.08);
  content: '';
}

/* 折叠状态下菜单项居中 */
.sidebar-menu.el-menu--collapse :deep(.el-menu-item),
.sidebar-menu.el-menu--collapse :deep(.el-sub-menu__title) {
  justify-content: center;
  margin-right: 8px;
  margin-left: 8px;
  padding: 0 !important;
  text-align: center;
}

.sidebar-menu.el-menu--collapse :deep(.el-menu-item:hover),
.sidebar-menu.el-menu--collapse :deep(.el-sub-menu__title:hover) {
  transform: none;
}

.sidebar-menu.el-menu--collapse :deep(.el-menu-item .el-icon),
.sidebar-menu.el-menu--collapse :deep(.el-sub-menu__title .el-icon) {
  margin-right: 0;
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
  padding: 12px 24px 24px;
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
  .sidebar-menu :deep(.el-menu-item span),
  .sidebar-menu :deep(.el-sub-menu__title span),
  .sidebar-menu :deep(.el-sub-menu__icon-arrow) {
    display: none;
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
    padding: 12px 16px 16px;
  }

  .username {
    display: none;
  }

  .user-info {
    padding: 6px;
  }
}
</style>
