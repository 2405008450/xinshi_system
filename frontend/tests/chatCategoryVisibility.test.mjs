import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
const source=readFileSync(new URL('../src/composables/useChatSessionCategories.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replaceAll('export ','')
test('群聊权限回收后目录不能继续保留旧缓存，同时保留可见节点较新修订',()=>{
 const api=runInNewContext(source+';({applySessionCategories,sessionCategories})',{reactive:value=>value})
 api.applySessionCategories({ready:true,items:[{id:'hidden',revision:1},{id:'visible',revision:3}]})
 api.applySessionCategories({ready:true,items:[{id:'visible',revision:2}]})
 assert.equal(api.sessionCategories.items.length,1)
 assert.equal(api.sessionCategories.items[0].id,'visible')
 assert.equal(api.sessionCategories.items[0].revision,3)
})
