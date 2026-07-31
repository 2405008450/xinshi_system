<template>
  <el-card class="pending-modules">
    <template #header>
      <div>
        <div class="page-title">待完善模块</div>
        <div class="page-subtitle">以下页面暂未接入真实业务数据，统一收纳在这里便于调试。</div>
      </div>
    </template>

    <div class="module-groups">
      <section v-for="group in visibleModuleGroups" :key="group.title" class="module-group">
        <h3>{{ group.title }}</h3>
        <div class="module-grid">
          <button
            v-for="item in group.items"
            :key="item.path"
            type="button"
            class="module-entry"
            @click="router.push(item.path)"
          >
            <span>{{ item.name }}</span>
            <small>{{ item.description }}</small>
          </button>
        </div>
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { hasPermission, isSuperAdmin } from '@/utils/permission'

const router = useRouter()

const moduleGroups = [
  {
    title: '项目类型',
    items: [
      { name: '口译项目管理', path: '/interpretation', description: '模拟表单' },
      { name: '标注项目管理', path: '/annotation', description: '模拟表单' },
      { name: '招聘项目管理', path: '/recruitment', description: '模拟表单' },
      { name: '其他项目管理', path: '/other', description: '模拟表单' },
    ],
  },
  {
    title: '业务管理',
    items: [
      { name: '客户联系人及回访', path: '/client-contacts', description: '待继续完善', permission: 'clients:read' },
      { name: '财务管理', path: '/finance', description: '待继续完善', permission: 'finance:read' },
      { name: '技术管理', path: '/technology-management', description: '暂无数据' },
      { name: '营销管理', path: '/marketing', description: '模拟表单' },
      { name: '采购管理', path: '/procurement', description: '模拟表单' },
    ],
  },
  {
    title: '人力管理',
    items: [
      { name: '考勤管理', path: '/hr-management/attendance', description: '模拟表单' },
      { name: 'KPI 管理', path: '/hr-management/kpi', description: '模拟表单' },
      { name: '薪酬管理', path: '/hr-management/salary', description: '模拟表单' },
      { name: '入职管理', path: '/hr-management/onboarding', description: '模拟表单' },
      { name: '离职管理', path: '/hr-management/offboarding', description: '模拟表单' },
    ],
  },
  {
    title: '内务管理',
    items: [
      { name: '办公室管理', path: '/administration-management/office', description: '模拟表单' },
      { name: '办公设备管理', path: '/administration-management/office-equipment', description: '模拟表单' },
    ],
  },
]

const visibleModuleGroups = computed(() => moduleGroups
  .map(group => ({
    ...group,
    items: group.items.filter(item =>
      isSuperAdmin() || (item.permission && hasPermission(item.permission))
    ),
  }))
  .filter(group => group.items.length))
</script>

<style scoped>
.page-title {
  font-size: 18px;
  font-weight: 600;
}

.page-subtitle {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.module-groups {
  display: grid;
  gap: 20px;
}

.module-group h3 {
  margin: 0 0 10px;
  color: var(--el-text-color-primary);
  font-size: 15px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.module-entry {
  min-height: 72px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, background-color 0.2s;
}

.module-entry:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.module-entry span,
.module-entry small {
  display: block;
}

.module-entry span {
  font-weight: 500;
}

.module-entry small {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
}
</style>
