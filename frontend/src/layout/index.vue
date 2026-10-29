<template>
  <el-container class="layout-container">
    <div v-if="isMobileViewport && mobileNavOpen" class="sidebar-mask" aria-hidden="true" @click="mobileNavOpen = false" />
    <el-aside :width="sidebarWidth" class="sidebar" :class="{ 'sidebar--collapsed': isCollapse, 'sidebar--drawer': isMobileViewport, 'is-open': mobileNavOpen }">
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
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
      >
        <!-- 工作台 -->
        <SidebarNavigationItem v-if="showWorkbench" index="/workbench" :icon="DataBoard" label="工作台" />
        <SidebarNavigationItem index="/company-management" :icon="OfficeBuilding" label="公司管理" />
        <li class="el-menu-item sidebar-session-item" role="menuitem" tabindex="0" aria-label="会话" title="会话" @click="openHeaderChat" @keydown.enter.prevent="openHeaderChat" @keydown.space.prevent="openHeaderChat"><el-badge :value="chatMentionTotal" :max="99" :hidden="!chatMentionTotal"><el-icon><ChatDotRound /></el-icon></el-badge><span v-show="!isCollapse" class="sidebar-session-title"><span>会话</span><a :href="sessionNewTabHref" target="_blank" rel="noopener noreferrer" class="sidebar-session-open" title="在新标签页打开" aria-label="会话：在新标签页打开" @click.stop @keydown.stop><TopRight aria-hidden="true" /></a></span></li>

        <!-- 业务链路：从新咨询到项目执行 -->
        <li v-if="showBusinessGroup && !isCollapse" class="menu-group-label" role="presentation"><span>业务管理</span></li>
        <SidebarNavigationItem v-if="showConsultations" index="/consultations" :icon="Phone" label="新咨询管理" />

        <SidebarNavigationItem v-if="canViewProjects" index="/translation-details" :icon="EditPen" label="笔译项目" />
        <SidebarNavigationItem v-if="canViewProjects" index="/interpretation-details" :icon="SpeakingProfileIcon" label="口译项目" />
        <SidebarNavigationItem v-if="canViewAnnotation" index="/annotation-details" :icon="Headset" label="标注项目" />
        <SidebarNavigationItem v-if="canViewProjects" index="/recruitment-details" :icon="Suitcase" label="招聘项目" />
        <SidebarNavigationItem v-if="canViewManuscript" index="/manuscript-arrangements" :icon="Calendar" label="稿件安排" />

        <!-- 协作资源：客户、资源需求与人才资源池 -->
        <li v-if="showResourceGroup && !isCollapse" class="menu-group-label" role="presentation"><span>资源协作</span></li>
        <SidebarNavigationItem v-if="showClients" index="/clients" :icon="Connection" label="客户信息" />
        <SidebarNavigationItem v-if="showResourceManagement" :index="resourceManagementPath" :icon="Avatar" label="资源管理" />

        <SidebarNavigationItem v-if="canViewHr" index="/hr-management/shifts" :icon="Management" label="人事管理" />
        <!-- 账户、扩展能力和管理员入口统一归入平台设置 -->
        <li v-if="!isCollapse" class="menu-group-label" role="presentation"><span>平台设置</span></li>
        <SidebarNavigationItem index="/profile" :icon="Postcard" label="个人中心" />
        <SidebarNavigationItem v-if="showPendingModules" index="/pending-modules" :icon="QuestionFilled" label="更多模块" />

        <SidebarNavigationItem v-if="showSystemMenu" :index="systemNavigation[0].path" :icon="Setting" label="系统管理" />
      </el-menu>
      <transition name="logo-text">
        <div v-show="!isCollapse" class="sidebar-version">{{ appVersion }} · 更新于 {{ appUpdatedAt }}</div>
      </transition>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-tooltip :content="collapseLabel" placement="bottom" :disabled="isMobileViewport">
            <el-button
              class="collapse-btn"
              :icon="isMobileViewport ? (mobileNavOpen ? Fold : Expand) : (isCollapse ? Expand : Fold)"
              :aria-label="collapseLabel"
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
          <AutoDraftCenter :show-entry="false" />
          <ScreenshotControl />
          <AnnotationChatInbox />
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
        <RouteSectionNavigation v-if="isSystemSection" :items="systemNavigation" label="系统管理二级导航" class="system-section-navigation" />
        <router-view v-slot="{ Component, route }">
          <transition name="fade-transform" mode="out-in">
            <component v-if="Component" :is="Component" :key="route.path" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
    <ResourceRequestDailyNotesDialog
      v-if="notesState.open"
      :model-value="notesState.open"
      :minimized="notesState.minimized"
      :can-edit="canEditNotes"
      @minimize="minimizeNotes"
      @update:model-value="value => { if (!value) closeNotes() }"
    />
    <ProjectChatDock :has-extra-tasks="notesState.open && notesState.minimized">
      <template #tasks>
        <button v-if="notesState.open && notesState.minimized" type="button" class="floating-dock-task" title="恢复需求说明" aria-label="恢复需求说明" @click="openNotes">
          <el-icon><Document /></el-icon>
          <span>需求说明</span>
        </button>
      </template>
    </ProjectChatDock>
    <ChatIssueCollector v-if="issueCollectorLoaded" />
    <AnnotationMaterialEditor v-if="materialEditor.loaded" />
    <AnnotationMaterialDialogs v-if="materialDialogs.loaded" />
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { ref, computed, defineAsyncComponent, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { User, Suitcase, Connection, Avatar, Management, Postcard, Setting, Document, EditPen, Headset, Calendar, OfficeBuilding, ArrowDown, DataBoard, Phone, ChatDotRound, QuestionFilled, Fold, Expand, TopRight } from '@element-plus/icons-vue'
import {
  canViewManuscriptArrangements,
  canViewTalentResourceLibrary,
  hasPermission
} from '../utils/permission'
import NotificationBell from '../components/NotificationBell.vue'
import AnnotationChatInbox from '@/components/chat/AnnotationChatInbox.vue'
import ProjectChatDock from '@/components/chat/ProjectChatDock.vue'
import { useAnnotationFollowed } from '@/composables/useAnnotationFollowed'
import { useProjectChatDock } from '@/composables/useProjectChatDock'
import { chatEntryContext } from '@/utils/chatEntryContext'
import { canManageDepartments, canConfigureWorkReports, canManageHr } from '@/utils/permission'
import { useDepartmentCatalog } from '@/composables/useDepartmentCatalog'
useDepartmentCatalog()
import { useResourceNotesDock } from '@/composables/useResourceNotesDock'
import { useMaterialEditor } from '@/composables/useMaterialEditor'
import { useMaterialDialogs } from '@/composables/useMaterialDialogs'
import { useResourceIssues } from '@/composables/useResourceIssues'
import UiZoomControl from '../components/UiZoomControl.vue'
import AutoDraftCenter from '../components/common/AutoDraftCenter.vue'
import ScreenshotControl from '../components/ScreenshotControl.vue'
import SidebarNavigationItem from '@/components/common/SidebarNavigationItem.vue'
import RouteSectionNavigation from '@/components/common/RouteSectionNavigation.vue'
import SpeakingProfileIcon from '@/components/common/SpeakingProfileIcon.vue'
import { useUiZoom } from '../composables/useUiZoom'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { logout } from '@/api/auth'
import { clearAuthSession } from '@/utils/authSession'

const route = useRoute()
const router = useRouter()
const { access: issueAccess, collector: issueCollector, refreshIssueAccess } = useResourceIssues()
const issueCollectorLoaded = ref(false)
const ChatIssueCollector = defineAsyncComponent(() => import('@/components/chat/ChatIssueCollector.vue'))
watch(() => issueCollector.visible, value => { if (value) issueCollectorLoaded.value = true })
const { openFullscreen } = useProjectChatDock()
const { mentionTotal: chatMentionTotal } = useAnnotationFollowed()
const { state: materialEditor } = useMaterialEditor()
const { state: materialDialogs } = useMaterialDialogs()
const AnnotationMaterialDialogs = defineAsyncComponent(() => import('@/components/annotation/AnnotationMaterialDialogs.vue'))
const AnnotationMaterialEditor = defineAsyncComponent(() => import('@/components/annotation/AnnotationMaterialEditor.vue'))
const sessionNewTabHref = computed(() => router.resolve({ path: '/workbench', query: { openSession: '1', ...(chatEntryContext(route) ? { sessionContext: chatEntryContext(route) } : {}) } }).href)
async function openHeaderChat() {
  const mentions = chatMentionTotal.value > 0
  openFullscreen()
  await nextTick()
  window.dispatchEvent(new CustomEvent('chat-show-messages', { detail: { mentions, context: route.query?.openSession === '1' && ['annotation','translation','interpretation','recruitment'].includes(route.query?.sessionContext) ? route.query.sessionContext : chatEntryContext(route) } }))
}
const ResourceRequestDailyNotesDialog = defineAsyncComponent(() => import('@/views/resource/components/ResourceRequestDailyNotesDialog.vue'))
const { state: notesState, openNotes, minimizeNotes, closeNotes } = useResourceNotesDock()
const canEditNotes = computed(() => hasPermission('projects:write'))
onBeforeUnmount(closeNotes)
const { openPanel, syncFromStorage } = useUiZoom()

const STORAGE_COLLAPSE_KEY = 'sidebar_collapse'
const appVersion = 'V1.7'
const appUpdatedAt = '2026-09-23 19:55'

/** 侧边栏是否折叠 */
const { isMobile: isMobileViewport } = useMobileViewport()
const preferredCollapse = ref(false)
const mobileNavOpen = ref(false)
const isCollapse = computed(() => !isMobileViewport.value && preferredCollapse.value)
const sidebarMenuRef = ref()

/** 侧边栏宽度；手机端为离屏抽屉，宽度由样式固定。 */
const sidebarWidth = computed(() => (isMobileViewport.value ? '240px' : isCollapse.value ? '64px' : '200px'))

function toggleCollapse() {
  if (isMobileViewport.value) {
    mobileNavOpen.value = !mobileNavOpen.value
    return
  }
  preferredCollapse.value = !preferredCollapse.value
  try {
    localStorage.setItem(STORAGE_COLLAPSE_KEY, preferredCollapse.value ? '1' : '0')
  } catch {}
}

const collapseLabel = computed(() => {
  if (isMobileViewport.value) return mobileNavOpen.value ? '关闭菜单' : '打开菜单'
  return isCollapse.value ? '展开菜单' : '收起菜单'
})

watch(() => route.fullPath, () => { mobileNavOpen.value = false })
watch(isMobileViewport, () => { mobileNavOpen.value = false })

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_COLLAPSE_KEY)
    if (saved !== null) preferredCollapse.value = saved === '1'
  } catch {}
  syncFromStorage()
  refreshIssueAccess().catch(() => {})
  if (route.query.openSession === '1') void openHeaderChat()
})

const canViewUsers = computed(() => hasPermission('system:users:read'))
const canViewHr = computed(() => canManageHr())
const canViewDepartments = computed(() => canManageDepartments())
const canViewReportSettings = computed(() => canConfigureWorkReports())
const canViewRoles = computed(() => hasPermission('system:roles:read'))
const canViewMailSettings = computed(() => hasPermission('system:mail_settings:read'))
const canViewProjectAudits = computed(() => hasPermission('system:audit:read'))
const showSystemMenu = computed(() => canViewDepartments.value || canViewUsers.value || canViewReportSettings.value || canViewRoles.value || canViewMailSettings.value || canViewProjectAudits.value)

const systemNavigation=computed(()=>[
  ...((canViewUsers.value||canViewDepartments.value||canViewReportSettings.value)?[{path:'/users',label:'组织架构'}]:[]),
  ...(canViewRoles.value?[{path:'/roles',label:'角色管理'}]:[]),
  ...(canViewMailSettings.value?[{path:'/mail-settings',label:'项目邮件设置'}]:[]),
  ...(canViewProjectAudits.value?[{path:'/project-operation-audits',label:'项目操作审计'}]:[])
])
const isSystemSection=computed(()=>systemNavigation.value.some(item=>item.path===route.path))

/** 是否显示「工作台」（所有员工） */
const showWorkbench = computed(() => hasPermission(['projects:read', 'tasks:read']))
/** 菜单入口与路由守卫、后端读取权限保持同一口径。 */
const canViewProjects = computed(() => hasPermission('projects:read'))
const canViewAnnotation = computed(() => hasPermission([
  'projects:read',
  'annotation_accounts:read',
  'annotation_accounts:write'
]))
const canViewManuscript = computed(() => canViewManuscriptArrangements())
const showClients = computed(() => hasPermission('clients:read'))
const showConsultations = computed(() => hasPermission('consultations:read'))
const showResourceManagement = computed(() => canViewTalentResourceLibrary() || issueAccess.can_enter)
const resourceManagementPath = computed(() => canViewTalentResourceLibrary() ? '/resource-management/talent-overview' : '/resource-management/resource-development?section=issues')
const showBusinessGroup = computed(() => (
  showConsultations.value || canViewProjects.value || canViewAnnotation.value
))
const showResourceGroup = computed(() => (
  showClients.value || showResourceManagement.value
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
  if(path==='/hr-management'||path.startsWith('/hr-management/'))return '/hr-management/shifts'
  if(systemNavigation.value.some(item=>item.path===path))return systemNavigation.value[0]?.path||path
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
    return resourceManagementPath.value
  }
  return path
}

const activeMenu = computed(() => resolveActiveMenu(route.path))

const currentPageTitle = computed(() => {
  if (route.name === 'AnnotationChildOrders' && route.query.orderScope === 'grandchild') return '标注三级订单管理'
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
    clearAuthSession()
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
  --sidebar-active-accent: #cbd5e1;
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
  padding: 0 12px;
  background: var(--color-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-right: 8px;
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
  padding: 10px 12px 14px;
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
  padding: 0 12px;
  border-radius: 10px;
  transition: color 180ms ease, background-color 180ms ease, transform 180ms ease;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  transform: translateX(2px);
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.2);
}

.sidebar-menu :deep(.el-menu-item.is-active::before) {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sidebar-active-accent);
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
  padding: 0 12px;
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
  padding-left: 28px !important;
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
  margin: 14px 14px 4px;
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
@media (max-width: 560px) {
  .header-left { flex: none; }
  .header-left :deep(.el-breadcrumb) { display: none; }
  .header-right { gap: 8px; }
  .header-right :deep(.ui-zoom-step) { display: none; }
}

@media (max-width: 768px) {
  /* 手机端侧边栏为离屏抽屉，由头部按钮打开，不再常驻占用屏幕宽度。 */
  .sidebar--drawer {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: 2100;
    width: min(240px, 82vw) !important;
    transform: translateX(-100%);
    transition: transform 220ms ease;
    box-shadow: none;
  }

  .sidebar--drawer.is-open {
    transform: translateX(0);
    box-shadow: 6px 0 24px rgba(15, 23, 42, 0.28);
  }

  .sidebar-mask {
    position: fixed;
    inset: 0;
    z-index: 2090;
    background: rgba(15, 23, 42, 0.45);
  }

  .sidebar-menu :deep(.el-menu-item),
  .sidebar-menu :deep(.el-sub-menu__title) {
    height: 48px;
    line-height: 48px;
  }

  .logo h2 {
    font-size: 16px;
  }

  .header {
    height: 52px;
    padding: 0 8px;
  }

  .header-left {
    gap: 4px;
  }

  .header-right {
    gap: 8px;
  }

  .header-right :deep(.ui-zoom-control) {
    display: none;
  }

  .main-content {
    padding: 8px;
  }

  .username {
    display: none;
  }

  .user-info {
    padding: 6px;
  }
}
</style>


<style scoped>.sidebar-session-item{cursor:pointer}.sidebar-session-item .el-badge{display:inline-flex;align-items:center;margin-right:5px}.sidebar-session-item:focus-visible{outline:2px solid #93c5fd;outline-offset:-2px}</style>

<style scoped>
.sidebar-session-title{display:inline-flex;flex:1;align-items:center;gap:4px;min-width:0;max-width:260px}.sidebar-session-title>span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sidebar-session-open{display:inline-flex;flex:0 0 20px;align-items:center;justify-content:center;width:20px;height:20px;border-radius:4px;color:inherit;opacity:.35;text-decoration:none}.sidebar-session-item:hover .sidebar-session-open{opacity:.65}.sidebar-session-open:hover,.sidebar-session-open:focus-visible{background:rgba(148,163,184,.12);opacity:1}.sidebar-session-open svg{width:12px;height:12px}.sidebar-session-open:focus-visible{outline:2px solid #93c5fd;outline-offset:1px}
</style>

<style scoped>.system-section-navigation{margin-bottom:8px}</style>
