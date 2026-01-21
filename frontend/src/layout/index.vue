<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="sidebar">
      <div class="logo">
        <div class="logo-icon">
          <el-icon :size="28"><OfficeBuilding /></el-icon>
        </div>
        <div class="logo-text">
          <h2>信实翻译公司</h2>
          <span class="logo-subtitle">翻译项目管理平台</span>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px">
        <MockSwitch />
        <span>Mock模式</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        :collapse="false"
      >
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
        <!-- 项目管理子菜单 -->
        <el-sub-menu index="/project-management">
          <template #title>
            <el-icon><Folder /></el-icon>
            <span>项目管理</span>
          </template>
          <el-sub-menu index="/project-management/translation">
            <template #title>笔译项目管理</template>
            <el-menu-item index="/project-management/translation">
              <template #title>项目流程表</template>
            </el-menu-item>
            <el-menu-item index="/project-management/translation/project-details">
              <template #title>项目详情</template>
            </el-menu-item>
            <el-menu-item index="/project-management/translation/project-files">
              <template #title>项目文件</template>
            </el-menu-item>
          </el-sub-menu>
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
        </el-sub-menu>
        <el-menu-item index="/work-schedule">
          <el-icon><ChatLineRound /></el-icon>
          <template #title>工作安排</template>
        </el-menu-item>
        <el-menu-item index="/technology-management">
          <el-icon><QuestionFilled /></el-icon>
          <template #title>技术管理</template>
        </el-menu-item>
        <el-divider class="menu-divider" />
        <!-- 资源管理子菜单 -->
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
        <!-- 客户管理子菜单 -->
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
        <!-- 财务管理 -->
        <el-menu-item index="/finance">
          <el-icon><Money /></el-icon>
          <template #title>财务管理</template>
        </el-menu-item>
        <!-- 营销管理 -->
        <el-menu-item index="/marketing">
          <el-icon><Promotion /></el-icon>
          <template #title>营销管理</template>
        </el-menu-item>
        <!-- 人力管理子菜单 -->
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
        <!-- 内务管理子菜单 -->
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
        <!-- 采购管理 -->
        <el-menu-item index="/procurement">
          <el-icon><ShoppingCart /></el-icon>
          <template #title>采购管理</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="User" />
              <span class="username">管理员</span>
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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { User, Key, Folder, Connection, Avatar, OfficeBuilding, ArrowDown, ChatLineRound, QuestionFilled, Money, Promotion, House, ShoppingCart } from '@element-plus/icons-vue'
import MockSwitch from '../components/MockSwitch.vue'

const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  // 对于嵌套路由，返回完整路径
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
