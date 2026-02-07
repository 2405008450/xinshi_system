<template>
  <el-container class="layout-container">
    <el-aside :width="sidebarWidth" class="sidebar" :class="{ 'sidebar--collapsed': isCollapse }">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="28"><OfficeBuilding /></el-icon>
        </div>
        <transition name="logo-text">
          <div v-show="!isCollapse" class="logo-text">
            <h2>信实翻译公司</h2>
            <span class="logo-subtitle">翻译项目管理平台</span>
          </div>
        </transition>
      </div>
      <div class="sidebar-extra" :class="{ 'sidebar-extra--collapsed': isCollapse }">
        <MockSwitch />
        <transition name="fade">
          <span v-show="!isCollapse" class="sidebar-extra-label">Mock模式</span>
        </transition>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
      >
        <!-- 仅超级管理员可见：用户/角色/用户角色关联 -->
        <template v-if="showFullMenu">
          <el-menu-item index="/users">
            <el-icon><User /></el-icon>
            <template #title>用户管理</template>
          </el-menu-item>
          <el-menu-item index="/roles">
            <el-icon><Key /></el-icon>
            <template #title>角色管理</template>
          </el-menu-item>
          <el-menu-item index="/user-roles">
            <el-icon><Connection /></el-icon>
            <template #title>用户角色关联</template>
          </el-menu-item>
          <el-divider class="menu-divider" />
        </template>
        <!-- 项目管理：超级管理员看全部，其他角色仅看笔译 -->
        <el-sub-menu index="/project-management">
          <template #title>
            <el-icon><Folder /></el-icon>
            <span>项目管理</span>
          </template>
          <el-sub-menu index="/project-management/translation">
            <template #title>笔译项目管理</template>
            <el-menu-item index="/project-management/translation">
              <template #title>项目流程</template>
            </el-menu-item>
            <el-menu-item index="/project-management/translation/project-details">
              <template #title>项目详情</template>
            </el-menu-item>
            <el-menu-item index="/project-management/translation/project-files">
              <template #title>项目文件</template>
            </el-menu-item>
          </el-sub-menu>
          <template v-if="showFullMenu">
            <el-menu-item index="/project-management/interpretation">
              <template #title>口译项目管理</template>
            </el-menu-item>
            <el-menu-item index="/project-management/annotation">
              <template #title>标注项目管理</template>
            </el-menu-item>
            <el-menu-item index="/project-management/recruitment">
              <template #title>招聘项目管理</template>
            </el-menu-item>
            <el-menu-item index="/project-management/other">
              <template #title>其他项目管理</template>
            </el-menu-item>
          </template>
        </el-sub-menu>
        <!-- 工作安排：超级管理员 或 项目经理 -->
        <el-menu-item v-if="showWorkSchedule" index="/work-schedule">
          <el-icon><ChatLineRound /></el-icon>
          <template #title>工作安排</template>
        </el-menu-item>
        <template v-if="showFullMenu">
          <el-menu-item index="/technology-management">
            <el-icon><QuestionFilled /></el-icon>
            <template #title>技术管理</template>
          </el-menu-item>
          <el-divider class="menu-divider" />
          <el-sub-menu index="/resource-management">
            <template #title>
              <el-icon><Avatar /></el-icon>
              <span>资源管理</span>
            </template>
            <el-menu-item index="/resource-management/translators">
              <template #title>译员信息</template>
            </el-menu-item>
            <el-menu-item index="/resource-management/annotators">
              <template #title>标注员</template>
            </el-menu-item>
            <el-menu-item index="/resource-management/suppliers">
              <template #title>供应商</template>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/client-management">
            <template #title>
              <el-icon><OfficeBuilding /></el-icon>
              <span>客户管理</span>
            </template>
            <el-menu-item index="/client-management/clients">
              <template #title>客户信息</template>
            </el-menu-item>
            <el-menu-item index="/client-management/subsidiary-clients">
              <template #title>子公司客户信息</template>
            </el-menu-item>
            <el-menu-item index="/client-management/client-contacts">
              <template #title>客户联系人及回访</template>
            </el-menu-item>
            <el-menu-item index="/client-management/consultations">
              <template #title>咨询基本情况</template>
            </el-menu-item>
          </el-sub-menu>
          <el-divider class="menu-divider" />
          <el-menu-item index="/finance">
            <el-icon><Money /></el-icon>
            <template #title>财务管理</template>
          </el-menu-item>
          <el-menu-item index="/marketing">
            <el-icon><Promotion /></el-icon>
            <template #title>营销管理</template>
          </el-menu-item>
          <el-sub-menu index="/hr-management">
            <template #title>
              <el-icon><User /></el-icon>
              <span>人力管理</span>
            </template>
            <el-menu-item index="/hr-management/attendance">
              <template #title>考勤管理</template>
            </el-menu-item>
            <el-menu-item index="/hr-management/kpi">
              <template #title>KPI管理</template>
            </el-menu-item>
            <el-menu-item index="/hr-management/salary">
              <template #title>薪酬管理</template>
            </el-menu-item>
            <el-menu-item index="/hr-management/onboarding">
              <template #title>入职管理</template>
            </el-menu-item>
            <el-menu-item index="/hr-management/offboarding">
              <template #title>离职管理</template>
            </el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/administration-management">
            <template #title>
              <el-icon><House /></el-icon>
              <span>内务管理</span>
            </template>
            <el-menu-item index="/administration-management/office">
              <template #title>办公室管理</template>
            </el-menu-item>
            <el-menu-item index="/administration-management/office-equipment">
              <template #title>办公室设备管理</template>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/procurement">
            <el-icon><ShoppingCart /></el-icon>
            <template #title>采购管理</template>
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
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { ref, computed, onMounted } from 'vue'
import { User, Key, Folder, Connection, Avatar, OfficeBuilding, ArrowDown, ChatLineRound, QuestionFilled, Money, Promotion, House, ShoppingCart, Fold, Expand } from '@element-plus/icons-vue'
import MockSwitch from '../components/MockSwitch.vue'
import { isSuperAdmin, getStoredRoles, hasRole, ROLE_PROJECT_MANAGER, ROLE_CUSTOMER_SPECIALIST, ROLE_PROJECT_SPECIALIST, ROLE_TEST, ROLE_REVIEW, ROLE_SALES } from '../utils/permission'

const route = useRoute()
const router = useRouter()

const STORAGE_COLLAPSE_KEY = 'sidebar_collapse'

/** 侧边栏是否折叠 */
const isCollapse = ref(false)

/** 侧边栏宽度 */
const sidebarWidth = computed(() => (isCollapse.value ? '64px' : '240px'))

function toggleCollapse() {
  isCollapse.value = !isCollapse.value
  try {
    localStorage.setItem(STORAGE_COLLAPSE_KEY, isCollapse.value ? '1' : '0')
  } catch {}
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_COLLAPSE_KEY)
    if (saved !== null) isCollapse.value = saved === '1'
  } catch {}
})

/** 是否显示完整菜单（超级管理员） */
const showFullMenu = computed(() => isSuperAdmin())

/** 是否显示工作安排（超级管理员、项目经理、客户专员、项目专员均可查看） */
const showWorkSchedule = computed(() => showFullMenu.value || hasRole([ROLE_PROJECT_MANAGER, ROLE_CUSTOMER_SPECIALIST, ROLE_PROJECT_SPECIALIST, ROLE_TEST, ROLE_REVIEW, ROLE_SALES]))

/** 当前用户名（可从 token 或存储解析，此处简单显示） */
const displayName = computed(() => {
  const roles = getStoredRoles()
  if (roles.length) return roles.join('、') || '用户'
  return '用户'
})

const activeMenu = computed(() => {
  return route.path
})

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
    // 跳转到系统设置
    console.log('系统设置')
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
    localStorage.removeItem('user_name')
    router.push('/login')
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  background: linear-gradient(180deg, #1f2937 0%, #111827 100%);
  color: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.28s ease;
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
  height: 70px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
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
  color: #d1d5db;
  height: 50px;
  line-height: 50px;
  margin: 4px 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.sidebar-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

.sidebar-menu :deep(.el-menu-item .el-icon) {
  margin-right: 8px;
  font-size: 18px;
}

.sidebar-menu :deep(.el-sub-menu) {
  margin: 4px 12px;
}

.sidebar-menu :deep(.el-sub-menu__title) {
  color: #d1d5db;
  height: 50px;
  line-height: 50px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.1);
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
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
  color: #374151;
}

.collapse-btn:hover {
  color: #2563eb;
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
  transition: all 0.3s ease;
}

.user-info:hover {
  background: #f3f4f6;
}

.username {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.main-content {
  background: #f9fafb;
  padding: 24px;
  overflow-y: auto;
}

/* 页面切换动画 */
.fade-transform-leave-active,
.fade-transform-enter-active {
  transition: all 0.3s ease;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* 响应式 */
@media (max-width: 768px) {
  .sidebar {
    width: 200px !important;
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
}
</style>
