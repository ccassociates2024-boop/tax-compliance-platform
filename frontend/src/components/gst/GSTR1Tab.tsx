import { useQuery } from '@tanstack/react-query'
import { gstAPI } from '../../api/client'
import { FileText, Loader2, CheckCircle2, Clock, AlertCircle } from 'lucide-react'

interface Props { clientId: string; period: string }

export default function GSTR1Tab({ clientId, period }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['gst-filings', clientId],
    queryFn: () => gstAPI.getFilings(clientId),
    enabled: !!clientId,
  })

  const filings = data?.data || []
  const currentFiling = filings.find((f: any) => f.period === period && f.return_type === 'GSTR1')

  const statusIcon = (status: string) => {
    if (status === 'filed') return <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    if (status === 'draft') return <Clock className="w-4 h-4 text-gray-400" />
    return <AlertCircle className="w-4 h-4 text-orange-500" />
  }

  if (isLoading) return (
    <div className="flex items-center justify-center h-40">
      <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
    </div>
  )

  return (
    <div className="space-y-5 max-w-5xl">
      {/* Current period status */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">GSTR-1 Status — {period}</h3>
          {currentFiling ? (
            <div className="flex items-center gap-2 text-sm">
              {statusIcon(currentFiling.status)}
              <span className="capitalize font-medium">{currentFiling.status}</span>
              {currentFiling.arn && (
                <span className="text-gray-500 font-mono text-xs">ARN: {currentFiling.arn}</span>
              )}
            </div>
          ) : (
            <span className="text-sm text-gray-400">Not started — upload invoices first</span>
          )}
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'B2B Invoices', key: 'gstr1_b2b', icon: '🏢' },
            { label: 'B2C Invoices', key: 'gstr1_b2c_small', icon: '👤' },
            { label: 'Exports', key: 'gstr1_exp', icon: '✈️' },
            { label: 'Credit Notes', key: 'gstr1_cdnr', icon: '📋' },
          ].map(({ label, key, icon }) => {
            const count = Array.isArray(currentFiling?.[key]) ? currentFiling[key].length : 0
            return (
              <div key={key} className="bg-gray-50 rounded-lg p-4 text-center">
                <p className="text-2xl mb-1">{icon}</p>
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className="text-lg font-bold text-gray-900">{count}</p>
              </div>
            )
          })}
        </div>

        {currentFiling?.status !== 'filed' && currentFiling && (
          <div className="mt-4 flex gap-3">
            <div className="flex-1 bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-medium">Next Step: Review and File</p>
                <p className="text-xs mt-0.5">
                  Upload credentials to file GSTR-1 directly via GST portal, or download JSON to file manually.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Filing history */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4">GSTR-1 Filing History</h3>
        {filings.filter((f: any) => f.return_type === 'GSTR1').length === 0 ? (
          <div className="text-center py-10 text-gray-400">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No GSTR-1 filings yet</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                {['Period', 'Status', 'ARN', 'Filed On'].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs text-gray-500 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filings
                .filter((f: any) => f.return_type === 'GSTR1')
                .map((f: any) => (
                  <tr key={f.id} className="hover:bg-gray-50">
                    <td className="py-2.5 px-3 font-mono text-gray-700">{f.period}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        {statusIcon(f.status)}
                        <span className="capitalize text-gray-700">{f.status}</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs text-gray-500">{f.arn || '—'}</td>
                    <td className="py-2.5 px-3 text-gray-500 text-xs">
                      {f.filed_at ? new Date(f.filed_at).toLocaleDateString('en-IN') : '—'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
