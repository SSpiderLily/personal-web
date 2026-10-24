const invalid = () => { throw new Error('Invalid statistics response') }
const count = value => Number.isSafeInteger(value) && value >= 0

function calendarDay(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return invalid()
  const milliseconds = Date.parse(`${value}T00:00:00.000Z`)
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString().slice(0, 10) !== value) return invalid()
  return milliseconds / 86400000
}

export function parseStatistics(value, expectedDays) {
  if ((expectedDays !== 7 && expectedDays !== 30) || !value || typeof value !== 'object' || Array.isArray(value) ||
      value.days !== expectedDays || value.timezone !== 'Asia/Shanghai' ||
      !count(value.website_visitors) || !Array.isArray(value.projects)) return invalid()
  if (calendarDay(value.end_date) - calendarDay(value.start_date) + 1 !== expectedDays) return invalid()
  const ids = new Set()
  const projects = Array.from(value.projects, item => {
    if (!item || typeof item !== 'object' || Array.isArray(item) || !count(item.project_id) || item.project_id === 0 || ids.has(item.project_id) ||
        typeof item.name !== 'string' || !count(item.visitors)) return invalid()
    ids.add(item.project_id)
    return { project_id: item.project_id, name: item.name, visitors: item.visitors }
  })
  return { days: value.days, timezone: value.timezone, start_date: value.start_date,
    end_date: value.end_date, website_visitors: value.website_visitors, projects }
}
