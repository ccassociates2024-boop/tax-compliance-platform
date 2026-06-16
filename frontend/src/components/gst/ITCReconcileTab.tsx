import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../api/client'
import { GitMerge, Loader2, CheckCircle2, AlertCircle, XCircle, Info, Upload } from 'lucide-react'

interface Props { clientId: string; period: string }

type TabType = 'summary' | 'matched' | 'mismatched' | 'only2b' | 'onlyBooks' | 'blocked'

export default function ITCReconcileTab({ clientId, period }: Props) {
  const [purchaseJson, setPurchaseJson] = useState('')
  const [gstr2bJson, setGstr2bJson] = useState('')
  const [activeSubTab, setActiveSubTab] = useState<TabType>('summary')
  const [result, setResult] = useState<any>(null)

  const mutation = useMutation({
    mutationFn: () => {
      let books = [], gstr2b = []
      try { books = JSON.parse(purchaseJson || '[]') } catch { throw new Error('Invalid Purchase JSON') }
      try { gstr2b = JSON.parse(gstr2bJson || '[]') } catch { throw new Error('Invalid GSTR-2B JSON') }
      return api.post('/gst-data/reconcile/itc', {
        client_id: clientId, period,
        purchase_invoices: books,
        gstr2b_invoices: gstr2b,
      })
    },
    onSuccess: (res) => setResult(res.data),
  })

  const s = result?.summary

  const subTabs: { id: TabType; label: string; count: number; color: string }[] = result ? [
    { id: 'summary', label: 'Summary', count: 0, color: 'text-gray-600' },
    { id: 'matched', label: 'Matched', count: result.total_matched, color: 'text-emerald-600' },
    { id: 'mismatched', label: 'Mismatched', count: result.total_mismatched, color: 'text-orange-600' },
    { id: 'only2b', label: 'Only in 2B', count: result.total_only_in_2b, color: 'text-blue-600' },
    { id: 'onlyBooks', label: 'Only in Books', count: result.total_only_in_books, color: 'text-red-600' },
    { id: 'blocked', label: 'Blocked (17(5))', count: result.total_blocked, color: 'text-purple-600' },
  ] : []

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Input */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4">ITC Reconciliation — GSTR-2B vs Purchase Books</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Purchase Register (JSON)
              <span className="ml-2 text-xs text-gray-400 font-normal">
                [{'{'}supplier_gstin, invoice_number, invoice_date, igst, cgst, sgst{'}'}]
              </span>
            </label>
            <textarea
              value={purchaseJson}
              onChange={(e) => setPurchaseJson(e.target.value)}
              rows={8}
              placeholder='[{"supplier_gstin":"27AABCS1429B1ZB","invoice_number":"INV-001","invoice_date":"01/04/2024","taxable_value":10000,"igst":1800,"cgst":0,"sgst":0}]'
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-xs font-mono focus:ring-2 focus:ring-emerald-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              GSTR-2B Data (JSON)
              <span className="ml-2 text-xs text-gray-400 font-normal">
                [{'{'}ctin, inum, idt, txval, iamt, camt, samt{'}'}]
              </span>
            </label>
            <textarea
              value={gstr2bJson}
              onChange={(e) => setGstr2bJson(e.target.value)}
              rows={8}
              placeholder='[{"ctin":"27AABCS1429B1ZB","trdnm":"ABC Pvt Ltd","inum":"INV-001","idt":"01/04/2024","val":11800,"txval":10000,"iamt":1800,"camt":0,"samt":0,"itcavl":"Yes"}]'
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-xs font-mono focus:ring-2 focus:ring-emerald-500 resize-none"
            />
          </div>
        </div>
        {mutation.error && (
          <p className="mt-2 text-sm text-red-600">{(mutation.error as Error).message}</p>
        )}
        <div className="mt-4 flex justify-end">
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || (!purchaseJson && !gstr2bJson)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-6 py-2.5 rounded-lg flex items-center gap-2 text-sm disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitMerge className="w-4 h-4" />}
            Reconcile Now
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {/* Sub-tabs */}
          <div className="border-b border-gray-200 px-5 flex gap-1 bg-gray-50">
            {subTabs.map(({ id, label, count, color }) => (
              <button
                key={id}
                onClick={() => setActiveSubTab(id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeSubTab === id
                    ? 'border-emerald-600 text-emerald-700 bg-white'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
                {count > 0 && (
                  <span className={`ml-2 text-xs font-bold ${color}`}>({count})</span>
                )}
              </button>
            ))}
          </div>

          <div className="p-5">
            {/* Summary */}
            {activeSubTab === 'summary' && s && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: 'Books IGST Total', val: s.books_igst, color: 'text-gray-900' },
                    { label: 'GSTR-2B IGST Total', val: s.gstr2b_igst, color: 'text-gray-900' },
                    { label: 'Net Difference', val: s.net_difference_igst, color: s.net_difference_igst !== 0 ? 'text-red-600' : 'text-emerald-600' },
                    { label: 'ITC Claimable (Matched)', val: s.itc_claimable_this_month_igst, color: 'text-emerald-700' },
                    { label: 'ITC Blocked u/s 17(5)', val: s.itc_blocked_sec17_5, color: 'text-red-700' },
                    { label: 'ITC Deferred (No 2B)', val: s.itc_deferred_no_2b, color: 'text-orange-700' },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="bg-gray-50 rounded-lg p-4">
                      <p className="text-xs text-gray-500 mb-1">{label}</p>
                      <p className={`text-xl font-bold ${color}`}>
                        ₹{(val || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-2">
                  <Info className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-blue-800">{s.recommendation}</p>
                </div>
              </div>
            )}

            {/* Matched */}
            {activeSubTab === 'matched' && (
              <InvoiceTable
                rows={result.matched}
                columns={['invoice_number', 'supplier_gstin', 'supplier_name', 'books_igst', '2b_igst', 'match_type']}
                icon={<CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                emptyMsg="No matched invoices"
              />
            )}

            {/* Mismatched */}
            {activeSubTab === 'mismatched' && (
              <InvoiceTable
                rows={result.mismatched}
                columns={['invoice_number', 'supplier_gstin', 'books_igst', '2b_igst', 'match_type', 'action']}
                icon={<AlertCircle className="w-4 h-4 text-orange-500" />}
                emptyMsg="No mismatched invoices"
                highlight="orange"
              />
            )}

            {/* Only in 2B */}
            {activeSubTab === 'only2b' && (
              <InvoiceTable
                rows={result.only_in_2b}
                columns={['invoice_number', 'supplier_gstin', 'supplier_name', 'igst', 'cgst', 'sgst', 'itc_availability', 'action']}
                icon={<Info className="w-4 h-4 text-blue-500" />}
                emptyMsg="All GSTR-2B invoices matched in books"
              />
            )}

            {/* Only in Books */}
            {activeSubTab === 'onlyBooks' && (
              <InvoiceTable
                rows={result.only_in_books}
                columns={['invoice_number', 'supplier_gstin', 'invoice_date', 'igst', 'cgst', 'sgst', 'risk', 'action']}
                icon={<XCircle className="w-4 h-4 text-red-500" />}
                emptyMsg="All book invoices found in GSTR-2B"
                highlight="red"
              />
            )}

            {/* Blocked */}
            {activeSubTab === 'blocked' && (
              <InvoiceTable
                rows={result.blocked_credits}
                columns={['invoice_number', 'supplier_gstin', 'hsn_sac', 'blocked_reason', 'section', 'igst_blocked', 'cgst_blocked', 'sgst_blocked']}
                icon={<XCircle className="w-4 h-4 text-purple-500" />}
                emptyMsg="No blocked credits found"
                highlight="purple"
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function InvoiceTable({ rows, columns, icon, emptyMsg, highlight }: {
  rows: any[]; columns: string[]; icon: React.ReactNode;
  emptyMsg: string; highlight?: string;
}) {
  if (!rows?.length) {
    return (
      <div className="text-center py-10 text-gray-400">
        <p className="text-sm">{emptyMsg}</p>
      </div>
    )
  }

  const bgMap: Record<string, string> = {
    orange: 'bg-orange-50', red: 'bg-red-50', purple: 'bg-purple-50',
  }
  const rowBg = highlight ? bgMap[highlight] : ''

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 text-xs text-gray-500 font-semibold w-8">#</th>
            {columns.map(col => (
              <th key={col} className="text-left py-2 px-2 text-xs text-gray-500 font-semibold capitalize">
                {col.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className={`${rowBg || 'hover:bg-gray-50'}`}>
              <td className="py-2 px-2 text-gray-400">{i + 1}</td>
              {columns.map(col => (
                <td key={col} className="py-2 px-2 text-gray-800">
                  {typeof row[col] === 'number'
                    ? `₹${row[col].toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                    : row[col] || '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
