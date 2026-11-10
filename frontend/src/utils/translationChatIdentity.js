export function translationChatTitle(project = {}) {
  const client = String(project.clientShortName || project.clientName || '').trim()
  const name = String(project.projectName || project.sourceFileName || '').trim()
  return [client, name].filter(Boolean).join(' · ')
}
