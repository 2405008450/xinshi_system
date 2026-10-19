import { formatBusinessDateTime } from './dateTime.js'
export const formatDate = value => value ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Hong_Kong' }).format(new Date(`${value}T00:00:00+08:00`)) : '-'
export const formatDateTime = formatBusinessDateTime
export const headcountText=(row)=>row.headcountMin==null?'-':(row.headcountMax!=null&&row.headcountMax!==row.headcountMin?`${row.headcountMin}–${row.headcountMax}人`:`${row.headcountMin}人`)
export const languageText=(row)=>(row.languageDirections||[]).map((item)=>item.label).join('；')||'-'
export const fullPeriodText=(row)=>row.employmentStart&&row.employmentEnd?`${formatDate(row.employmentStart)}—${formatDate(row.employmentEnd)}`:'-'
export const periodText=(row)=>fullPeriodText(row)
export const feeText=(row)=>row.serviceFeeType==='fixed'?`${row.serviceFeeCurrency||'CNY'} ${row.serviceFeeAmount??'-'}`:row.serviceFeeType==='annual_salary_rate'?`年薪 ${row.serviceFeeRate??'-'}%`:row.serviceFeeType==='monthly_salary_multiple'?`月薪 ${row.serviceFeeMultiplier??'-'}倍`:row.serviceFeeType==='other'?(row.serviceFeeNote||'其他'):'-'
const roleAssignmentName = (row, roleCode) => row.roleAssignments?.find((item) => item.roleCode === roleCode)?.assigneeName || '未分配'
export const recruitmentProjectDetailItems = [
  {label:'订单号',key:'orderNo'},
  {label:'项目名称',key:'projectName',editable:true,maxlength:500},
  {label:'职位描述',key:'jobDescription',span:2,editable:true,multiline:true},
  {label:'职位名称/类型',key:'positionTitle',editable:true,required:true,maxlength:255},
  {label:'招聘人数',key:'headcount',formatter:(_value,row)=>headcountText(row)},
  {label:'现客户经理',key:'clientManagerName'},
  {label:'项目状态',key:'projectStatus',type:'status'},
  {label:'项目经理',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_manager')},
  {label:'项目专员',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_specialist')},
  {label:'项目助理',key:'roleAssignments',formatter:(_value,row)=>roleAssignmentName(row,'project_assistant')},
  {label:'客户简称',key:'clientShortName'},
  {label:'客户编号',key:'clientCode'},
  {label:'客户全称',key:'clientName'},
  {label:'客户领域',key:'clientDomain'},
  {label:'子客户/联系人',key:'contactName',editable:true,maxlength:255},
  {label:'客户单号/项目标识',key:'customerOrderNo',editable:true,maxlength:150},
  {label:'外语/翻译方向',key:'languageSummary',span:2,formatter:(_value,row)=>languageText(row)},
  {label:'拟入职日期',key:'targetOnboard',formatter:(_value,row)=>row.targetOnboardType==='anytime'?'随时':formatDate(row.targetOnboardDate)},
  {label:'拟履职周期',key:'employmentPeriod',formatter:(_value,row)=>periodText(row)},
  {label:'任职工作属地',key:'workLocation',editable:true,required:true,maxlength:500},
  {label:'服务费用',key:'serviceFee',formatter:(_value,row)=>feeText(row)},
  {label:'费用说明',key:'serviceFeeNote',span:2,editable:true,multiline:true},
  {label:'简历人选数',key:'candidateCount',formatter:(value)=>`${value || 0} 人`},
  {label:'客户咨询时间',key:'customerConsultationTime'},
  {label:'客户确认时间',key:'customerConfirmationTime'},
  {label:'报价单路径',key:'quotationPath',span:2,editable:true,multiline:true},
  {label:'合同路径',key:'contractPath',span:2,editable:true,multiline:true},
  {label:'项目路径',key:'projectPath',span:2,editable:true,multiline:true},
  {label:'备注',key:'remarks',span:2,editable:true,multiline:true},
  {label:'邮件主题预览',key:'emailSubjectPreview',span:2,editable:true,multiline:true},
  {label:'发圈请求',key:'socialPostRequest',span:2,editable:true,multiline:true},
  {label:'资源请求',key:'resourceRequest',span:2,editable:true,multiline:true},
  {label:'创建时间',key:'createdAt'},
  {label:'更新时间',key:'updatedAt'},
]
