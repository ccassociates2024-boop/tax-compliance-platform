import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ─── AUTH ────────────────────────────────────────────────────────────────────

export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (data: object) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
}

// ─── CLIENTS ─────────────────────────────────────────────────────────────────

export const clientsAPI = {
  list: (params?: object) => api.get('/clients', { params }),
  create: (data: object) => api.post('/clients', data),
  get: (id: string) => api.get(`/clients/${id}`),
  update: (id: string, data: object) => api.patch(`/clients/${id}`, data),
  delete: (id: string) => api.delete(`/clients/${id}`),
}

// ─── INCOME TAX ──────────────────────────────────────────────────────────────

export const incomeTaxAPI = {
  storeCredentials: (data: object) => api.post('/income-tax/credentials', data),
  fetchData: (data: object) => api.post('/income-tax/fetch', data),
  getData: (clientId: string, fy: string) =>
    api.get(`/income-tax/data/${clientId}`, { params: { financial_year: fy } }),
  getITRFilings: (clientId: string) => api.get(`/income-tax/itr/${clientId}`),
  computeITR: (data: object) => api.post('/income-tax/compute', data),
}

// Alias used in IncomeTaxPage
export const incomeAPI = incomeTaxAPI

// ─── GST ─────────────────────────────────────────────────────────────────────

export const gstAPI = {
  storeCredentials: (data: object) => api.post('/gst/credentials', data),
  fetchData: (data: object) => api.post('/gst/fetch', data),
  uploadInvoices: (data: object) => api.post('/gst/upload-invoices', data),
  getGSTR3BWorking: (data: object) => api.post('/gst/gstr3b-working', data),
  getFilings: (clientId: string) => api.get(`/gst/filings/${clientId}`),
  reconcile: (clientId: string, period: string) =>
    api.post(`/gst/reconcile/${clientId}`, null, { params: { period } }),
}

// ─── TDS ─────────────────────────────────────────────────────────────────────

export const tdsAPI = {
  storeCredentials: (data: object) => api.post('/tds/credentials', data),
  fetchData: (data: object) => api.post('/tds/fetch', data),
  complianceCheck: (data: object) => api.post('/tds/compliance-check', data),
  getFilings: (clientId: string) => api.get(`/tds/filings/${clientId}`),
  compute234e: (data: object) => api.post('/tds/compute-234e', data),
  matchChallans: (data: object) => api.post('/tds/match-challans', data),
  rateLookup: (section: string, deducteeType: string, amount: number) =>
    api.get('/tds/rate-lookup', { params: { section, deductee_type: deducteeType, payment_amount: amount } }),
  listSections: () => api.get('/tds/sections'),
  returnDueDates: () => api.get('/tds/return-due-dates'),
  validate26Q: (data: object) => api.post('/tds/validate-26q', data),
  validatePan: (pan: string) => api.post('/tds/validate-pan', null, { params: { pan } }),
}

// ─── SUBSCRIPTIONS ───────────────────────────────────────────────────────────

export const subscriptionAPI = {
  listPlans: () => api.get('/subscriptions/plans'),
  mySubscription: () => api.get('/subscriptions/my-subscription'),
  createOrder: (data: object) => api.post('/subscriptions/create-order', data),
  createSubscription: (data: object) => api.post('/subscriptions/create-subscription', data),
  verifyPayment: (data: object) => api.post('/subscriptions/verify-payment', data),
  cancel: () => api.post('/subscriptions/cancel'),
  downgradeToFree: () => api.post('/subscriptions/downgrade-free'),
  getUsage: () => api.get('/subscriptions/usage'),
}

// ─── DEMO MODE ───────────────────────────────────────────────────────────────

export const demoAPI = {
  status: () => api.get('/demo/status'),
  login: () => api.post('/demo/login'),
  clients: () => api.get('/demo/clients'),
  itrResult: (pan: string) => api.get(`/demo/itr/${pan}`),
  gstResult: (pan: string) => api.get(`/demo/gst/${pan}`),
  tdsResult: (pan: string) => api.get(`/demo/tds/${pan}`),
  chat: (messages: object[], clientId?: string) =>
    fetch(`${BASE_URL}/api/v1/demo/ai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
      body: JSON.stringify({ messages, client_id: clientId }),
    }),
  simulatePayment: (plan: string) => api.post('/demo/payment/simulate', { plan }),
  portalFetch: (pan: string) => api.post(`/demo/portal/fetch/${pan}`),
}

// ─── AI ENGINE ────────────────────────────────────────────────────────────────

export const aiAPI = {
  // Returns a streaming response — handle in component with fetch()
  chat: (messages: object[], clientId?: string) =>
    fetch(`${BASE_URL}/api/v1/ai/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
      body: JSON.stringify({ messages, client_id: clientId }),
    }),

  analyzeITR: (clientId: string, fy: string) =>
    fetch(`${BASE_URL}/api/v1/ai/analyze-itr`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
      body: JSON.stringify({ client_id: clientId, financial_year: fy }),
    }),

  getRiskScore: (clientId: string, fy: string) =>
    api.post(`/ai/risk-score/${clientId}`, null, { params: { financial_year: fy } }),

  optimizeDeductions: (data: object) => api.post('/ai/optimize-deductions', data),
}
