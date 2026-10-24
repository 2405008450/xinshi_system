<template>
  <DraggableFormDialog :model-value="modelValue" @update:model-value="$emit('update:modelValue',$event)" width="min(1500px, calc(100vw - 32px))" top="3vh" maximizable class="paired-workspace" @open="load" destroy-on-close>
    <template #header><div class="workspace-heading"><strong @mousedown.stop>{{contextLabel}}</strong><span>双人采标管理 · {{levelLabel}}</span></div></template>
    <div v-loading="loading">
      <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="load">重新加载</el-button></el-alert>
      <template v-if="workspace">
        <div class="workspace-tools"><AnnotationProjectDetailPopover :project-id="project.id" :summary="project" reference-text="查看项目详情" /><BusinessDetailPopover :row="workspace" title="联系安排详情"><template #reference><el-button link type="primary">查看联系安排</el-button></template><template #content><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="item in [{key:'strategy',label:'联系策略'},{key:'moments',label:'发圈安排'},{key:'posts',label:'发帖安排'},{key:'handover',label:'交接说明'}]" :key="item.key" :label="item.label" :span="2"><div class="pre-wrap">{{workspace.notes[item.key] || '-'}}</div></el-descriptions-item></el-descriptions></template></BusinessDetailPopover><el-tag v-if="workspace.archived" type="info">已归档，只读</el-tag><el-button v-if="canWrite" @click="editSettings">联系安排与工作区设置</el-button><el-button @click="openHistory()">操作历史</el-button><el-link v-if="canAccounts" :href="accountUrl" target="_blank">平台与账号管理</el-link></div>
        <el-tabs v-model="tab">
          <el-tab-pane v-for="item in tabs" :key="item.value" :label="item.label" :name="item.value" />
        </el-tabs>
        <PairedEntityList :key="`${project.id}:${tab}`" ref="listRef" :project-id="project.id" :kind="tab" :editable="editable" :columns="columns" :search-placeholder="tab==='contacts'?'搜索姓名、资源编号':'搜索分组或任务名称'">
          <template #toolbar>
            <template v-if="editable">
              <template v-if="tab==='contacts'"><el-button v-if="canTalents" @click="openCandidates">引用人才</el-button><el-button v-if="canTalentWrite" @click="newTalent()">新增人才/搭档</el-button></template>
              <el-button v-else-if="tab==='groups'" type="primary" @click="editGroup()">新增分组</el-button>
              <el-button v-else-if="tab==='collection'" type="primary" @click="editTask()">新增采集批次</el-button>
            </template>
          </template>
          <template #cell="{row,column}">
            <el-link v-if="column.key==='person.full_name'" :href="talentUrl(row.person_id)" target="_blank">{{row.person?.full_name || '-'}}</el-link>
            <span v-else>{{cell(row,column)}}</span>
          </template>
          <template #details="{row}">
            <el-descriptions-item v-for="entry in details(row)" :key="entry.label" :label="entry.label" :span="2"><div class="pre-wrap">{{entry.value || '-'}}</div></el-descriptions-item>
          </template>
          <template #actions="{row}">
            <template v-if="tab==='contacts'"><el-button v-if="editable" link type="primary" @click="editContact(row)">编辑</el-button><el-button v-if="editable" link type="primary" @click="addFollowUp(row)">跟进</el-button><el-button link @click="contactDetails(row)">联系明细</el-button></template>
            <template v-else-if="tab==='groups'"><el-button v-if="editable" link type="primary" @click="editGroup(row)">调整分组</el-button><el-button link @click="openHistory(row.id)">历史</el-button></template>
            <template v-else><el-button v-if="editable" link type="primary" @click="editTask(row)">编辑</el-button><el-button link type="primary" @click="openRecords(row)">过程记录</el-button><el-button v-if="editable&&tab==='collection'" link type="primary" @click="openTransfer(row)">转入标注</el-button></template>
          </template>
        </PairedEntityList>
      </template>
      <el-empty v-else-if="!error&&!loading" description="该订单尚未建立双人采标工作区，需由有编辑权限的人员首次打开" />
    </div>
    <template #footer><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>

  <PairedFormEditor v-model="editor.visible" :title="editor.title" :subtitle="contextLabel" :value="form" :fields="editor.fields" :saving="saving" :error="editor.error" :conflict="editor.conflict" @save="saveEditor" @reload="reloadEditor">
    <template v-if="editor.kind==='contacts'">
      <el-divider>可工作时间</el-divider>
      <div v-for="(item,index) in form.availability" :key="item.key" class="repeat-row" data-dialog-field-search-group>
        <el-form-item label="安排类型"><el-select v-model="item.type"><el-option label="具体日期" value="date"/><el-option label="工作日" value="weekday"/><el-option label="周末" value="weekend"/><el-option label="例外日期/节假日" value="exception"/></el-select></el-form-item>
        <el-form-item v-if="['date','exception'].includes(item.type)" label="日期" :prop="`availability.${index}.date`" :rules="[{required:true,message:'请选择日期',trigger:'change'}]"><el-date-picker v-model="item.date" value-format="YYYY-MM-DD"/></el-form-item>
        <el-form-item label="时间段或说明"><el-input v-model="item.time" placeholder="例如 19:00—21:00；该日不可用"/></el-form-item><el-button link type="danger" @click="form.availability.splice(index,1)">移除</el-button>
      </div>
      <el-button @click="form.availability.push({key:crypto.randomUUID(),type:'weekday',date:'',time:''})">增加时间安排</el-button>
      <el-divider>渠道状态</el-divider>
      <div v-for="(item,index) in form.channel_states" :key="item.key" class="repeat-row" data-dialog-field-search-group>
        <el-form-item label="渠道"><el-select v-model="item.channel"><el-option v-for="option in channelOptions" :key="option.value" :value="option.value" :label="option.label"/></el-select></el-form-item>
        <el-form-item label="具体账号/群名" :prop="`channel_states.${index}.target`" :rules="[{required:true,message:'请填写具体账号或群名',trigger:'blur'}]"><el-input v-model="item.target"/></el-form-item><el-form-item label="状态"><el-select v-model="item.status"><el-option label="正常" value="正常"/><el-option label="已删好友" value="已删好友"/><el-option label="已退群" value="已退群"/></el-select></el-form-item><el-button link type="danger" @click="form.channel_states.splice(index,1)">移除</el-button>
      </div>
      <el-button @click="form.channel_states.push({key:crypto.randomUUID(),channel:'wecom',target:'',status:'正常'})">增加渠道状态</el-button>
      <el-divider>各语言口音</el-divider>
      <div v-for="skill in form.language_skills" :key="skill.id" class="repeat-row"><el-form-item :label="skill.label+'口音'"><el-input v-model="skill.accent" :disabled="!canTalentWrite" maxlength="255"/></el-form-item><el-button v-if="canTalentWrite" @click="updateAccent(skill)">保存到人才总库</el-button></div>
    </template>
    <template v-if="editor.kind==='talent'&&duplicates.length"><el-alert title="发现疑似重复人才，请选择关联，或确认姓名不同后独立新建。" type="warning" :closable="false"/><el-button v-for="person in duplicates" :key="person.id" @click="linkDuplicate(person)">关联 {{person.full_name || person.fullName}}（{{person.resource_code || person.resourceCode || '-'}}）</el-button><el-checkbox v-model="form.allow_duplicate">已核对，独立新建档案</el-checkbox></template>
    <template v-if="editor.kind==='transfer'"><el-alert title="仅转入选中的批次。若只转入其中一部分，请先新增独立采集批次，并在原批次说明拆分范围。重复转入不会重复创建标注任务。" :closable="false"/></template>
  </PairedFormEditor>

  <DraggableFormDialog v-model="candidatesVisible" title="引用已登记人才" width="min(1100px, calc(100vw - 32px))" append-to-body>
    <el-alert title="人数仅代表系统可识别人才；群登记人数为人次，不据此推断成员或跨群去重。复制与加入联系表不会标记已联系。" :closable="false"/>
    <div class="paired-toolbar"><el-input v-model="candidateQuery.keyword" placeholder="姓名、资源编号" clearable @input="scheduleCandidates" @keyup.enter="loadCandidates"/><el-select v-model="candidateQuery.language_id" clearable placeholder="语言/方言" @change="loadCandidates"><el-option v-for="language in languages" :key="language.id" :value="language.id" :label="language.label"/></el-select><el-select v-model="candidateQuery.channel" clearable placeholder="渠道" @change="loadCandidates"><el-option v-for="option in channelOptions.filter(item=>item.value!=='project_group')" :key="option.value" :value="option.value" :label="option.label"/></el-select><el-input v-model="candidateQuery.company_account" placeholder="公司对接账号，如HR1企微" clearable @input="scheduleCandidates"/><el-button @click="loadCandidates">查询</el-button><el-button @click="resetCandidates">重置</el-button></div>
    <div class="paired-toolbar"><span>当前筛选人才 {{candidateTotal}} 人；按比例只选未加入人才</span><el-select v-model="ratio" style="width:130px"><el-option v-for="value in [10,20,30,40,50,60,70,80,90,100]" :key="value" :value="value" :label="value+'%'"/></el-select><el-button @click="applyRatio">按比例预选</el-button><span>已选 {{candidateSelection.length}} 人</span><el-button @click="copyCandidates">复制已选联系资料</el-button><el-date-picker v-model="candidateQuery.added_date" type="date" value-format="YYYY-MM-DD" placeholder="成功加微日期" @change="loadCandidates"/></div>
    <el-alert v-if="groupStatistics" :closable="false" :title="`企微项目大群：已建 ${groupStatistics.built_group_count} 个，已登记 ${groupStatistics.recorded_group_count} 个，登记合计 ${groupStatistics.people_count_total ?? '未登记'} 人次（未跨群去重）`"/><div class="daily-new"><el-button v-for="day in dailyNew" :key="day.date" link @click="candidateQuery.added_date=day.date;loadCandidates()">{{day.date}} 新开拓 {{day.count}} 人</el-button></div>
    <el-table ref="candidateTable" :data="candidates" row-key="id" border max-height="400" v-loading="candidateLoading" @selection-change="candidateSelection=$event"><el-table-column type="selection" width="50" :selectable="row=>!row.joined"/><el-table-column prop="resource_code" label="资源编号"/><el-table-column prop="full_name" label="姓名"/><el-table-column label="语言/口音"><template #default="{row}">{{row.language_skills.map(item=>item.label+(item.accent?'（'+item.accent+'）':'')).join('、')}}</template></el-table-column><el-table-column label="公司账号"><template #default="{row}">{{(row.company_accounts||[]).join('、')}}</template></el-table-column><el-table-column label="状态"><template #default="{row}">{{row.joined?'已加入本订单':'未加入'}}</template></el-table-column></el-table>
    <template #footer><el-button @click="candidatesVisible=false">关闭</el-button><el-button :loading="saving" :disabled="!candidateSelection.length" type="primary" @click="joinCandidates">加入联系表（{{candidateSelection.length}}）</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="recordsVisible" :title="`${activeTask?.name || ''} · 过程记录`" width="min(1120px, calc(100vw - 32px))" append-to-body>
    <div class="paired-toolbar"><el-select v-model="recordKind"><el-option v-for="kind in recordKinds" :key="kind.value" :value="kind.value" :label="kind.label"/></el-select><el-button v-if="editable" type="primary" @click="editRecord()">新增{{optionLabel(recordKinds,recordKind)}}</el-button><el-button @click="refreshRecords">刷新</el-button><el-button v-if="editable&&recordKind==='account'&&activeTask?.source_task_id" @click="useCollectionAccounts">使用采集账号</el-button></div>
    <el-table :data="visibleRecords" border><el-table-column prop="position" label="序号" width="65"/><el-table-column prop="title" label="记录名称"/><el-table-column label="内容"><template #default="{row}">{{recordSummary(row)}}</template></el-table-column><el-table-column label="人员"><template #default="{row}">{{names(row.person_ids)}}</template></el-table-column><el-table-column label="更新时间"><template #default="{row}">{{formatBusinessDateTime(row.updated_at)}}</template></el-table-column><el-table-column label="详情" fixed="right" width="100"><template #default="{row}"><BusinessDetailPopover :row="row" title="阶段记录详情"><template #content><el-descriptions :column="2" border size="small"><el-descriptions-item v-for="entry in recordDetails(row)" :key="entry.label" :label="entry.label">{{entry.value}}</el-descriptions-item></el-descriptions></template></BusinessDetailPopover></template></el-table-column><el-table-column label="操作" fixed="right" width="200"><template #default="{row}"><el-button v-if="editable" link @click="editRecord(row)">编辑</el-button><el-button v-if="editable&&recordKind==='progress'" link @click="editRecord(null,row.id)">在后面插入</el-button><el-button link @click="openHistory(row.id)">调整历史</el-button></template></el-table-column></el-table>
    <template #footer><el-button @click="recordsVisible=false">关闭</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="contactVisible" :title="`${activeContact?.person?.full_name || ''} · 联系明细`" width="min(960px, calc(100vw - 32px))" append-to-body>
    <el-descriptions :column="2" border size="small"><el-descriptions-item v-for="entry in details(activeContact || {})" :key="entry.label" :label="entry.label" :span="2"><div class="pre-wrap">{{entry.value || '-'}}</div></el-descriptions-item></el-descriptions>
    <h4>跟进记录</h4><div v-for="entry in activeContact?.data?.follow_ups || []" :key="entry.created_at" class="history-entry"><strong>{{entry.contact_date}} · {{entry.actor_name}}</strong><span>{{optionLabel(followChannels,entry.channel)}} · {{formatBusinessDateTime(entry.created_at)}}</span><p class="pre-wrap">{{entry.content}}</p></div>
    <h4>附件</h4><el-button v-for="file in activeContact?.data?.attachments || []" :key="file.id" link @click="download(file)">{{file.name}}</el-button><el-upload v-if="editable" :show-file-list="false" :http-request="upload"><el-button>上传附件（不超过10MB）</el-button></el-upload>
    <template #footer><el-button @click="openHistory(activeContact.id)">修改历史</el-button><el-button @click="contactVisible=false">关闭</el-button></template>
  </DraggableFormDialog>

  <DraggableFormDialog v-model="historyVisible" title="操作与调整历史" width="min(960px, calc(100vw - 32px))" append-to-body>
    <div v-for="entry in history.items" :key="entry.id" class="history-entry"><strong>{{entry.actor_name}} · {{actionLabel(entry.action)}} · {{formatBusinessDateTime(entry.created_at)}}</strong><el-descriptions :column="2" border size="small"><el-descriptions-item label="修改前"><pre>{{humanSnapshot(entry.before)}}</pre></el-descriptions-item><el-descriptions-item label="修改后"><pre>{{humanSnapshot(entry.after)}}</pre></el-descriptions-item></el-descriptions></div>
    <el-pagination :total="history.total" :page-size="20" :current-page="historyPage" layout="total, prev, pager, next" @current-change="historyPage=$event;loadHistory()"/>
    <template #footer><el-button @click="historyVisible=false">关闭</el-button></template>
  </DraggableFormDialog>
</template>

<script setup>
import {computed,nextTick,onBeforeUnmount,reactive,ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import * as api from '@/api/annotationPaired'
import * as ops from '@/api/annotationOps'
import {getProjectLanguages} from '@/api/projectLanguages'
import {hasPermission,isSuperAdmin} from '@/utils/permission'
import {businessDateTimeInputValue,formatBusinessDateTime} from '@/utils/dateTime'
import {willingnessOptions,taskStatuses,recordKinds,optionLabel,selectCandidateRatio,pairedDuration} from '@/utils/annotationPaired'
import AnnotationProjectDetailPopover from './AnnotationProjectDetailPopover.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import PairedFormEditor from './PairedFormEditor.vue'
import PairedEntityList from './PairedEntityList.vue'
const props=defineProps({modelValue:Boolean,project:{type:Object,required:true}})
defineEmits(['update:modelValue'])
const router=useRouter(),workspace=ref(),people=ref([]),contacts=ref([]),groups=ref([]),staffOptions=ref([]),languages=ref([]),listRef=ref(),loading=ref(false),error=ref(''),saving=ref(false),tab=ref('contacts')
const canWrite=hasPermission('projects:write'),canTalents=hasPermission(['talents:read','talents:write','translators:read','translators:write']),canTalentWrite=hasPermission(['talents:write','translators:write']),canAccounts=hasPermission(['annotation_accounts:read','annotation_accounts:write'])
const editable=computed(()=>canWrite&&!workspace.value?.archived)
const contextLabel=computed(()=>`${props.project.orderNo || ''} · ${props.project.projectName || ''}`)
const levelLabel=computed(()=>['母订单','子订单','三级订单'][props.project.orderLevel ?? (props.project.parentProjectId?1:0)])
const accountUrl=computed(()=>router.resolve({name:'AnnotationProjectDetails',query:{projectId:props.project.id,section:'accounts',view:'project'}}).href)
const talentUrl=id=>router.resolve({name:'Talents',query:{openTalent:id}}).href
const tabs=[{value:'contacts',label:'项目联系'},{value:'groups',label:'分组管理'},{value:'collection',label:'采集管理'},{value:'annotation',label:'标注管理'}]
const channelOptions=[{value:'small_group',label:'企微小群'},{value:'project_group',label:'企微项目大群（仅登记）'},{value:'wecom',label:'企微好友'},{value:'wechat',label:'微信好友'}]
const responseOptions=[{value:'not_contacted',label:'尚未联系'},{value:'no_response',label:'没回复'},{value:'responded',label:'已回复'}]
const followChannels=[{value:'message',label:'留言追问'},{value:'wechat_call',label:'微信电话追问'},{value:'phone',label:'手机追问'},{value:'other',label:'其他'}]
const clone=value=>JSON.parse(JSON.stringify(value))
const message=e=>typeof e?.detail==='string'?e.detail:e?.detail?.message || e?.message || '操作失败'
const peopleOptions=computed(()=>people.value.map(person=>({value:person.id,label:`${person.resource_code || '-'} · ${person.full_name}`})))
const names=ids=>(ids||[]).map(id=>people.value.find(person=>person.id===id)?.full_name || '-').join('、') || '-'
const groupName=id=>groups.value.find(group=>group.id===id)?.name || '-'
const loadAll=async kind=>{const rows=[];let total=1;while(rows.length<total){const page=await api.list(props.project.id,kind,{skip:rows.length,limit:500});rows.push(...page.items);total=page.total;if(!page.items.length)break}return rows}
const refreshContext=async()=>{[people.value,contacts.value,groups.value,staffOptions.value]=await Promise.all([api.getPeople(props.project.id),loadAll('contacts'),loadAll('groups'),api.getStaff(props.project.id)])}
let loadSequence=0
const load=async()=>{const current=++loadSequence;loading.value=true;error.value='';workspace.value=null;try{const row=canWrite?await api.initialize(props.project.id):await api.getWorkspace(props.project.id);if(current!==loadSequence)return;workspace.value=row;if(row)await refreshContext();languages.value=await getProjectLanguages()}catch(e){if(current===loadSequence)error.value=message(e)}finally{if(current===loadSequence)loading.value=false}}
const reload=async()=>{await refreshContext();await listRef.value?.reload()}
const contactColumns=[{key:'person.resource_code',label:'资源编号'},{key:'person.full_name',label:'人才姓名'},{key:'willingness',label:'项目意愿',filter:{label:'项目意愿',type:'select',options:willingnessOptions},format:row=>optionLabel(willingnessOptions,row.willingness)},{key:'response',label:'联系回复',format:row=>optionLabel(responseOptions,row.data.response_status||'not_contacted')},{key:'data.quote',label:'项目报价'},{key:'person.region',label:'人才所在地',default:false},{key:'accent',label:'语言与口音',format:row=>(row.person?.language_skills||[]).map(skill=>`${skill.label}：${skill.accent||'-'}`).join('；')},{key:'data.reason',label:'原因/心理价位',default:false},{key:'data.remarks',label:'备注',default:false}]
const groupColumns=[{key:'name',label:'分组名称'},{key:'members',label:'当前成员',format:row=>names([row.members?.person1_id,row.members?.person2_id])},{key:'version',label:'成员版本',format:row=>row.members?.version},{key:'archived',label:'分组状态',format:row=>row.archived?'已归档':'有效'},{key:'created_at',label:'建立时间',format:row=>formatBusinessDateTime(row.created_at),default:false}]
const taskColumns=[{key:'name',label:'任务/批次名称'},{key:'group',label:'来源分组',format:row=>groupName(row.group_id)},{key:'person_ids',label:'任务人员',format:row=>names(row.person_ids)},{key:'status',label:'当前状态',filter:{label:'当前状态',type:'select',options:taskStatuses},format:row=>optionLabel(taskStatuses,row.status)},{key:'data.workload',label:'工作量'},{key:'data.price',label:'价格说明',format:row=>row.latest_records?.price?.data?.price ?? row.data.price},{key:'data.method',label:'采集方式',default:false},{key:'data.content',label:'任务内容',default:false},{key:'data.personal_prices',label:'个人价格',default:false},{key:'data.remarks',label:'备注',default:false},...recordKinds.map(kind=>({key:'latest_'+kind.value,label:'最近'+kind.label,default:kind.value==='progress',format:row=>latestText(row,kind.value)}))]
const latestText=(row,kind)=>{const record=row.latest_records?.[kind];return record?[record.title,record.data.price,record.data.planned_progress,record.data.result,record.data.planned_start?formatBusinessDateTime(record.data.planned_start):''].filter(Boolean).join('；'):'-'}
const columns=computed(()=>tab.value==='contacts'?contactColumns:tab.value==='groups'?groupColumns:taskColumns)
const cell=(row,column)=>{const value=column.format?column.format(row):column.key.split('.').reduce((value,key)=>value?.[key],row);return value==null||value===''?'-':value}
const details=row=>row.person_id?[{label:'来源',value:(row.data?.sources||[]).join('；')},{label:'时间安排',value:(row.data?.availability||[]).map(item=>`${({weekday:'工作日',weekend:'周末',date:'具体日期',exception:'例外日期'})[item.type]} ${item.date||''} ${item.time||''}`).join('\n')},{label:'渠道状态',value:(row.data?.channel_states||[]).map(item=>`${optionLabel(channelOptions,item.channel)} / ${item.target} / ${item.status}`).join('\n')},{label:'原因/心理价位',value:row.data?.reason},{label:'备注',value:row.data?.remarks}]:[{label:'成员历史版本',value:row.members_version},{label:'来源采集批次',value:row.source_task_name}]
const editor=reactive({visible:false,title:'',kind:'',row:null,fields:[],error:'',conflict:false}),form=reactive({})
const input=(key,label,type='text',options={})=>({key,label,type,...options})
const openEditor=(kind,title,fields,values,row=null)=>{Object.keys(form).forEach(key=>delete form[key]);Object.assign(form,values);Object.assign(editor,{kind,title,fields,row,error:'',conflict:false,visible:true})}
const editSettings=()=>openEditor('settings','联系安排与工作区设置',[input('strategy','联系策略','textarea',{wide:true}),input('moments','发圈安排','textarea'),input('posts','发帖安排','textarea'),input('handover','交接说明','textarea',{wide:true}),input('allow_multiple_groups','允许人才参与当前订单多个有效组','boolean'),input('archived','归档工作区（恢复后可继续维护）','boolean')],{...workspace.value.notes,allow_multiple_groups:workspace.value.allow_multiple_groups,archived:workspace.value.archived},workspace.value)
const editContact=row=>openEditor('contacts','编辑项目联系人',[input('name','人才姓名','readonly'),input('willingness','项目参与意愿','select',{required:true,options:willingnessOptions}),input('quote','项目报价（自由填写）'),input('reason','原因、可参与时间或心理价位','textarea',{required:value=>['no_time','declined','this_time_declined','no_pair','price_low'].includes(value.willingness)}),input('remarks','备注','textarea',{wide:true})],{name:row.person.full_name,willingness:row.willingness,quote:row.data.quote||'',reason:row.data.reason||'',remarks:row.data.remarks||'',availability:clone(row.data.availability||[]),channel_states:clone(row.data.channel_states||[]),language_skills:clone(row.person.language_skills||[])},row)
const editGroup=row=>openEditor('groups',row?'调整分组':'新增分组',[input('name','分组名称','text',{required:true}),input('person1_id','第一位采集员','select',{required:true,options:peopleOptions.value.filter(option=>contacts.value.some(item=>item.person_id===option.value))}),input('person2_id','第二位采集员','select',{required:true,options:peopleOptions.value.filter(option=>contacts.value.some(item=>item.person_id===option.value))}),input('reason','调整、退出或恢复原因','textarea',{wide:true}),input('archived','归档分组','boolean')],{name:row?.name||`分组${groups.value.length+1}`,person1_id:row?.members.person1_id||'',person2_id:row?.members.person2_id||'',reason:'',archived:row?.archived||false,request_key:row?.request_key||crypto.randomUUID()},row)
const editTask=row=>openEditor('tasks',row?'编辑任务':'新增采集批次',[input('name','任务/批次名称','text',{required:true}),...(row?[]:[input('group_id','分组','select',{required:true,options:groups.value.filter(item=>!item.archived).map(item=>({value:item.id,label:item.name}))})]),input('status','当前状态','select',{options:taskStatuses,required:true}),...(row?.stage==='annotation'?[input('person_ids','标注人员','select',{options:peopleOptions.value,multiple:true,required:true})]:[]),input('content','任务内容','textarea',{wide:true}),input('workload','工作量（自由填写）'),input('price','组价/任务价格（自由填写）'),input('personal_prices','个人价格说明','textarea'),...(row?.stage==='annotation'?[]:[input('method','采集方式','select',{options:[{value:'平台',label:'平台'},{value:'线下',label:'线下'},{value:'平台及线下',label:'平台及线下'}]})]),input('exit_reason','退出原因','textarea',{when:values=>values.status==='withdrawn',required:true}),input('remarks','备注','textarea',{wide:true})],{name:row?.name||'',status:row?.status||'pending',person_ids:row?.person_ids||[],group_id:row?.group_id||'',request_key:row?.request_key||crypto.randomUUID(),...row?.data},row)
const addFollowUp=row=>openEditor('follow','新增联系跟进',[input('channel','跟进方式','select',{options:followChannels,required:true}),input('contact_date','实际联系日期','date',{required:true}),input('response_status','本次联系回复情况','select',{required:true,options:responseOptions.filter(option=>option.value!=='not_contacted')}),input('content','联系内容、追问情况','textarea',{wide:true,required:true})],{channel:'message',response_status:'no_response',contact_date:businessDateTimeInputValue().slice(0,10),content:''},row)
const duplicates=ref([])
const newTalent=()=>{duplicates.value=[];openEditor('talent','新增人才/搭档',[input('full_name','姓名','text',{required:true}),...(isSuperAdmin()?[input('primary_phone','手机'),input('primary_email','邮箱'),input('wechat','微信')]:[]),input('referral_person_id','谁的搭档（选填）','select',{options:peopleOptions.value}),input('language_id','语言/方言','select',{options:languages.value.map(item=>({value:item.id,label:item.label}))}),input('accent','该语言口音'),input('remarks','备注','textarea')],{full_name:'',primary_phone:'',primary_email:'',wechat:'',referral_person_id:null,language_id:null,accent:'',remarks:'',allow_duplicate:false,request_key:crypto.randomUUID()})}
const linkDuplicate=async person=>{try{await api.save(props.project.id,'contacts',null,{person_id:person.id,data:{sources:['新增查重后关联']}});editor.visible=false;await reload()}catch(e){editor.error=message(e)}}
const updateAccent=async skill=>{try{const original=editor.row.person.language_skills.find(item=>item.id===skill.id);await api.saveAccent(props.project.id,editor.row.person_id,skill.id,{accent:skill.accent,expected_accent:original?.accent||''});original.accent=skill.accent;ElMessage.success('口音已同步到人才总库')}catch(e){ElMessage.error(message(e))}}

const candidatesVisible=ref(false),candidates=ref([]),candidateSelection=ref([]),candidateTable=ref(),candidateLoading=ref(false),candidateTotal=ref(0),ratio=ref(100),dailyNew=ref([]),groupStatistics=ref(null),candidateQuery=reactive({keyword:'',language_id:'',channel:'',company_account:'',added_date:''})
let candidateController,candidateSequence=0,candidateTimer
const openCandidates=()=>{candidatesVisible.value=true;loadCandidates()}
const resetCandidates=()=>{Object.keys(candidateQuery).forEach(key=>candidateQuery[key]='');loadCandidates()}
const scheduleCandidates=()=>{clearTimeout(candidateTimer);if(!candidateQuery.keyword&&!candidateQuery.company_account)loadCandidates();else candidateTimer=setTimeout(loadCandidates,400)}
const loadCandidates=async()=>{clearTimeout(candidateTimer);candidateController?.abort();candidateController=new AbortController();const current=++candidateSequence;candidateLoading.value=true;candidateSelection.value=[];try{const params=Object.fromEntries(Object.entries(candidateQuery).filter(([,value])=>value));const rows=[];let total=1;while(rows.length<total){const page=await api.getCandidates(props.project.id,{...params,only_new:false,skip:rows.length,limit:500},candidateController.signal);if(current!==candidateSequence)return;rows.push(...page.items);total=page.total;dailyNew.value=page.daily_new;groupStatistics.value=page.group_statistics;if(!page.items.length)break}candidates.value=rows;candidateTotal.value=total}catch(e){if(e.code!=='ERR_CANCELED')ElMessage.error(message(e))}finally{if(current===candidateSequence)candidateLoading.value=false}}
const applyRatio=async()=>{candidateTable.value?.clearSelection();await nextTick();selectCandidateRatio(candidates.value,ratio.value).forEach(row=>candidateTable.value?.toggleRowSelection(row,true))}
const copyCandidates=async()=>{const lines=candidateSelection.value.map(row=>`${row.resource_code||'-'}\t${row.full_name}\t${row.wechat||''}\t${row.phone||''}\t${row.email||''}`);if(!lines.length)return ElMessage.warning('请先选择人才');try{await navigator.clipboard.writeText(lines.join('\n'));ElMessage.success('已复制当前有权查看的联系资料')}catch{ElMessage.error('浏览器未允许复制，请检查剪贴板权限')}}
const joinCandidates=async()=>{saving.value=true;const failures=[];for(const row of [...candidateSelection.value]){try{await api.save(props.project.id,'contacts',null,{person_id:row.id,data:{sources:[optionLabel(channelOptions,candidateQuery.channel),...(row.company_accounts||[]),...row.added_sources.map(item=>`${item.date} ${item.channel}`)]}});row.joined=true}catch(e){failures.push(row.full_name+'：'+message(e))}}saving.value=false;await reload();if(failures.length)ElMessage.error(failures.join('；'));else ElMessage.success('已加入联系表');await loadCandidates()}

const recordsVisible=ref(false),activeTask=ref(),records=ref([]),recordKind=ref('progress')
const visibleRecords=computed(()=>records.value.filter(row=>row.kind===recordKind.value))
const refreshRecords=async()=>{try{records.value=await api.getRecords(props.project.id,activeTask.value.id)}catch(e){ElMessage.error(message(e))}}
const openRecords=async row=>{activeTask.value=row;recordsVisible.value=true;await refreshRecords()}
const useCollectionAccounts=async()=>{try{const source=await api.getRecords(props.project.id,activeTask.value.source_task_id);const latest=source.filter(item=>item.kind==='account').sort((a,b)=>new Date(b.updated_at)-new Date(a.updated_at))[0];if(!latest)return ElMessage.warning('来源采集批次尚未登记账号引用');await editRecord();form.account_ids=[...(latest.data.account_ids||[])];form.content='引用来源采集批次账号；如标注人员已更换，需先在账号管理中重新分配。'}catch(e){ElMessage.error(message(e))}}
const recordSummary=row=>[row.data.price,row.data.planned_progress,row.data.actual_progress,row.data.result,row.data.content,row.data.inserted?'插入':'',row.data.postponed?'顺延':''].filter(Boolean).join('；')||'-'
const recordLabels={content:'计划内容/说明',price:'价格说明',planned_progress:'预计完成进度',actual_progress:'实际完成进度',planned_start:'预计开始时间',planned_end:'预计完成/客户要求时间',actual_start:'实际开始时间',actual_end:'实际完成时间',duration_adjustment_minutes:'耗时调整（分钟）',adjustment_reason:'调整原因',trainer:'预定讲师/负责人',actual_trainer:'实际讲师/检查人',actual_content:'实际内容',skipped:'未进行',reason:'原因',result:'结果/通过情况',client_feedback:'客户返修意见',communicated:'已与人员沟通',inserted:'插入节点',postponed:'顺延节点',account_ids:'引用账号'}
const recordDetails=row=>[...Object.entries(row.data).filter(([,value])=>value!==''&&value!=null&&value!==false).map(([key,value])=>({label:recordLabels[key]||key,value:key.endsWith('_start')||key.endsWith('_end')?formatBusinessDateTime(value):typeof value==='boolean'?(value?'是':'否'):Array.isArray(value)?value.join('、'):String(value)})),{label:'实际耗时',value:pairedDuration(row.data)==null?'-':pairedDuration(row.data)+'分钟'}]
let recordInsertAfter=null
const editRecord=async(row,insertAfter=null)=>{recordInsertAfter=insertAfter;const kind=row?.kind||recordKind.value;let accounts=[];if(kind==='account'){if(!canAccounts)return ElMessage.warning('需要账号查看权限');const page=await ops.getAccounts({projectId:props.project.id,limit:500});accounts=page.map(item=>({value:item.id,label:`${item.platformName||'平台'} · ${item.personName||'未分配'} · ${item.nickname||'账号'}`}))}const types=['progress','training','trial','inspection','repair'];openEditor('record',row?'编辑'+optionLabel(recordKinds,kind):'新增'+optionLabel(recordKinds,kind),[
  input('title','记录名称','text',{required:true}),input('person_ids','关联实际人员','select',{multiple:true,required:true,options:peopleOptions.value.filter(option=>activeTask.value.person_ids.includes(option.value))}),
  ...(kind==='price'?[input('price','价格说明（自由填写）','textarea',{wide:true})]:[]),
  ...(kind==='account'?[input('account_ids','引用已分配给任务人员的账号','select',{multiple:true,options:accounts}),input('content','账号用途/备注','textarea',{wide:true})]:[input('content',kind==='training'?'预定培训内容':'内容说明','textarea',{wide:true})]),
  ...(types.includes(kind)?[input('planned_start','预计开始时间','datetime'),input('planned_end',kind==='repair'?'客户要求返修完成时间':'预计完成时间','datetime'),input('actual_start','实际开始时间','datetime'),input('actual_end','实际完成时间','datetime')]:[]),
  ...(kind==='progress'?[input('planned_progress','预计完成进度（自由填写）','textarea'),input('actual_progress','实际完成进度（自由填写）','textarea'),input('duration_adjustment_minutes','实际耗时调整（分钟）','number'),input('adjustment_reason','人工调整耗时原因','textarea',{when:value=>Boolean(value.duration_adjustment_minutes),required:true})]:[]),
  ...(kind==='training'?[input('trainer','预定培训讲师','select',{options:staffOptions.value}),input('actual_trainer','实际培训讲师','select',{options:staffOptions.value}),input('actual_content','实际培训内容','textarea',{wide:true}),input('skipped','未进行培训','boolean'),input('reason','未培训原因','textarea',{when:value=>value.skipped,required:true})]:[]),
  ...(['trial','inspection'].includes(kind)?[input('actual_trainer','检查人'),input('result','考核/质检结果与备注','textarea',{wide:true})]:[]),
  ...(kind==='repair'?[input('client_feedback','客户返修意见','textarea',{wide:true}),input('communicated','已与人员沟通','boolean'),input('result','返修结果','textarea')]:[]),
  ...(kind==='performance'?[input('result','人员表现评价','textarea',{wide:true})]:[]),
],{title:row?.title||`${optionLabel(recordKinds,kind)}${visibleRecords.value.length+1}`,person_ids:row?.person_ids||activeTask.value.person_ids,request_key:row?.request_key||crypto.randomUUID(),kind,content:'',duration_adjustment_minutes:0,...row?.data},row)}
const openTransfer=async row=>{const tasks=(await loadAll('collection')).filter(item=>item.group_id===row.group_id);const targets=await loadAll('annotation');const pending=tasks.filter(item=>!targets.some(target=>target.source_task_id===item.id)&&!['withdrawn','archived'].includes(item.status));openEditor('transfer','转入标注',[input('task_ids','采集批次（选择部分即部分标注）','select',{multiple:true,required:true,options:pending.map(item=>({value:item.id,label:item.name}))}),input('person_ids','标注人员（可与采集人员不同）','select',{multiple:true,required:true,options:peopleOptions.value})],{task_ids:pending.some(item=>item.id===row.id)?[row.id]:[],person_ids:[]})}
const saveEditor=async()=>{if(saving.value)return;saving.value=true;editor.error='';editor.conflict=false;const id=props.project.id,row=editor.row;try{
  if(editor.kind==='settings'){workspace.value=await api.updateWorkspace(id,{expected_revision:row.revision,allow_multiple_groups:form.allow_multiple_groups,archived:form.archived,notes:Object.fromEntries(['strategy','moments','posts','handover'].map(key=>[key,form[key]||'']))})}
  else if(editor.kind==='contacts'){await api.save(id,'contacts',row.id,{person_id:row.person_id,expected_revision:row.revision,willingness:form.willingness,data:{...row.data,quote:form.quote,reason:form.reason,remarks:form.remarks,availability:form.availability,channel_states:form.channel_states}})}
  else if(editor.kind==='groups'){await api.save(id,'groups',row?.id,{request_key:form.request_key,name:form.name,person1_id:form.person1_id,person2_id:form.person2_id,reason:form.reason,archived:form.archived,expected_revision:row?.revision})}
  else if(editor.kind==='tasks'){await api.save(id,'tasks',row?.id,{request_key:form.request_key,name:form.name,group_id:form.group_id,status:form.status,person_ids:form.person_ids,expected_revision:row?.revision,data:Object.fromEntries(['content','workload','price','personal_prices','method','remarks','exit_reason'].map(key=>[key,form[key]||'']))})}
  else if(editor.kind==='follow'){await api.followUp(id,row.id,{expected_revision:row.revision,channel:form.channel,contact_date:form.contact_date,content:form.content,response_status:form.response_status})}
  else if(editor.kind==='talent'){const talent={full_name:form.full_name,capabilities:[{capability_type:'annotation'}],allow_duplicate:form.allow_duplicate,remarks:form.remarks,language_skills:form.language_id?[{language_id:form.language_id,role:'native',priority:1,accent:form.accent}]:[]};if(isSuperAdmin())Object.assign(talent,{primary_phone:form.primary_phone,primary_email:form.primary_email,wechat:form.wechat});await api.createTalent(id,{request_key:form.request_key,talent,referral_person_id:form.referral_person_id||null})}
  else if(editor.kind==='transfer'){await api.transfer(id,{task_ids:form.task_ids,person_ids:form.person_ids})}
  else if(editor.kind==='record'){const data=Object.fromEntries(Object.keys(recordLabels).filter(key=>key!=='account_ids'&&form[key]!==undefined).map(key=>[key,form[key]||(['planned_start','planned_end','actual_start','actual_end'].includes(key)?null:form[key])]));await api.saveRecord(id,activeTask.value.id,row?.id,{request_key:form.request_key,expected_revision:row?.revision,kind:form.kind,title:form.title,insert_after_id:recordInsertAfter,person_ids:form.person_ids,account_ids:form.account_ids||[],data});await refreshRecords()}
  editor.visible=false;ElMessage.success('已保存');await reload()
}catch(e){editor.error=message(e);editor.conflict=e.status===409||e.response?.status===409;if(e.rawDetail?.duplicates)duplicates.value=e.rawDetail.duplicates}finally{saving.value=false}}
const reloadEditor=async()=>{await reload();editor.error='最新数据已加载，当前草稿仍保留。请复制所需内容后关闭并重新打开编辑窗口。';editor.conflict=false}
const contactVisible=ref(false),activeContact=ref()
const contactDetails=row=>{activeContact.value=row;contactVisible.value=true}
const upload=async request=>{try{await api.uploadAttachment(props.project.id,activeContact.value.id,request.file);await reload();activeContact.value=contacts.value.find(item=>item.id===activeContact.value.id);request.onSuccess({});ElMessage.success('附件已上传')}catch(e){request.onError(e);ElMessage.error(message(e))}}
const download=async file=>{try{const blob=await api.downloadAttachment(props.project.id,activeContact.value.id,file.id);const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=file.name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){ElMessage.error(message(e))}}
const historyVisible=ref(false),history=ref({items:[],total:0}),historyPage=ref(1),historyEntity=ref()
const openHistory=async entityId=>{historyEntity.value=entityId;historyPage.value=1;historyVisible.value=true;await loadHistory()}
const loadHistory=async()=>{try{history.value=await api.getHistory(props.project.id,{entity_id:historyEntity.value,skip:(historyPage.value-1)*20,limit:20})}catch(e){ElMessage.error(message(e))}}
const actionLabel=action=>({initialize:'建立工作区',workspace:'工作区设置',contact:'联系资料',contact_source:'合并来源',follow_up:'联系跟进',group:'分组调整',task:'任务调整',transfer:'转入标注',record:'阶段记录',postpone:'节点顺延',delete:'删除',accent:'口音修改',attachment:'上传附件'})[action]||action
const humanSnapshot=snapshot=>{
  const labels={name:'名称',willingness:'参与意愿',status:'状态',data:'内容',content:'说明',members:'成员版本',person_id:'人才',person_ids:'实际人员',person1_id:'采集员1',person2_id:'采集员2',reason:'原因',quote:'报价',price:'价格',remarks:'备注',title:'记录名称',position:'序号',version:'成员版本',actor_name:'操作人',created_at:'记录时间',updated_at:'修改时间',kind:'记录类型',stage:'业务阶段',sources:'来源',allow_multiple_groups:'允许多组',archived:'已归档',notes:'联系安排',strategy:'联系策略',moments:'发圈安排',posts:'发帖安排',handover:'交接说明',availability:'可工作时间',channel_states:'渠道状态',channel:'渠道',target:'公司账号或群名',type:'安排类型',date:'日期',time:'时段',follow_ups:'跟进记录',contact_date:'实际联系日期',response_status:'回复情况',attachments:'附件',accent:'口音',...recordLabels}
  const hidden=new Set(['id','key','project_id','request_key','request_hash','group_id','members_id','source_task_id','task_id','actor_id','created_by','skill_id','revision'])
  const format=(value,key='')=>{
    if(value==null||value==='')return '-'
    if(key==='person_ids')return names(value)
    if(key==='account_ids')return `已关联 ${value.length} 个账号（在账号管理查看）`
    if(Array.isArray(value))return value.map(item=>format(item,key)).join('；')
    if(typeof value==='object')return Object.entries(value).filter(([name])=>!hidden.has(name)).map(([name,item])=>`${labels[name]||name}：${format(item,name)}`).join('\n')
    if(['person_id','person1_id','person2_id'].includes(key))return names([value])
    if(key==='willingness')return optionLabel(willingnessOptions,value)
    if(key==='response_status')return optionLabel(responseOptions,value)
    if(key==='status')return optionLabel(taskStatuses,value)
    if(key==='kind')return optionLabel(recordKinds,value)
    if(key==='stage')return value==='collection'?'采集':'标注'
    if(key==='channel')return optionLabel([...channelOptions,...followChannels],value)
    if(key==='type')return ({weekday:'工作日',weekend:'周末',date:'具体日期',exception:'例外日期'})[value]||value
    if(key.endsWith('_at'))return formatBusinessDateTime(value)
    return typeof value==='boolean'?(value?'是':'否'):String(value)
  }
  return format(snapshot)
}
onBeforeUnmount(()=>{clearTimeout(candidateTimer);candidateController?.abort();loadSequence++;candidateSequence++})
</script>
<style scoped>
.workspace-heading{display:flex;flex-direction:column;gap:6px}.workspace-heading strong{user-select:text;cursor:text;overflow-wrap:anywhere}.workspace-tools,.paired-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0}.paired-toolbar>.el-input,.paired-toolbar>.el-select{width:190px}.repeat-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:8px}.repeat-row .el-form-item{flex:1;min-width:150px}.pre-wrap,pre{white-space:pre-wrap;overflow-wrap:anywhere}.history-entry{padding:12px 0;border-bottom:1px solid #e2e8f0}.history-entry>span{display:block;color:#64748b;margin-top:5px}.daily-new{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px}
</style>
