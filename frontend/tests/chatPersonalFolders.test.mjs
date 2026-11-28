import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {dragChatSession} from '../src/utils/chatPersonalFolders.js'
const source=readFileSync(new URL('../src/components/chat/ChatWorkspace.vue',import.meta.url),'utf8')
const listCode=source.slice(source.indexOf('const visibleSessions = computed('),source.indexOf('watch(()=>recentInFolder.value.length'))+';visibleSessions.value'
const ref=value=>({value})
function view(folder,keyword=''){
 const sessions=[{key:'discussion:a',projectType:'discussion',projectId:'a',title:'需求讨论'},{key:'direct:b',projectType:'direct',projectId:'b',title:'单聊'},{key:'discussion:c',projectType:'discussion',projectId:'c',title:'其他群'}]
 return runInNewContext(listCode,{computed:fn=>ref(fn()),privateFolder:ref(folder),allMentionSessions:ref(sessions),props:{sessions,searchSessions:sessions,activeKey:'',annotationFilters:{mine:true,statuses:['in_progress']}},appliedKeyword:ref(keyword),annotationMentionView:ref(false),selectedFolder:ref(''),tab:ref('all'),annotationMode:ref('group'),annotationFiltersActive:ref(Boolean(folder)),personalFollowingFolderId:'following',folderNodes:ref([]),mentionSort:ref('time_desc'),inGroup:()=>true,sessionMatchesFolder:()=>true,normalizeAnnotationStatus:x=>x,groupSessionList:x=>x,compareSessionActivity:()=>0,compareMentionSessions:()=>0,matchesSearch:(text,q)=>text.includes(q)})
}
test('个人目录可同时显示群聊与单聊，并保持目录内的关键字范围',()=>{
 const scope={sessions:[{key:'discussion:a',projectType:'discussion',projectId:'a',title:'需求讨论'},{key:'direct:b',projectType:'direct',projectId:'b',title:'单聊'}]}
 assert.deepEqual(Array.from(view(scope),row=>row.key),['discussion:a','direct:b'])
 assert.deepEqual(Array.from(view(scope,'单聊'),row=>row.key),['direct:b'])
 assert.equal(view({sessions:[]}).length,0)
 assert.deepEqual(Array.from(view(null),row=>row.key),['discussion:a','discussion:c'])
})
test('目录页的下划线编号在拖动时转换为统一会话身份',()=>{
 let payload;dragChatSession({dataTransfer:{setData:(type,value)=>{assert.equal(type,'application/x-xinshi-chat-session');payload=JSON.parse(value)}}},{key:'discussion:p1',projectType:'discussion',project_id:'p1',title:'群聊'})
 assert.equal(payload.projectId,'p1');assert.equal(payload.key,'discussion:p1')
})
