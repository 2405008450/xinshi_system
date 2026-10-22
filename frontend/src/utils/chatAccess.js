export function chatConversationScope(url = '') {
  const path = String(url).split('?')[0]
  const project = path.match(/\/project-chat\/(annotation\/)?([0-9a-f-]{36})\/(?:start|group|timeline|messages|history|settings)$/i)
  if (project) return { projectType: project[1] ? 'annotation' : 'translation', projectId: project[2] }
  const chat = path.match(/\/chat\/(direct|discussions)\/([0-9a-f-]{36})\/(?:group|timeline|messages|history)$/i)
  return chat ? { projectType: chat[1] === 'discussions' ? 'discussion' : 'direct', projectId: chat[2] } : null
}
