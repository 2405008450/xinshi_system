<template>
  <el-menu-item :index="index" class="sidebar-navigation-item">
    <el-icon v-if="icon"><component :is="icon" /></el-icon>
    <template #title>
      <span class="sidebar-navigation-title">
        <span class="sidebar-navigation-label">{{ label }}</span>
        <a
          class="sidebar-navigation-open"
          :href="href"
          target="_blank"
          rel="noopener noreferrer"
          title="在新标签页打开"
          :aria-label="`${label}：在新标签页打开`"
          @click.stop
          @keydown.stop
        >
          <TopRight class="sidebar-navigation-open-icon" aria-hidden="true" />
        </a>
      </span>
    </template>
  </el-menu-item>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { TopRight } from '@element-plus/icons-vue'

const props = defineProps({
  index: { type: String, required: true },
  label: { type: String, required: true },
  icon: { type: [Object, Function], default: null }
})
const router = useRouter()
// 使用路由生成链接，动态菜单入口变化时同步更新目标地址。
const href = computed(() => router.resolve(props.index).href)
</script>

<style scoped>
.sidebar-navigation-title {
  display: inline-flex;
  flex: 1;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 260px;
  vertical-align: middle;
}

.sidebar-navigation-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-navigation-open {
  display: inline-flex;
  flex: 0 0 20px;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  color: inherit;
  opacity: 0.35;
  text-decoration: none;
  transition: opacity 160ms ease, background-color 160ms ease;
}

.sidebar-navigation-item:where(:hover) .sidebar-navigation-open {
  opacity: 0.65;
}

.sidebar-navigation-open:hover,
.sidebar-navigation-open:focus-visible {
  background: rgba(148, 163, 184, 0.12);
  opacity: 1;
}

.sidebar-navigation-open:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 1px;
}

.sidebar-navigation-open-icon {
  width: 12px;
  height: 12px;
}
</style>
