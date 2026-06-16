import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clientsAPI } from '../api/client'
import { ArrowLeft, User, Building2, FileText, BadgeIndianRupee } from 'lucide-react'

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['client', id],
    queryFn: () => clientsAPI.get(id!),
    enabled: !!id,
  })

  const client = data?.data

  if (isLoading) return (
    <div className="p-6 flex items-center justify-center h-64">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
    </div>
  )

  if (!client) return (
    <div className="p-6 text-gray-500">Client not found.</div>
  )

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <button
        onClick={() => navigate('/clients')}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Clients
      </button>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <User className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{client.name}</h1>
              <p className="text-sm text-gray-500">{client.client_type?.toUpperCase()} · {client.pan}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate(`/income-tax/${id}`)}
              className="flex items-center gap-1.5 text-sm bg-blue-50 text-blue-700 border border-blue-200 px-3 py-2 rounded-lg hover:bg-blue-100"
            >
              <BadgeIndianRupee className="w-4 h-4" /> Income Tax
            </button>
            <button
              onClick={() => navigate(`/gst/${id}`)}
              className="flex items-center gap-1.5 text-sm bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-2 rounded-lg hover:bg-emerald-100"
            >
              <FileText className="w-4 h-4" /> GST
            </button>
            <button
              onClick={() => navigate(`/tds/${id}`)}
              className="flex items-center gap-1.5 text-sm bg-violet-50 text-violet-700 border border-violet-200 px-3 py-2 rounded-lg hover:bg-violet-100"
            >
              <Building2 className="w-4 h-4" /> TDS
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 text-sm">
          {[
            ['PAN', client.pan],
            ['GSTIN', client.gstin || '—'],
            ['TAN', client.tan || '—'],
            ['Email', client.email || '—'],
            ['Mobile', client.mobile || '—'],
            ['AY / FY', client.assessment_year || '2025-26'],
          ].map(([label, val]) => (
            <div key={label} className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-0.5">{label}</p>
              <p className="font-medium text-gray-800 font-mono">{val}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
