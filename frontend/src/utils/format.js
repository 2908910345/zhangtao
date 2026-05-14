export function formatAmount(val) {
  if (val === 0 || val === undefined || val === null) return '0.00'
  return Number(val).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function parseDimensions(dimStr) {
  if (!dimStr || !dimStr.trim()) return []
  return dimStr
    .split(';')
    .map((p) => {
      const idx = p.indexOf(':')
      if (idx > 0) {
        return { type: p.substring(0, idx).trim(), value: p.substring(idx + 1).trim() }
      }
      return { type: '', value: p.trim() }
    })
    .filter((d) => d.type && d.value)
}