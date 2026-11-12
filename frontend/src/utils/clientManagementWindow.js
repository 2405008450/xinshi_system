import { shallowRef } from 'vue'

export const clientManagementTarget = shallowRef(null)

export function isClientShortName(label, prop) {
  return ['客户简称', '母客户简称', '子客户简称'].includes(label) ||
    ['clientShortName', 'client_short_name', 'subClientShortName', 'sub_client_short_name'].includes(prop)
}

export function clientManagementRequest(row, value, subClient = false) {
  const shortName = String(value ?? '').trim()
  if (!shortName || shortName === '-' || shortName === '—') return null

  if (row?.id && row?.parent_client_id && row?.sub_client_code) {
    return { client_id: row.parent_client_id, sub_client_id: row.id, short_name: shortName }
  }
  const clientId = row?.clientId || row?.client_id || (Array.isArray(row?.sub_clients) ? row.id : undefined)
  const subClientId = row?.subClientId || row?.sub_client_id
  const subName = String(row?.subClientShortName || row?.sub_client_short_name || '').trim()
  // Translation lists carry both names. Other project forms can display the
  // selected sub-client in the customer-short-name field itself.
  if (subClient || (subClientId && (!subName || subName === shortName))) {
    return { client_id: subClientId ? clientId : undefined, sub_client_id: subClientId, short_name: shortName }
  }
  return { client_id: clientId, short_name: shortName }
}
