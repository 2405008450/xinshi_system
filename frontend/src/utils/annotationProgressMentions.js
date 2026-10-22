import { managerIds } from './annotationManagerChange.js'

export function progressMentionSelection(defaults, project, users, currentUserId) {
  const allowed=new Set(users.map(user=>String(user.id)))
  return [...new Set([...managerIds(project||{},'project_manager'),...(defaults||[])].map(String))]
    .filter(id=>id!==String(currentUserId)&&allowed.has(id))
}

export function expandProgressMentionDepartments(selection,users){
  const departments=new Set(selection.departmentIds||[])
  return {departmentIds:[],userIds:[...new Set([...(selection.userIds||[]),...users.filter(user=>[user.departmentId,...(user.departmentIds||[])].some(id=>departments.has(id))).map(user=>user.id)])]}
}
