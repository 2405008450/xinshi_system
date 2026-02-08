# 工作安排页面职责重构说明

**当前状态**：已完成「双页拆分」与工作台、composable、共享组件；排班管理页仍使用原有内联数据与 load/save。`scheduleDefaultData.js` 中默认部门名单为精简版，完整名单仍在 `WorkSchedule.vue` 内；若需工作台与排班共用一个默认数据源，可将 `WorkSchedule.vue` 内 `getDefaultDeptPersonData` 迁移到 `scheduleDefaultData.js` 并让排班页改用 `useScheduleData()`。

## 1️⃣ 拆分后的文件结构建议

```
frontend/src/views/schedule/
├── REFACTOR.md                 # 本说明
├── scheduleDefaultData.js      # 默认排班数据（无 Vue 依赖）
├── composables/
│   └── useScheduleData.js      # 排班数据状态与 load/save/复制
├── components/
│   ├── ScheduleHeader.vue      # 日期 + 星期 + 可选管理员按钮
│   ├── MyTasksPanel.vue        # 我的任务（只读表格）
│   ├── ShiftTableReadonly.vue  # 今日班次只读表
│   ├── OverviewPanel.vue       # 总览（急稿说明+PM+班次+请假+统计）
│   ├── TranslatorPanel.vue     # 译员安排（中英/英中）
│   ├── DepartmentsPanel.vue    # 各部门安排
│   ├── NotScheduledPanel.vue   # 暂不安排
│   └── AllTasksPanel.vue       # 全部项目
├── dialogs/
│   ├── TaskFormDialog.vue
│   ├── ShiftFullEditDialog.vue
│   ├── ShiftRowEditDialog.vue
│   ├── LeaveNotesEditDialog.vue
│   └── TranslatorTableEditDialog.vue
├── WorkSchedule.vue            # 管理页（≤600 行）
└── WorkDashboard.vue           # 工作台/普通用户页（≤400 行）
```

## 2️⃣ 从 WorkSchedule.vue 移动到 WorkDashboard.vue 的逻辑/模块

| 模块 | 说明 |
|------|------|
| **我的任务** | 整块 Tab 迁至 WorkDashboard，作为主内容；WorkSchedule 不再包含。 |
| **今日班次（只读）** | 在 WorkDashboard 中仅展示班次表 + 请假/调休列表，无编辑入口。 |
| **当前用户与「我的任务」匹配** | `currentUserName`、`initCurrentUserName`、`myTasksList` 仅保留在 WorkDashboard（或通过 useScheduleData + 本地 computed）。 |
| **与当前用户相关的概览** | 可选：在 WorkDashboard 显示“今日我的任务数”或“所在班次”等简要信息。 |

**保留在 WorkSchedule.vue 的**：总览（含编辑）、译员安排、各部门安排、暂不安排、全部项目、所有弹窗与写操作。

## 3️⃣ 路由（仅结构）

- `/admin/schedule` → WorkSchedule.vue（管理页）
- `/workbench` → WorkDashboard.vue（工作台）

现有 `/work-schedule` 可重定向到 `/admin/schedule` 或保留并指向 WorkSchedule.vue，由你选择。

## 3️⃣ 示例代码（页面骨架与引用）

**WorkDashboard.vue 引用关系：**
```vue
<script setup>
import ScheduleHeader from './components/ScheduleHeader.vue'
import MyTasksPanel from './components/MyTasksPanel.vue'
import ShiftTableReadonly from './components/ShiftTableReadonly.vue'
import { useScheduleData } from './composables/useScheduleData'
// 使用 useScheduleData() 得到 scheduleDate, weekdayLabel, deptPersonData, shiftTableData, leaveNotes, loadScheduleForDate
// 本地 computed myTasksList 由 deptPersonData + currentUserName 推导
</script>
```

**WorkSchedule.vue（管理页）** 仍保留原有内联逻辑；仅去掉「我的任务」Tab、默认 Tab 改为「总览」。后续可改为：
- 使用 `useScheduleData()` 替代本地 refs 与 load/save；
- 使用 `<ScheduleHeader show-admin-actions />` 替代顶部栏；
- 将各 Tab 内容拆到 `components/*Panel.vue`、弹窗拆到 `dialogs/*.vue`。

## 4️⃣ 重构风险与注意事项

- **数据源统一**：两页均通过 `useScheduleData()` 读写同一 localStorage key（`work_schedule_YYYY-MM-DD`），避免两套逻辑不一致。
- **默认数据体积**：`getDefaultDeptPersonData()` 体量大，单独放在 `scheduleDefaultData.js`，便于维护与测试。
- **样式复用**：从 WorkSchedule 抽离的组件需保留原有 class（如 `section-block`、`data-table`），必要时将公共样式放到 `schedule` 下共用 scoped 或共享样式文件。
- **权限**：路由层仅做结构拆分，真实鉴权（如仅管理员可访问 `/admin/schedule`）需在路由守卫或后端中实现。
- **入口与导航**：侧栏需区分「工作台」(workbench) 与「排班管理」(admin/schedule)，避免普通用户误入管理页。
