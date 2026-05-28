import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

let currentBookName = 'default'

export function setCurrentBook(name) {
  currentBookName = name
  sessionStorage.setItem('current_book', name)
}

export function getCurrentBook() {
  if (sessionStorage.getItem('current_book')) {
    currentBookName = sessionStorage.getItem('current_book')
  }
  return currentBookName
}

export function uploadBalance(file, bookName = null) {
  const form = new FormData()
  form.append('file', file)
  const targetBook = bookName || currentBookName
  return http.post('/upload/balance', form, { params: { book_name: targetBook } })
}

export function uploadJournal(file, bookName = null) {
  const form = new FormData()
  form.append('file', file)
  const targetBook = bookName || currentBookName
  return http.post('/upload/journal', form, { params: { book_name: targetBook } })
}

export function saveToDatabase(bookName = null) {
  const targetBook = bookName || currentBookName
  return http.post('/books/save-current', null, { params: { book_name: targetBook } })
}

export function getSubjectTree() {
  return http.get('/subjects/tree', { params: { book_name: currentBookName } })
}

export function getAllSubjects() {
  return http.get('/subjects/all', { params: { book_name: currentBookName } })
}

export function getSubjectJournal(code, params = {}) {
  return http.get(`/subjects/${code}/journal`, {
    params: { ...params, book_name: currentBookName }
  })
}

export function getSubjectBalance(code) {
  return http.get(`/subjects/${code}/balance`, { params: { book_name: currentBookName } })
}

export function getSubjectDimensions(code, typeFilter) {
  const p = { book_name: currentBookName }
  if (typeFilter) p.type = typeFilter
  return http.get(`/subjects/${code}/dimensions`, { params: p })
}

export function getVoucherDetail(voucherNo, period = '') {
  const params = { book_name: currentBookName }
  if (period) params.period = period
  return http.get(`/voucher/${voucherNo}`, { params })
}

export function getStatistics() {
  return http.get('/statistics', { params: { book_name: currentBookName } })
}

export function getActiveBook() {
  return http.get('/books/active')
}

export function listBooks() {
  return http.get('/books')
}

export function createBook(name, description = '') {
  return http.post('/books', { name, description })
}

export function saveAsBook(name, description = '') {
  return http.post('/books/save-as', { name, description })
}

export function deleteBook(name) {
  return http.delete(`/books/${name}`)
}

export function switchBook(name) {
  return http.post(`/books/switch/${name}`)
}

export function clearAllData() {
  return http.delete('/data/clear', { params: { book_name: currentBookName } })
}

export function downloadBalanceTemplate() {
  return http.get('/templates/balance', { responseType: 'blob' })
}

export function downloadJournalTemplate() {
  return http.get('/templates/journal', { responseType: 'blob' })
}

export function exportBalanceDraft(params = {}) {
  return http.get('/export/draft', {
    params: { book_name: currentBookName, ...params },
    responseType: 'blob'
  })
}

// 搜索科目
export function searchSubjects(keyword) {
  return http.get('/subjects/search', { params: { keyword, book_name: currentBookName } })
}

// 审计调整分录
export function getAdjustments(bookName = null) {
  return http.get('/adjustments', { params: { book_name: bookName || currentBookName } })
}

export function createAdjustment(data, bookName = null) {
  return http.post('/adjustments', data, { params: { book_name: bookName || currentBookName } })
}

export function updateAdjustment(entryId, data) {
  return http.put(`/adjustments/${entryId}`, data)
}

export function deleteAdjustment(entryId) {
  return http.delete(`/adjustments/${entryId}`)
}

export function clearAdjustments(bookName = null) {
  return http.delete('/adjustments', { params: { book_name: bookName || currentBookName } })
}

// 试算平衡表
export function getTrialBalance(bookName = null) {
  return http.get('/trial-balance', { params: { book_name: bookName || currentBookName } })
}

// 凭证汇总
export function getVoucherBook(params = {}) {
  return http.get('/vouchers', { params: { ...params, book_name: currentBookName } })
}

// 底稿模板
export function listDraftTemplates() {
  return http.get('/draft-templates')
}

export function getDraftTemplate(code, bookName = null) {
  return http.get(`/draft-templates/${code}`, { params: { book_name: bookName || currentBookName } })
}

// 明细表
export function getDetailSchedule(code, dimensionType = '', openingSign = 'debit') {
  const params = { book_name: currentBookName, opening_sign: openingSign }
  if (dimensionType) params.dimension_type = dimensionType
  return http.get(`/draft-templates/detail/${code}`, { params })
}

export function getDetailDimensionTypes(code) {
  return http.get(`/draft-templates/detail/${code}/dimensions`, { params: { book_name: currentBookName } })
}

// 层级底稿明细表（新）
export function getDetailHierarchy(templateCode, openingSign = 'debit') {
  return http.get(`/draft-templates/${templateCode}/detail-hierarchy`, {
    params: { book_name: currentBookName, opening_sign: openingSign }
  })
}

// 底稿调整值持久化
export function getTemplateAdjustments(code, bookName = null) {
  return http.get(`/draft-templates/${code}/adjustments`, { params: { book_name: bookName || currentBookName } })
}

export function saveTemplateAdjustments(code, adjustments, bookName = null) {
  return http.put(`/draft-templates/${code}/adjustments`, { adjustments }, { params: { book_name: bookName || currentBookName } })
}

// 账套备份恢复
export function backupBook(name) {
  return http.get(`/books/${name}/backup`, { responseType: 'blob' })
}

export function restoreBook(file, name) {
  const form = new FormData()
  form.append('file', file)
  return http.post('/books/restore', form, { params: { name } })
}

export default http