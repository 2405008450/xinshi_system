<template>
  <el-table :data="rows" border row-key="id" max-height="460" empty-text="没有符合条件的人才">
    <OrderedTableColumns :settings-key="settingsKey">
      <el-table-column type="index" label="序号" width="64" :index="index => offset + index + 1" />
      <el-table-column label="匹配率" width="110"><template #default="{row}">{{ formatRegionMatchRate(row.matchRate) }}</template></el-table-column>
      <el-table-column v-for="column in columns" :key="column.key" :label="column.label" :width="column.width" show-overflow-tooltip>
        <template #default="{row}">
          <el-popover v-if="section(column.key)" trigger="click" placement="left" :width="760" :title="`${name(row)} ${column.label}`" popper-class="region-match-talent-details" @show="loadDetail(row)">
            <template #reference><el-button link type="primary">{{ cell(column,row) }}</el-button></template>
            <el-alert v-if="errors[row.id]" :title="errors[row.id]" type="error" :closable="false"><el-button link @click="loadDetail(row)">重试</el-button></el-alert>
            <TalentDetailContent v-loading="loading[row.id]" :detail="details[row.id] || row" :section="section(column.key)" />
          </el-popover>
          <TalentProjectSituationPopover v-else-if="column.key==='projectSituation'" :person-id="row.id" :person-name="name(row)" :summary="row.projectSituation" />
          <div v-else-if="column.key==='capabilityTypes'"><el-tag v-for="value in row.capabilityTypes" :key="value" size="small">{{ capabilities[value] || value }}</el-tag><span v-if="!row.capabilityTypes?.length">-</span></div>
          <el-tag v-else-if="column.key==='status'" :type="({active:'success',standby:'info',inactive:'danger'})[row.status]" size="small">{{ statuses[row.status] || row.status }}</el-tag>
          <el-tag v-else-if="column.key==='annotationWillingness' && row.annotationWillingness" size="small">{{ ({high:'高',medium:'中',low:'低'})[row.annotationWillingness] }}</el-tag>
          <SensitiveContactValue v-else-if="['primaryPhone','primaryEmail'].includes(column.key)" :value="row[column.key]" :restricted="row.contactRestricted" />
          <span v-else>{{ cell(column,row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" fixed="right" width="96">
        <template #default="{row}"><el-popover trigger="click" placement="left" :width="760" :title="`${name(row)} 详情`" popper-class="region-match-talent-details" @show="loadDetail(row,true)">
          <template #reference><el-button link type="primary">查看详情</el-button></template>
          <el-alert v-if="errors[row.id]" :title="errors[row.id]" type="error" :closable="false"><el-button link @click="loadDetail(row,true)">重试</el-button></el-alert>
          <TalentDetailContent v-loading="loading[row.id]" :detail="details[row.id] || row" :projects="projects[row.id] || []" />
        </el-popover></template>
      </el-table-column>
    </OrderedTableColumns>
  </el-table>
</template>
<script setup>
import { reactive,onBeforeUnmount } from 'vue'
import OrderedTableColumns from '@/components/common/OrderedTableColumns.vue'
import SensitiveContactValue from '@/components/common/SensitiveContactValue.vue'
import TalentDetailContent from './TalentDetailContent.vue'
import TalentProjectSituationPopover from './TalentProjectSituationPopover.vue'
import { getTalent,getTalentProjects } from '@/api/talents'
import { getTalentDisplayName } from '@/utils/talentNames'
import { talentStatusLabels } from '@/utils/talentStatus'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { formatRegionMatchRate } from '@/utils/regionMatchResults'
const props=defineProps({rows:{type:Array,required:true},columns:{type:Array,required:true},offset:{type:Number,default:0},settingsKey:{type:String,required:true}})
const name=row=>getTalentDisplayName(row,'人才')
const statuses=talentStatusLabels,capabilities={written_translation:'笔译',interpretation:'口译',annotation:'标注'}
const section=key=>({fullName:'identity',educationSummary:'education',languageSummary:'language',overallRating:'performance'})[key]
function cell(column,row){
 const value=row[column.key]
 if(column.key==='fullName')return name(row)
 if(column.type==='datetime')return formatBusinessDateTime(value)
 if(column.key==='age')return row.currentAge==null?'-':`${row.currentAge}岁`
 if(column.key==='yearsExperience')return value==null?'-':`${value}年`
 if(column.key==='employmentStatus')return ({student:'在校学生',employed:'在职',freelance:'自由职业',seeking:'待业/求职中',retired:'已退休',other:'其他'})[value]||value||'-'
 if(column.key==='overallRating')return [row.overallScore==null?'':`${row.overallScore}分`,value].filter(Boolean).join(' · ')||'-'
 if(column.key==='duplicateReviewRequired')return value?'待核重':'-'
 if(column.key==='wechatAccount')return row.wechatAccounts?.join('、')||value||'-'
 return Array.isArray(value)?value.join('、')||'-':value??'-'
}
const details=reactive({}),projects=reactive({}),loading=reactive({}),errors=reactive({})
const controllers=new Map()
async function loadDetail(row,full=false){
 if(loading[row.id])return
 if(details[row.id]&&(!full||projects[row.id]))return
 const controller=new AbortController();controllers.set(row.id,controller);loading[row.id]=true;delete errors[row.id]
 try{
  if(!details[row.id])details[row.id]=await getTalent(row.id,{signal:controller.signal})
  if(full&&!projects[row.id])projects[row.id]=await getTalentProjects(row.id,{signal:controller.signal})
 }catch(error){if(error.code!=='ERR_CANCELED')errors[row.id]=error.detail||error.message||'详情加载失败'}
 finally{loading[row.id]=false;controllers.delete(row.id)}
}
onBeforeUnmount(()=>{for(const controller of controllers.values())controller.abort()})
</script>
<style>
.region-match-talent-details{max-width:calc(100vw - 32px)}
.region-match-talent-details .talent-detail-content{max-height:560px;overflow:auto;overflow-wrap:anywhere}
</style>
