import { Fragment, cloneVNode } from 'vue'

export function orderTableColumnNodes(nodes, definitions, order) {
  const flatten = items => items.flatMap(node => node?.type === Fragment && Array.isArray(node.children) ? flatten(node.children) : [node])
  const flat = flatten(nodes)
  const rank = new Map(order.map((key, index) => [key, index]))
  const identified = flat.map(node => {
    const attrs = node.props || {}
    if (typeof node.type === 'symbol' || ['selection', 'index', 'expand'].includes(attrs.type)) return null
    const field = definitions.find(column => [attrs['column-order-key'], attrs['column-key'], attrs.columnKey, node.key, attrs.prop, attrs.property].includes(column.key))
      || (attrs.label != null && definitions.find(column => attrs.label === column.label))
    return field ? { key: field.key, node: cloneVNode(node, { fixed: false, key: `ordered:${field.key}` }) } : null
  })
  const sorted = identified.filter(Boolean).sort((a, b) => (rank.get(a.key) ?? Infinity) - (rank.get(b.key) ?? Infinity))
  let index = 0
  return flat.map((node, position) => identified[position] ? sorted[index++].node : node)
}
