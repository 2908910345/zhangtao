const STORAGE_KEY = 'recent_history'
const MAX_ITEMS = 20

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return []
}

function saveHistory(items) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)))
  } catch {}
}

export function addRecentItem(item) {
  const items = loadHistory()
  const filtered = items.filter(i => !(i.type === item.type && i.code === item.code))
  filtered.unshift({ ...item, time: Date.now() })
  saveHistory(filtered)
  return filtered
}

export function getRecentItems(type = null) {
  const items = loadHistory()
  if (type) return items.filter(i => i.type === type)
  return items
}

export function clearRecentHistory() {
  localStorage.removeItem(STORAGE_KEY)
}
