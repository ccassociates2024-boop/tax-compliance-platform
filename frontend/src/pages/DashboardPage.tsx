import { useQuery } from '@tanstack/react-query'
import { clientsAPI } from '../api/client'
import { Users, FileText, Receipt, Calculator, TrendingUp, AlertCircle, Clock, CheckCircle2 } from 'lucide-react'

const DEADLINES = [
  { label: 'GSTR-1 (Monthly)', date: '11 Jun 2025', type: 'GST', urgent: false },
  { label: 'TDS Q4 Return (26Q)', date: '31 May 2025', type: 'TDS', urgent: true },
  { label: 'Advance Tax (1st Installment)', date: '15 Jun 2025', type: 'IT', urgent: false },
  { label: 'GSTR-3B (Monthly)', date: '20 Jun 2025', type: 'GST', urgent: false },
  { label: 'Form 16 Issue Deadline', date: '15 Jun 2025', type: 'TDS', urgent: false },
]

const typeColors: Record<string, string> = {
  GST: 'bg-emerald-100 text-emerald-700',
  TDS: 'bg-purple-100 text-purple-700',
  IT: 'bg-blue-100 text-blue-700',
}

export default function DashboardPage() {
  const { data: clientsData } = useQuery({
    queryKey: ['clients', 'summary'],
    queryFn: () => clientsAPI.list({ per_page: 1 }),
  })

  const totalClients = clientsData?.data?.total || 0

  const stats = [
    { label: 'Total Clients', value: totalClients, icon: Users, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Pending ITR', value: 24, icon: FileText, color: 'text-orange-600', bg: 'bg-orange-50' },
    { label: 'Pending GST', value: 18, icon: Receipt, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'TDS Defaults', value: 3, icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-50' },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">FY 2024-25 Overview</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-gray-500 font-medium">{label}</p>
              <div className={`${bg} rounded-lg p-2`}>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
            </div>
            <p className="text-3xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Compliance Calendar */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-gray-500" />
            <h2 className="font-semibold text-gray-900">Upcoming Deadlines</h2>
          </div>
          <div className="space-y-3">
            {DEADLINES.map((d) => (
              <div
                key={d.label}
                className={`flex items-center justify-between p-3 rounded-lg ${
                  d.urgent ? 'bg-red-50 border border-red-200' : 'bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-3">
                  {d.urgent ? (
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-900">{d.label}</p>
                    <p className="text-xs text-gray-500">{d.date}</p>
                  </div>
                </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${typeColors[d.type]}`}>
                  {d.type}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="space-y-2">
            {[
              { label: 'Add New Client', href: '/clients', color: 'bg-blue-600 hover:bg-blue-700' },
              { label: 'Fetch IT Data', href: '/income-tax', color: 'bg-emerald-600 hover:bg-emerald-700' },
              { label: 'Upload GST Invoices', href: '/gst', color: 'bg-purple-600 hover:bg-purple-700' },
              { label: 'AI Tax Analysis', href: '/ai-assistant', color: 'bg-orange-600 hover:bg-orange-700' },
            ].map(({ label, href, color }) => (
              <a
                key={label}
                href={href}
                className={`block w-full text-center text-white text-sm font-medium py-2.5 px-4 rounded-lg transition-colors ${color}`}
              >
                {label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
