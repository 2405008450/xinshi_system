import { reactive } from 'vue'
export const technicalDevelopmentAccess = reactive({ userId: '', can_enter: false })
export function canViewTechnicalDevelopment() {
  return !!localStorage.getItem('user_id') && technicalDevelopmentAccess.userId === localStorage.getItem('user_id') && technicalDevelopmentAccess.can_enter
}
