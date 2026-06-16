import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clientsAPI } from '../api/client'
import GSTUploadTab from '../components/gst/GSTUploadTab'
import GSTR1Tab from '../components/gst/GSTR1Tab'
import GSTR3BTab from '../components/gst/GSTR3BTab'
import ITCReconcileTab from '../components/gst/ITCReconcileTab'
import { Receipt, Upload, FileText, Calculator, GitMerge } from 'lucide-react'

const TABS = [
  { id: 'upload', label: 'Upload Invoices', icon: Upload },
  { id: 'gstr1', label: 'GSTR-1', icon: FileText },
  { id: 'gstr3b', label: 'GSTR-3B', icon: Calculator },
  { id: 'reconcile', label: 'ITC Reconciliation', icon: GitMerge },
]

export default function GSTPage() {
  const { clientId } = useParams()
  const [selectedClient, setSelectedClient] = useState(clientId || '')
  const [selectedPeriod, setSelectedPeriod] = useState(() => {
    const d = new Date()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    return `${month}${d.getFullYear()}`  // e.g. "042024"
  })
  const [activeTab, setActiveTab] = useState('upload')

  const { data: clientsData } = useQuery({
    queryKey: ['clients'],
    queryFn: () => clientsAPI.list({ per_page: 200 }),
  })
  const clients = (clientsData?.data?.clients || []).filter((c: any) => c.gst_registered)

  const selectedClientData = clients.find((c: any) => c.id === selectedClient)

  // Generate period options (last 13 months)
  const periodOptions = Array.from({ length: 13 }, (_, i) => {
    const d = new Date()
    d.setMonth(d.getMonth() - i)
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const year = d.getFullYear()
    return {
      value: `${month}${year}`,
      label: d.toLocaleString('en-IN', { month: 'long', year: 'numeric' }),
    }
  })

  return (
    <div className="flex flex-col h-full">
      {/* Header controls */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Receipt className="w-5 h-5 text-emerald-600" />
            <h1 className="text-lg font-bold text-gray-900">GST Filing</h1>
          </div>

          <div className="flex items-center gap-3 ml-auto">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Client (GST Registered)</label>
              <select
                value={selectedClient}
                onChange={(e) => setSelectedClient(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-emerald-500 min-w-[220px]"
              >
                <option value="">Select client...</option>
                {clients.map((c: any) => (
                  <option key={c.id} value={c.id}>
                    {c.full_name} — {c.gstin}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Tax Period</label>
              <select
                value={selectedPeriod}
                onChange={(e) => setSelectedPeriod(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-emerald-500"
              >
                {periodOptions.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Client info banner */}
        {selectedClientData && (
          <div className="mt-3 flex items-center gap-6 bg-emerald-50 px-4 py-2 rounded-lg text-sm">
            <span className="font-medium text-emerald-800">{selectedClientData.full_name}</span>
            <span className="text-emerald-600 font-mono text-xs">{selectedClientData.gstin}</span>
            {selectedClientData.composition_scheme && (
              <span className="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded-full font-medium">
                Composition Scheme
              </span>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="flex gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === id
                  ? 'border-emerald-600 text-emerald-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto bg-gray-50 p-6">
        {!selectedClient ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            <Receipt className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-lg font-medium">Select a GST-registered client to begin</p>
            <p className="text-sm mt-1">Only GST-registered clients are shown above</p>
          </div>
        ) : (
          <>
            {activeTab === 'upload' && (
              <GSTUploadTab clientId={selectedClient} period={selectedPeriod} gstin={selectedClientData?.gstin || ''} />
            )}
            {activeTab === 'gstr1' && (
              <GSTR1Tab clientId={selectedClient} period={selectedPeriod} />
            )}
            {activeTab === 'gstr3b' && (
              <GSTR3BTab clientId={selectedClient} period={selectedPeriod} gstin={selectedClientData?.gstin || ''} />
            )}
            {activeTab === 'reconcile' && (
              <ITCReconcileTab clientId={selectedClient} period={selectedPeriod} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
