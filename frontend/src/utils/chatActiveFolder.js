import {resourceFolderId,resourceDiscussionIds,sessionMatchesFolder} from './chatSessionFolders'
export function activeConversationFolder(session,nodes,current=''){
 const type=session.projectType||session.kind
 if(type==='direct')return ''
 const resource=type==='discussion'&&(session.subtitle==='资源开拓讨论'||resourceDiscussionIds.includes(String(session.projectId)))
 if(current&&!(type==='discussion'&&current===resourceFolderId&&!resource)&&sessionMatchesFolder(session,current,nodes))return current
 const categories=session.categoryIds||[]
 const category=nodes.find(row=>categories.includes(row.id))
 if(category){let root=category;const seen=new Set();while(root.parentKey&&!seen.has(root.id)){seen.add(root.id);const parent=nodes.find(row=>row.id===root.parentKey);if(!parent)break;root=parent}return root.id}
 if(type==='discussion'&&(session.subtitle==='资源开拓讨论'||resourceDiscussionIds.includes(String(session.projectId))))return resourceFolderId
 return nodes.find(row=>!row.parentKey&&row.ruleKey===type)?.id||''
}
