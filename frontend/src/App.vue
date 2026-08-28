<template>
  <router-view />
</template>

<script setup>
</script>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  min-height: 100%;
  overflow: hidden;
}

body {
  color: var(--color-text-primary);
  background: var(--color-page-bg);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

button,
input,
textarea,
select {
  font: inherit;
}

:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* 全局容器 */
.el-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  transition: border-color 200ms ease, box-shadow 200ms ease;
}

.el-card:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow-card);
}

.el-card__header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-primary);
  font-weight: 600;
}

/* 表格 */
.el-table {
  --el-table-header-bg-color: var(--color-surface-muted);
  --el-table-row-hover-bg-color: var(--color-page-bg);
  --el-table-current-row-bg-color: var(--color-primary-soft);
  --el-table-border-color: var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  overflow: hidden;
}

.el-table th.el-table__cell {
  color: var(--color-text-secondary);
  font-weight: 600;
}

.el-table .el-table__row {
  transition: background-color 180ms ease;
}

/* 按钮 */
.el-button {
  min-height: 36px;
  border-radius: var(--radius-sm);
  font-weight: 500;
  transition: color 180ms ease, background-color 180ms ease, border-color 180ms ease,
    box-shadow 180ms ease;
}

.el-button--primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
}

.el-button--primary:hover,
.el-button--primary:focus-visible {
  border-color: var(--color-primary-hover);
  background: var(--color-primary-hover);
}

.el-button--primary:active {
  border-color: var(--color-primary-active);
  background: var(--color-primary-active);
}

/* 表单 */

/* Element Plus 在 .el-input / .el-textarea 作用域内把 --el-input-text-color
   重定义为 --el-text-color-regular(本系统 #475569)，会遮蔽 :root 上的设置，
   且与只读字段同色而无法区分。必须在同一作用域覆盖。
   加 :root 前缀把特异性提到 0,2,0 压过 EP 的 0,1,0——本文件的样式在开发模式下
   先于 element-plus 注入，靠源码顺序无法取胜，且构建后顺序还会变化。 */
:root .el-input,
:root .el-textarea {
  --el-input-text-color: var(--field-text-editable);
}

.el-input__wrapper,
.el-select__wrapper,
.el-textarea__inner {
  border-radius: var(--radius-md);
  transition: box-shadow 180ms ease;
}

.el-input__wrapper:not(.is-disabled):hover,
.el-select__wrapper:not(.is-disabled):hover {
  box-shadow: 0 0 0 1px var(--field-border-hover) inset;
}

.el-input__wrapper.is-focus,
.el-select__wrapper.is-focused,
.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--field-border-focus) inset;
}

.el-form-item__label {
  color: var(--color-text-secondary);
  font-weight: 500;
}

/* 弹窗、下拉层 */
.el-dialog {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-dropdown);
}

.el-dialog__header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.el-dialog__title {
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
}

.el-dialog__body {
  padding: 24px;
}

.el-dialog__footer {
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
  background: var(--color-page-bg);
}

.el-dropdown__popper,
.el-select__popper,
.el-picker__popper {
  box-shadow: var(--shadow-dropdown);
}

/* 分页和标签 */
.el-pagination {
  justify-content: flex-end;
  margin-top: 20px;
}

.el-pagination .btn-prev,
.el-pagination .btn-next,
.el-pagination .el-pager li {
  border-radius: var(--radius-sm);
}

.el-pagination .el-pager li.is-active {
  background: var(--color-primary);
  color: #fff;
}

.el-tag {
  border-radius: var(--radius-sm);
  font-weight: 500;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--color-surface-muted);
}

::-webkit-scrollbar-thumb {
  border: 2px solid var(--color-surface-muted);
  border-radius: 8px;
  background: #94a3b8;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}
</style>
