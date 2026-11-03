import {createIdempotencyKey} from './idempotency.js'
export const isChinese=value=>/^(中|简中|繁中)$|^zh|中文|汉语|简体|繁体|簡體|繁體/.test(String(value||'').replace(/\s/g,'').toLowerCase())
export function defaultRateMetric(direction){return 'customer_auto'}
export const newCustomerRate=(direction='')=>({_key:createIdempotencyKey(),languagePair:direction,amount:undefined,currency:'CNY',metric:defaultRateMetric(direction),unitSize:1})
export const ratePayload=row=>({id:row.id||null,language_pair:row.languagePair,amount:row.amount,currency:row.currency||'CNY',metric:row.metric,unit_size:row.unitSize||1,reference_id:row.referenceId||null,reference_revision:row.referenceRevision??null})
export const referenceDraft=row=>({...newCustomerRate(row.languagePair),amount:Number(row.amount),currency:row.currency,metric:row.metric,unitSize:Number(row.unitSize),referenceId:row.id,referenceRevision:row.revision})
