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
      style: {
        minWidth: 0,
        maxWidth: '100%',
        borderTop: '1px solid var(--color-border, #e2e8f0)',
        padding: showSelection ? '10px 14px' : '8px 14px',
        background: 'var(--color-page-bg, #f8fafc)',
        whiteSpace: 'normal',
        textAlign: 'left',
      },
      onMousedown: event => event.stopPropagation(),
    }, [
      showSelection ? h('div', { class: 'multi-select-summary__count', style: { fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary, #475569)', marginBottom: '6px' } }, `已选 ${props.labels.length} 项`) : null,
      showSelection ? h('div', { role: 'list', style: { display: 'flex', flexWrap: 'wrap', gap: '5px', maxHeight: 'min(120px,22vh)', overflowY: 'auto', overscrollBehavior: 'contain' } },
        props.labels.length ? props.labels.map((label, index) => h('span', {
          key: index, role: 'listitem', title: String(label),
          style: { maxWidth: '100%', overflowWrap: 'anywhere', background: 'var(--color-surface, #ffffff)', color: 'var(--color-text-primary, #111827)', border: '1px solid var(--color-border, #e2e8f0)', borderRadius: '6px', padding: '1px 8px', fontSize: '12px', lineHeight: '20px' },
        }, String(label))) : h('span', { style: { color: 'var(--color-text-muted, #64748b)', fontSize: '12px' } }, '尚未选择')) : null,
      props.showConfirm ? h('div', { style: { display: 'flex', justifyContent: 'flex-end', paddingTop: showSelection ? '8px' : 0 } }, [
        h(ElButton, { type: 'primary', size: 'small', style: { minHeight: '28px', height: '28px', padding: '4px 12px' }, onClick: event => { event.stopPropagation(); emit('confirm') } }, { default: () => '确认' }),
      ]) : null,
    ])
    }
  },
})
