import { getClients } from '@/api/clients'

const clientDomain = (client) => (
  [client?.field_level1, client?.field_level2].filter(Boolean).join(' / ')
)

export const flattenProjectClientOptions = (clients) => (
  (Array.isArray(clients) ? clients : []).flatMap((client) => {
    const parentOption = {
      id: client.id,
      parent_client_id: client.id,
      sub_client_id: null,
      client_short_name: client.client_short_name || '',
      client_code: client.client_code || '',
      client_name: client.client_name || '',
      client_domain: clientDomain(client),
      client_manager: client.client_manager || '',
      manager_contact: client.manager_contact || '',
      parent_client_short_name: '',
    }
    const subClientOptions = (Array.isArray(client.sub_clients) ? client.sub_clients : []).map((subClient) => ({
      id: subClient.id,
      parent_client_id: client.id,
      sub_client_id: subClient.id,
      client_short_name: subClient.client_short_name || '',
      client_code: subClient.sub_client_code || '',
      client_name: subClient.client_name || '',
      client_domain: clientDomain(subClient),
      client_manager: subClient.client_manager || client.client_manager || '',
      manager_contact: subClient.manager_contact || client.manager_contact || '',
      parent_client_short_name: client.client_short_name || '',
    }))
    return [parentOption, ...subClientOptions]
  })
)

// 与笔译项目管理一致：输入简称时远程联想母客户和子客户。
export const fetchProjectClientSuggestions = async (queryString, callback) => {
  const keyword = String(queryString || '').trim()
  try {
    const clients = await getClients({
      skip: 0,
      limit: 20,
      client_short_name: keyword || undefined,
      frequent_first: true,
    })
    callback(flattenProjectClientOptions(clients))
  } catch {
    callback([])
  }
}
