// 与后端一致：部门和指定人员取并集，全部部门不包含未分配部门人员。
export function reportScopePeople(scope,people) {
  const departments=new Set(scope.department_ids||[]),senders=new Set(scope.sender_ids||[])
  return people.filter(person=>person.active!==false&&(scope.senders_all||senders.has(person.id)||(person.departments||[]).some(department=>scope.all_departments||departments.has(department.id))))
}
