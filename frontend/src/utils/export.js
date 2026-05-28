import ExcelJS from 'exceljs'

const fontNormal = { name: '微软雅黑', size: 10 }
const fontTitle = { name: '微软雅黑', size: 14, bold: true }
const fontSubtitle = { name: '微软雅黑', size: 10, color: { argb: 'FF666666' } }
const fontHeader = { name: '微软雅黑', size: 10, bold: true, color: { argb: 'FFFFFFFF' } }

const fillHeader = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4472C4' } }
const fillEven = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF2F7FB' } }

const borderStyle = {
  style: 'thin',
  color: { argb: 'FFB4C6E7' },
}
const border = {
  top: borderStyle,
  bottom: borderStyle,
  left: borderStyle,
  right: borderStyle,
}

const alignCenter = { horizontal: 'center', vertical: 'middle' }
const alignLeft = { horizontal: 'left', vertical: 'middle' }
const alignRight = { horizontal: 'right', vertical: 'middle' }

function applyStyle(cell, { font, fill, alignment, border: bdr, numFmt } = {}) {
  if (font) cell.font = font
  if (fill) cell.fill = fill
  if (alignment) cell.alignment = alignment
  if (bdr) cell.border = bdr
  if (numFmt) cell.numFmt = numFmt
}

export async function exportToExcel({
  data,
  headers,
  filename = 'export.xlsx',
  sheetName = 'Sheet1',
  title,
  subtitle,
  amountKeys = [],
}) {
  const wb = new ExcelJS.Workbook()
  wb.creator = '账套管理系统'
  wb.created = new Date()

  const ws = wb.addWorksheet(sheetName, {
    pageSetup: { orientation: 'landscape', fitToPage: true, margins: {
      left: 0.7, right: 0.7, top: 0.7, bottom: 0.7, header: 0.3, footer: 0.3,
    }},
  })

  let rowIdx = 1
  const colCount = headers.length

  if (title) {
    ws.mergeCells(1, 1, 1, colCount)
    const cell = ws.getCell(`A${rowIdx}`)
    cell.value = title
    applyStyle(cell, { font: fontTitle, alignment: { horizontal: 'center', vertical: 'middle' } })
    ws.getRow(rowIdx).height = 32
    rowIdx++
  }

  if (subtitle) {
    ws.mergeCells(rowIdx, 1, rowIdx, colCount)
    const cell = ws.getCell(`A${rowIdx}`)
    cell.value = subtitle
    applyStyle(cell, { font: fontSubtitle, alignment: { horizontal: 'center', vertical: 'middle' } })
    ws.getRow(rowIdx).height = 20
    rowIdx++
  }

  if (title || subtitle) {
    ws.addRow([])
    rowIdx++
  }

  const headerRow = ws.addRow(headers.map(h => h.label))
  ws.getRow(rowIdx).height = 24
  headers.forEach((_, ci) => {
    const cell = headerRow.getCell(ci + 1)
    applyStyle(cell, { font: fontHeader, fill: fillHeader, alignment: alignCenter, border })
  })
  rowIdx++

  data.forEach((item, ri) => {
    const row = ws.addRow(headers.map(h => {
      const val = item[h.key]
      if (h.key === 'debit' || h.key === 'credit' || amountKeys.includes(h.key)) {
        const num = Number(val)
        return isNaN(num) ? val : num
      }
      return val ?? ''
    }))
    ws.getRow(rowIdx).height = 20
    headers.forEach((h, ci) => {
      const cell = row.getCell(ci + 1)
      const isAmount = h.key === 'debit' || h.key === 'credit' || amountKeys.includes(h.key)
      applyStyle(cell, {
        font: fontNormal,
        alignment: isAmount ? alignRight : (ci === 0 ? alignCenter : alignLeft),
        border,
        fill: ri % 2 === 1 ? fillEven : undefined,
        numFmt: isAmount ? '#,##0.00' : undefined,
      })
    })
    rowIdx++
  })

  headers.forEach((h, ci) => {
    const col = ws.getColumn(ci + 1)
    const maxLen = Math.max(
      h.label.length * 2,
      ...data.map(r => {
        const v = r[h.key]
        return String(v ?? '').length
      })
    )
    col.width = Math.min(Math.max(maxLen + 4, 10), 40)
  })

  ws.autoFilter = {
    from: { row: title ? 4 : 1, column: 1 },
    to: { row: title ? 4 : 1, column: colCount },
  }

  const buf = await wb.xlsx.writeBuffer()
  const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}