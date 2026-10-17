// 地区只描述当前订单的语言项，不参与语言方向标识与子订单拆分。
export const emptyLanguageRegion = () => ({ city: '', district: '', street: '' })

export const normalizeLanguageRegions = (regions = []) => regions
  .map(region => Object.fromEntries(['city', 'district', 'street'].map(key => [key, region[key]?.trim() || null])))
  .filter(region => region.city || region.district || region.street)

export const copyLanguageRegions = (regions = []) => regions.map(region => ({ ...emptyLanguageRegion(), ...region }))
