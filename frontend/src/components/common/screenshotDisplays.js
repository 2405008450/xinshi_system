import { defineComponent, h, Text, cloneVNode } from 'vue'
import { ElTableColumn, ElDescriptions, ElDescriptionsItem } from 'element-plus'
import ScreenshotText from './ScreenshotText.vue'
import { screenshotIds } from '@/utils/screenshotReferences'

// 保留原有插槽与格式化器，只把含截图引用的文本节点换成授权图片。
function renderNodes(nodes) {
  return nodes?.map(node=>{
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
      ...(slots.default?{default:scope=>renderNodes(slots.default(scope))}:attrs.prop?{default:scope=>{
        const value=String(attrs.prop).split('.').reduce((obj,key)=>obj?.[key],scope.row)
        const formatted=attrs.formatter?attrs.formatter(scope.row,scope.column,value,scope.$index):value
        return screenshotIds(formatted).length?h(ScreenshotText,{text:String(formatted)}):formatted
      }}:{})
    })
  }
})
export const ScreenshotDescriptionsItem=defineComponent({
  name:'ElDescriptionsItem',
  inheritAttrs:false,
  setup(_, {attrs,slots}) {return ()=>h(ElDescriptionsItem,attrs,{...slots,default:()=>renderNodes(slots.default?.())})}
})
export const ScreenshotDescriptions=defineComponent({
  inheritAttrs:false,
  setup(_, {attrs,slots}) {return ()=>h(ElDescriptions,attrs,{...slots,default:()=>renderNodes(slots.default?.())})}
})
