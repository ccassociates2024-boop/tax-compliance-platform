import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { clientsAPI } from '../api/client'
import {
  Users, Plus, Search, FileText, Receipt, Calculator,
  ChevronRight, Tag, Loader2
} from 'lucide-react'

export default function ClientsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['clients', search, page],
    queryFn: () => clientsAPI.list({ search, page, per_page: 20 }),
    placeholderData: (prev) => prev,
  })

  const clients = data?.data?.clients || []
  const total = data?.data?.total || 0

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
          <p className="text-gray-500 text-sm mt-0.5">{total} total clients</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Client
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          placeholder="Search by name, PAN, or GSTIN..."
          className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-5 py-3">Client</th>
              <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">PAN</th>
              <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">GSTIN</th>
              <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">Type</th>
              <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">Services</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="text-center py-12">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400 mx-auto" />
                </td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-12 text-gray-400 text-sm">
                  No clients found
                </td>
              </tr>
            ) : (
              clients.map((c: any) => (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/clients/${c.id}`)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 text-sm font-bold">
                        {c.full_name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{c.full_name}</p>
                        {c.tags?.length > 0 && (
                          <div className="flex gap-1 mt-0.5">
                            {c.tags.slice(0, 2).map((tag: string) => (
                              <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="font-mono text-sm text-gray-700">{c.pan}</span>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="font-mono text-xs text-gray-500">{c.gstin || '—'}</span>
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded-full font-medium capitalize">
                      {c.client_type}
                    </span>
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex gap-1.5">
                      <span title="Income Tax"><FileText className="w-4 h-4 text-blue-500" /></span>
                      {c.gst_registered && <span title="GST"><Receipt className="w-4 h-4 text-emerald-500" /></span>}
                      {c.is_tds_deductor && <span title="TDS"><Calculator className="w-4 h-4 text-purple-500" /></span>}
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={page * 20 >= total}
              onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 text-sm border rounded-lg disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {showAddModal && <AddClientModal onClose={() => setShowAddModal(false)} onSuccess={() => { setShowAddModal(false); qc.invalidateQueries({ queryKey: ['clients'] }) }} />}
    </div>
  )
}

function AddClientModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ full_name: '', pan: '', client_type: 'individual', gstin: '', email: '', phone: '', gst_registered: false, is_tds_deductor: false })
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => clientsAPI.create(form),
    onSuccess,
    onError: (e: any) => setError(e.response?.data?.detail || 'Failed to add client'),
  })

  const f = (k: string) => (e: any) => setForm(p => ({ ...p, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Add New Client</h2>
        {error && <p className="text-sm text-red-600 mb-3 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Full Name *</label>
            <input value={form.full_name} onChange={f('full_name')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">PAN *</label>
              <input value={form.pan} onChange={f('pan')} placeholder="ABCDE1234F" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Client Type</label>
              <select value={form.client_type} onChange={f('client_type')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="individual">Individual</option>
                <option value="huf">HUF</option>
                <option value="firm">Firm</option>
                <option value="company">Company</option>
                <option value="llp">LLP</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email</label>
              <input value={form.email} onChange={f('email')} type="email" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Phone</label>
              <input value={form.phone} onChange={f('phone')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">GSTIN</label>
            <input value={form.gstin} onChange={f('gstin')} placeholder="27AABCS1429B1ZB" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono" />
          </div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" checked={form.gst_registered} onChange={f('gst_registered')} className="rounded" />
              GST Registered
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" checked={form.is_tds_deductor} onChange={f('is_tds_deductor')} className="rounded" />
              TDS Deductor
            </label>
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <button onClick={onClose} className="flex-1 border border-gray-300 text-gray-700 text-sm font-medium py-2 rounded-lg hover:bg-gray-50">Cancel</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.full_name || !form.pan}
            className="flex-1 bg-blue-600 text-white text-sm font-medium py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 flex items-center justify-center gap-2"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Add Client
          </button>
        </div>
      </div>
    </div>
  )
}
