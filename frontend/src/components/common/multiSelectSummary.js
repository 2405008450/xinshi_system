import { defineComponent, h } from 'vue'
import { ElButton } from 'element-plus'

// 用于下拉面板和自定义复选浮窗；独立滚动已选标签，避免挤占选项区。
export default defineComponent({
  name: 'MultiSelectSummary',
  props: { labels: { type: Array, default: () => [] }, optionCount: { type: Number, default: Infinity }, showConfirm: { type: Boolean, default: true } },
  emits: ['confirm'],
  setup(props, { emit }) {
    return () => {
      const showSelection = props.optionCount > 5
      return h('section', {
      class: ['multi-select-summary', !showSelection && 'multi-select-summary--compact'], 'aria-label': showSelection ? '已选项汇总' : '多选确认',
      'data-option-count': props.optionCount,
      style: { minWidth: 0, maxWidth: '100%', borderTop: showSelection ? '1px solid var(--el-border-color-lighter)' : 'none', paddingTop: showSelection ? '8px' : 0, whiteSpace: 'normal', textAlign: 'left' },
      onMousedown: event => event.stopPropagation(),
    }, [
      showSelection ? h('div', { class: 'multi-select-summary__count', style: { fontSize: '12px', color: 'var(--el-text-color-secondary)', marginBottom: '6px' } }, `已选 ${props.labels.length} 项`) : null,
      showSelection ? h('div', { role: 'list', style: { display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: 'min(140px,25vh)', overflowY: 'auto', overscrollBehavior: 'contain' } },
        props.labels.length ? props.labels.map((label, index) => h('span', {
          key: index, role: 'listitem', title: String(label),
          style: { maxWidth: '100%', overflowWrap: 'anywhere', background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', border: '1px solid var(--el-border-color-lighter)', borderRadius: '4px', padding: '2px 7px', fontSize: '12px', lineHeight: '20px' },
        }, String(label))) : h('span', { style: { color: 'var(--el-text-color-placeholder)', fontSize: '12px' } }, '尚未选择')) : null,
      props.showConfirm ? h('div', { style: { display: 'flex', justifyContent: 'flex-end', paddingTop: showSelection ? '8px' : 0 } }, [
        h(ElButton, { type: 'primary', size: 'small', onClick: event => { event.stopPropagation(); emit('confirm') } }, { default: () => '确认' }),
      ]) : null,
    ])
    }
  },
})
