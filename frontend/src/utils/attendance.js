export const durationLabel=value=>{const minutes=Math.round(Number(value||0)*100)/100;const absolute=Math.abs(minutes),hours=Math.floor(absolute/60);const rest=Math.round((absolute-hours*60)*100)/100;return (minutes<0?'-':'')+(hours?`${hours}小时${rest?`${rest}分钟`:''}`:`${rest}分钟`)}
export const attendanceWindow=form=>({start_at:`${form.start_at}+08:00`,end_at:`${form.end_at}+08:00`})
