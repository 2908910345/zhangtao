import { reactive } from 'vue'

const STORAGE_KEY = 'app_settings'

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return {}
}

function saveSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {}
}

const defaults = {
  showDimensionSubjects: true,
  showCounterpartSubject: false,
}

const saved = loadSettings()
const settings = reactive({ ...defaults, ...saved })

export function useSettings() {
  function updateSetting(key, value) {
    settings[key] = value
    saveSettings({ ...settings })
  }

  function resetSettings() {
    for (const key of Object.keys(defaults)) {
      settings[key] = defaults[key]
    }
    saveSettings({ ...settings })
  }

  return {
    settings,
    updateSetting,
    resetSettings,
  }
}