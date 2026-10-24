import { parseProject } from './projectContent.js'
async function get(path, fetchImpl) {
  const response = await fetchImpl(path, { cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(8000) })
  if (!response.ok) throw new Error('Project unavailable')
  return response.json()
}
export async function fetchProjects(fetchImpl = globalThis.fetch) {
  const value = await get('/api/projects', fetchImpl)
  if (!Array.isArray(value?.projects)) throw new Error('Invalid project list')
  const items = value.projects.map(parseProject)
  if (new Set(items.map(item => item.id)).size !== items.length || items.some(item => item.status !== 'published')) throw new Error('Invalid public project list')
  return items
}
export async function fetchProject(id, fetchImpl = globalThis.fetch) {
  if (!Number.isSafeInteger(id) || id < 1) throw new Error('Invalid project id')
  const value = await get('/api/projects/' + id, fetchImpl)
  const project = parseProject(value?.project)
  if (project.id !== id || project.status !== 'published') throw new Error('Project unavailable')
  return project
}
