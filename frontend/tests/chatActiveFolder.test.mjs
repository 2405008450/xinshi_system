import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
const defaults=JSON.parse(readFileSync(new URL('../../data/chat_session_folders.json',import.meta.url),'utf8'))
const resourceFolderId=defaults.find(row=>row.ruleKey==='resource').id,resourceDiscussionIds=defaults.filter(row=>row.parentKey===resourceFolderId).map(row=>row.id)
const folderSource=readFileSync(new URL('../src/utils/chatSessionFolders.js',import.meta.url),'utf8')
const matchSource=folderSource.slice(folderSource.indexOf('export function sessionMatchesFolder'),folderSource.indexOf('export function sessionFolderCount')).replace('export ','')
const sessionMatchesFolder=runInNewContext(matchSource+';sessionMatchesFolder',{resourceFolderId,normalizeAnnotationStatus:value=>value})
const source=readFileSync(new URL('../src/utils/chatActiveFolder.js',import.meta.url),'utf8').replace(/^import .*$/gm,'').replace('export ','')
const activeFolder=runInNewContext(source+';activeConversationFolder',{resourceFolderId,resourceDiscussionIds,sessionMatchesFolder})
const nodes=defaults.filter(row=>!row.parentKey)
test('通知从资源讨论跳到标注项目时，同步到标注分组',()=>{assert.equal(activeFolder({projectType:'annotation',projectId:'p'},nodes,resourceFolderId),nodes.find(row=>row.ruleKey==='annotation').id)})
test('其他模块和直接聊天不会沿用不相干分组',()=>{for(const type of ['translation','interpretation','recruitment'])assert.equal(activeFolder({projectType:type,projectId:'p'},nodes,resourceFolderId),nodes.find(row=>row.ruleKey===type).id);assert.equal(activeFolder({projectType:'direct',projectId:'p'},nodes,resourceFolderId),'')})
test('自建会话按分类定位，资源讨论按固定一级分组定位',()=>{const custom=[...nodes,{id:'custom',parentKey:null},{id:'child',parentKey:'custom'}];assert.equal(activeFolder({projectType:'discussion',projectId:'child',categoryIds:['child']},custom,resourceFolderId),'custom');assert.equal(activeFolder({projectType:'discussion',projectId:resourceDiscussionIds[0]},nodes,''),resourceFolderId)})
