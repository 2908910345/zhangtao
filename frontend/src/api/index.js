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

export default http