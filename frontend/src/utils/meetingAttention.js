import {ref} from 'vue'

// 复用全局会议宿主的状态，多个会话窗口无需各自轮询。
export const meetingAttentionCount=ref(0)
