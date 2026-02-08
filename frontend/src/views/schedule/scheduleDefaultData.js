/**
 * 工作安排默认数据（无 Vue 依赖）
 * 完整 getDefaultDeptPersonData 从 WorkSchedule.vue 迁移后替换 defaultDeptPersonData 的引用即可。
 */

const defaultDeptPersonData = () => [
  { name: '伟琪', dept: '项目经理', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
  { name: '李娴', dept: '项目经理', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] },
  { name: '孟花', dept: '项目经理', status: 'scheduled', tasks: [{ category: '直接项目任务', content: '搜索自己名字', projectNo: '', deadline: '' }], fixedTasks: [] }
  // 完整名单见 WorkSchedule.vue getDefaultDeptPersonData，迁移后替换此数组
]

export function getDefaultDeptPersonData() {
  return defaultDeptPersonData()
}

export function getDefaultScheduleData() {
  return {
    deptPersonData: getDefaultDeptPersonData(),
    notScheduledTasks: [
      { personName: '-', department: '翻译部', projectOrTask: '3w，李娴跟进：已派曹柳云9号早八点半回，Thomas审改，李娴导出完整版、给翠珍派一检二检，瑞珠排版，待安排内部细节检查', projectNo: 'TP260202016', remarks: '广州年鉴，中译英（母语），2月28日交' }
    ],
    pmRotationOrder: '伟琪 / 李娴 / 孟花',
    shiftTableData: [
      { shift: '早早班 8:30-18:00', layoutIt: '', client: '靖琳、楚翘', hr: '翠珍', translationProject: '伟琪' },
      { shift: '早班 9:00-18:30', layoutIt: '运坚、胜辉、浚轩、裕林、晨旭', client: '瑞珠', hr: '雅然、辛建、文慧', translationProject: '以龙、志林' },
      { shift: '9:30-18:30', layoutIt: '', client: '家铭（9点半）', hr: '立溶、舒婷、宇琪', translationProject: '旷姣' },
      { shift: '晚班 10:30-20:00', layoutIt: '美霞、苗丹、黄萌', client: '舒倩(晚班)', hr: '紫霞', translationProject: '振中、孟花' },
      { shift: '晚晚班 13:30-21:30', layoutIt: '大杰', client: '烨珊', hr: '颖琦、少洁、菀筠', translationProject: '李娴' },
      { shift: '8:45~9:30', layoutIt: '泉哥、武哥（销售）', client: '少妃、陈佳、韵钰', hr: '', translationProject: 'Thomas' }
    ],
    leaveNotes: [
      '武哥周五（2月6日）12:00后请假',
      'Thomas周五（0206）14:00开始请假，7、8点在家办公',
      '陈佳0206上午请假，0206下午、0208-0210、0215在家办公共5天，0211-0214请假4天',
      '瑞珠2月11日-14日（周三至周六）休年假',
      '以龙2月11日-14日请假四天',
      '美霞0213-0214调休两天'
    ],
    urgentTableZhEn: [
      { order: '2 中午12点后', name: '王婷', type: '全部', quality: '73', cloudRev: '-', dailyRate: '5/1000/8000', remarks: '法律类需审改，其他中英要求不是很高的可基本检查' },
      { order: '3 傍晚5点后', name: '王邃玲', type: '全部', quality: '80', cloudRev: '可/可', dailyRate: '5/1000/6000', remarks: '法律类需安排审改' },
      { order: '1', name: '高超', type: '全部', quality: '73', cloudRev: '可/可', dailyRate: '5/1000/8000', remarks: '大概仅适合银行，法律类需审改' },
      { order: 'N/A', name: '曹柳云', type: '全部', quality: '73', cloudRev: '可/可', dailyRate: '-', remarks: '非合同法律类需审改' },
      { order: '0', name: '孙红艳', type: '全部', quality: '74', cloudRev: '可/可', dailyRate: '2/500/2000', remarks: '中英要求不高的均可基本检查' },
      { order: '1', name: '商莹', type: '全部', quality: '74', cloudRev: '可/可', dailyRate: '3/500/3000', remarks: '不接法律和医学' },
      { order: 'N/A', name: '陈风', type: '全部', quality: '73', cloudRev: '-', dailyRate: '?/?/7000', remarks: '需审改' },
      { order: '2 中午12点后', name: '雷智', type: '全部', quality: '74', cloudRev: '-', dailyRate: '?/?/4000', remarks: '需审改' },
      { order: 'N/A', name: '何长青', type: '全部', quality: '74', cloudRev: '-', dailyRate: '?/?/4000', remarks: '需审改' },
      { order: '1', name: '李鲁莎', type: '全部', quality: '73', cloudRev: '-', dailyRate: '?/?/6000', remarks: '需审改' }
    ],
    urgentTableEnZh: [
      { order: '2（白天不做稿）', name: '史明月', type: '全部（不适合对中文要求高的）', quality: '74', cloudRev: '可/未知', dailyRate: '1/500/4000', remarks: '工作日中午和下午不能做稿，一般需审改' },
      { order: '1', name: '杨雪', type: '全部（法律类优先）', quality: '75', cloudRev: '可/未知', dailyRate: '5/350/3000', remarks: '律师，一般需审改' },
      { order: 'N/A', name: '王邃玲', type: '全部（中文较好）', quality: '78', cloudRev: '可/可', dailyRate: '5/500/4000', remarks: '注意优先安排中英项目' },
      { order: 'N/A', name: '曹柳云', type: '全部', quality: '75', cloudRev: '可/可', dailyRate: '5/500/4000', remarks: '一般需审改' },
      { order: '1', name: '梁昌金', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '5/500/4000', remarks: '一般需审改' },
      { order: '1', name: '熊建磊', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '-', remarks: '一般要审改' },
      { order: '1', name: '张留寰', type: '全部', quality: '75', cloudRev: '可/未知', dailyRate: '-', remarks: '一般要审改' },
      { order: '1', name: '乔艳红', type: '全部', quality: '75', cloudRev: '可/可', dailyRate: '?/?/7000', remarks: '急稿可不改' }
    ]
  }
}
