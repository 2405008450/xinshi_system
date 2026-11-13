import { defineComponent, h, Text, cloneVNode } from 'vue'
import { ElTableColumn, ElDescriptions, ElDescriptionsItem } from 'element-plus'
import ScreenshotText from './ScreenshotText.vue'
import { screenshotIds } from '@/utils/screenshotReferences'
import ClientManagementLink from './ClientManagementLink.vue'
import { isClientShortName } from '@/utils/clientManagementWindow'

const fieldValue = (row, prop) => String(prop || '').split('.').reduce((value, key) => value?.[key], row)
const subClientField = (label, prop) => label === '子客户简称' || /^sub_?client/i.test(prop || '')

function descriptionText(nodes) {
  return nodes.map(node => {
    if (typeof node === 'string') return node
    if (typeof node?.children === 'string') return node.children
    return Array.isArray(node?.children) ? descriptionText(node.children) : ''
  }).join('').trim()
}

function descriptionSlot(attrs, slot) {
  return () => {
    const valueNodes = slot?.()
    const nodes = Array.isArray(valueNodes) ? valueNodes : valueNodes == null ? [] : [valueNodes]
    if (isClientShortName(attrs.label) && attrs['client-link-disabled'] === undefined) {
      const value = descriptionText(nodes)
      if (value) return h(ClientManagementLink, { value, row: attrs['client-row'], subClient: subClientField(attrs.label) })
    }
    return renderNodes(nodes)
  }
}

// 保留原有插槽与格式化器，只把含截图引用的文本节点换成授权图片。
function renderNodes(nodes) {
  return (nodes == null ? [] : Array.isArray(nodes) ? nodes : [nodes]).map(node=>{
    if(typeof node==='string')return screenshotIds(node).length?h(ScreenshotText,{text:node}):node
    if(node?.type===Text && screenshotIds(node.children).length)return h(ScreenshotText,{text:node.children})
    if(typeof node?.children==='string'&&screenshotIds(node.children).length){const copy=cloneVNode(node);copy.children=[h(ScreenshotText,{text:node.children})];copy.shapeFlag=(copy.shapeFlag&~8)|16;copy.dynamicChildren=null;copy.patchFlag=-2;return copy}
    if(Array.isArray(node?.children)){const copy=cloneVNode(node);copy.children=renderNodes(node.children);copy.dynamicChildren=null;copy.patchFlag=-2;return copy}
    if(node?.children&&typeof node.children==='object'){
      const copy=cloneVNode(node);copy.children={...node.children}
      for(const [name,slot] of Object.entries(node.children))if(typeof slot==='function')copy.children[name]=(...args)=>renderNodes(slot(...args))
      copy.patchFlag|=1024;return copy
    }
    return node
  })
}
export const ScreenshotTableColumn=defineComponent({
  inheritAttrs:false,
  setup(_, {attrs,slots}) {
    return ()=>h(ElTableColumn,attrs,{
      ...slots,
      ...(slots.default || attrs.prop || isClientShortName(attrs.label) ? {default:scope=>{
        const value = fieldValue(scope.row, attrs.prop)
        if (isClientShortName(attrs.label, attrs.prop)) {
          const name = value ?? scope.row.clientShortName ?? scope.row.client_short_name ?? scope.row.shortName
          if (typeof name === 'string') return h(ClientManagementLink, { value: name, row: scope.row, subClient: subClientField(attrs.label, attrs.prop) })
        }
        if (slots.default) return renderNodes(slots.default(scope))
        const formatted=attrs.formatter?attrs.formatter(scope.row,scope.column,value,scope.$index):value
        return screenshotIds(formatted).length?h(ScreenshotText,{text:String(formatted)}):formatted
      }}:{})
    })
  }
})
// Descriptions 按原生子项名称收集字段，必须保留 ElDescriptionsItem 节点身份。
// 在父级转换字段插槽，才能同时保留布局与截图显示。
export const ScreenshotDescriptionsItem=defineComponent({
  name:'ElDescriptionsItem',
  inheritAttrs:false,
  setup(_, {attrs,slots}) {
    return () => {
      const { 'client-link-disabled': _disabled, 'client-row': _row, ...itemAttrs } = attrs
      return h(ElDescriptionsItem, itemAttrs, { ...slots, default: descriptionSlot(attrs, slots.default) })
    }
  }
})

function descriptionItems(nodes) {
  return nodes.map(node => {
    // ElDescriptions reads the item vnode's slots directly without mounting it.
    if (node?.type?.name === 'ElDescriptionsItem' && isClientShortName(node.props?.label)) {
      const copy = cloneVNode(node)
      copy.children = { ...node.children, default: descriptionSlot(node.props, node.children?.default) }
      return copy
    }
    if (Array.isArray(node?.children)) {
      const copy = cloneVNode(node)
      copy.children = descriptionItems(node.children)
      copy.dynamicChildren = null
      copy.patchFlag = -2
      return copy
    }
    return node
  })
}
export const ScreenshotDescriptions=defineComponent({
  name: 'ScreenshotDescriptions',
  inheritAttrs:false,
  setup(_, {attrs,slots}) {return ()=>h(ElDescriptions,attrs,{...slots,default:()=>descriptionItems(renderNodes(slots.default?.()) || [])})}
})
