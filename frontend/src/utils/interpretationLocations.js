export const emptyInterpretationLocation = () => ({countryProvince:'',city:'',address:''})
export const interpretationLocationText = location => [location.countryProvince,location.city,location.address].map(value=>String(value||'').trim()).filter(Boolean).join(' ')
export const normalizeInterpretationLocations = (details, legacy=[]) => details?.length
  ? details.map(item=>({...emptyInterpretationLocation(),...item}))
  : (legacy.length?legacy:['']).map(address=>({...emptyInterpretationLocation(),address}))
export const interpretationLocationPayload = details => (details||[]).map(item=>({
  countryProvince:String(item.countryProvince||'').trim(),city:String(item.city||'').trim(),address:String(item.address||'').trim(),
})).filter(item=>interpretationLocationText(item))
