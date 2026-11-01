export const remainingTimeOptions = [
  ['under_30','30分钟内'], ['30_60','30-60分钟'], ['1_2h','1-2小时'],
  ['2_5h','2-5小时'], ['5_10h','5-10小时'], ['over_10h','10小时以上'],
].map(([value,label]) => ({value,label}))
export const workSlotLabel = slot => slot === 'end_shift' ? '下班汇报' : `${slot}:00 汇报`
export function openAnnotationWorkStatus(detail = {}) {
  window.dispatchEvent(new CustomEvent('open-annotation-work-status', {detail}))
}
