// 在请求新接口前确认后端支持，避免静态路径被旧版详情路由当作项目 ID。
export function supportsAnnotationGrandchildOrders(schema) {
  return Boolean(schema?.paths?.['/projects/annotation/areas']?.get &&
    schema.paths['/projects/annotation/page']?.get?.parameters?.some(parameter =>
      parameter.name === 'order_scope' &&
      (parameter.schema?.pattern?.includes('grandchild') || parameter.schema?.enum?.includes('grandchild'))))
}

export function normalizeAnnotationOrderLevel(row) {
  if (!row) return row
  return {...row, orderLevel: Number.isInteger(row.orderLevel) ? row.orderLevel : row.parentProjectId ? 1 : 0}
}

export function supportsAnnotationLanguageRegions(schema) {
  return Boolean(schema?.components?.schemas?.AnnotationLanguageItemInput?.properties?.regions)
}

export function supportsAnnotationRegionFilters(schema) {
  const fields = schema?.paths?.['/projects/annotation/page']?.get?.['x-annotation-region-filters']
  return Array.isArray(fields) && ['city','district','street'].every(field => fields.includes(field))
}
