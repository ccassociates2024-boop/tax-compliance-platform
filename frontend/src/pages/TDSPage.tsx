import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { tdsAPI } from '../api/client'
import {
  Calculator, FileText, Link2, Search, AlertTriangle,
  CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, Plus, Trash2,
} from 'lucide-react'
import ClientSelector from '../components/ClientSelector'

type Tab = '234e' | 'challan' | '26q' | 'rates' | 'history'

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n)
}

// ── 234E Calculator ────────────────────────────────────────────────────────

function Calc234E() {
  const [form, setForm] = useState({
    quarter: 'Q1', return_type: '26Q',
    actual_filing_date: '', total_tds_amount: 0,
  })

  const mutation = useMutation({
    mutationFn: () => tdsAPI.compute234e(form),
  })
  const r = mutation.data?.data

  return (
    <div className="max-w-lg space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="font-semibold text-gray-900">Section 234E — Late Filing Fee</h3>
        <p className="text-xs text-gray-500">₹200/day from due date until actual filing date. Capped at TDS amount.</p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Quarter</label>
            <select value={form.quarter}
              onChange={e => setForm(f => ({ ...f, quarter: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {['Q1', 'Q2', 'Q3', 'Q4'].map(q => <option key={q}>{q}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Return Type</label>
            <select value={form.return_type}
              onChange={e => setForm(f => ({ ...f, return_type: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {['24Q', '26Q', '27Q', '27EQ'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Actual Filing Date</label>
            <input type="date" value={form.actual_filing_date}
              onChange={e => setForm(f => ({ ...f, actual_filing_date: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Total TDS in Return (₹)</label>
            <input type="number" min={0} value={form.total_tds_amount || ''}
              onChange={e => setForm(f => ({ ...f, total_tds_amount: parseFloat(e.target.value) || 0 }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>

        <button onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {mutation.isPending ? 'Computing…' : 'Compute 234E Fee'}
        </button>
      </div>

      {r && (
        <div className={`rounded-xl border p-5 ${r.applicable_fee > 0
          ? 'bg-red-50 border-red-200' : 'bg-emerald-50 border-emerald-200'}`}>
          <div className="flex items-center gap-2 mb-3">
            {r.applicable_fee > 0
              ? <AlertTriangle className="w-5 h-5 text-red-500" />
              : <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
            <h4 className="font-semibold text-gray-900">
              {r.applicable_fee > 0 ? `234E Fee: ₹${fmt(r.applicable_fee)}` : 'No 234E Fee Applicable'}
            </h4>
          </div>
          <div className="space-y-1.5 text-sm">
            {[
              ['Quarter', r.quarter],
              ['Return Type', r.return_type],
              ['Due Date', r.due_date],
              ['Filed On', r.actual_filing_date],
              ['Delay', `${r.delay_days} days`],
              ['Fee @ ₹200/day', `₹${fmt(r.total_fee_before_cap)}`],
              ['TDS Cap', `₹${fmt(r.tds_amount_cap)}`],
              ['Applicable Fee', `₹${fmt(r.applicable_fee)}`],
            ].map(([label, val]) => (
              <div key={label as string} className="flex justify-between">
                <span className="text-gray-600">{label}</span>
                <span className="font-mono font-medium text-gray-900">{val}</span>
              </div>
            ))}
          </div>
          <p className="text-xs mt-3 text-gray-600 bg-white/70 rounded-lg px-3 py-2">{r.note}</p>
        </div>
      )}
    </div>
  )
}

// ── Challan Matching ────────────────────────────────────────────────────────

function ChallanMatcher({ clientId }: { clientId: string }) {
  const emptyDed = () => ({
    deductee_name: '', deductee_pan: '', section: '194J',
    payment_date: '', payment_amount: 0, tds_deducted: 0,
    tds_deposited: 0, challan_number: '', challan_date: '', bsr_code: '',
  })
  const emptyCh = () => ({
    challan_number: '', bsr_code: '', deposit_date: '',
    amount: 0, section: '194J', period_month: 4, period_year: 2024,
  })

  const [deductions, setDeductions] = useState([emptyDed()])
  const [challans, setChallans] = useState([emptyCh()])
  const [quarter, setQuarter] = useState('Q1')

  const mutation = useMutation({
    mutationFn: () => tdsAPI.matchChallans({
      client_id: clientId, quarter,
      deductions, challans, is_government_deductor: false,
    }),
  })
  const r = mutation.data?.data

  const STATUS_STYLE: Record<string, string> = {
    matched: 'bg-emerald-100 text-emerald-800',
    unmatched: 'bg-red-100 text-red-800',
    short: 'bg-amber-100 text-amber-800',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 bg-white rounded-xl border border-gray-200 p-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Quarter</label>
          <select value={quarter} onChange={e => setQuarter(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            {['Q1', 'Q2', 'Q3', 'Q4'].map(q => <option key={q}>{q}</option>)}
          </select>
        </div>
        <button onClick={() => mutation.mutate()} disabled={!clientId || mutation.isPending}
          className="ml-auto flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          <Link2 className="w-4 h-4" />
          {mutation.isPending ? 'Matching…' : 'Match Challans'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Deductions */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-sm text-gray-800">TDS Deductions</h4>
            <button onClick={() => setDeductions(d => [...d, emptyDed()])}
              className="text-xs text-blue-600 flex items-center gap-1 hover:underline">
              <Plus className="w-3 h-3" /> Add Row
            </button>
          </div>
          <div className="space-y-3">
            {deductions.map((d, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-3 space-y-2 relative">
                <button onClick={() => setDeductions(dd => dd.filter((_, j) => j !== i))}
                  className="absolute top-2 right-2 text-gray-300 hover:text-red-500">
                  <Trash2 className="w-3 h-3" />
                </button>
                {[
                  ['deductee_name', 'Deductee Name', 'text'],
                  ['deductee_pan', 'PAN', 'text'],
                  ['payment_date', 'Payment Date', 'date'],
                  ['payment_amount', 'Payment Amount (₹)', 'number'],
                  ['tds_deducted', 'TDS Deducted (₹)', 'number'],
                  ['tds_deposited', 'TDS Deposited (₹)', 'number'],
                  ['challan_number', 'Challan No.', 'text'],
                  ['challan_date', 'Challan Date', 'date'],
                ].map(([k, label, type]) => (
                  <div key={k as string}>
                    <label className="block text-xs text-gray-400 mb-0.5">{label as string}</label>
                    <input type={type as string} value={(d as any)[k as string] || ''}
                      onChange={e => setDeductions(dd => dd.map((x, j) => j === i
                        ? { ...x, [k as string]: type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value }
                        : x))}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-xs" />
                  </div>
                ))}
                <div>
                  <label className="block text-xs text-gray-400 mb-0.5">Section</label>
                  <select value={d.section}
                    onChange={e => setDeductions(dd => dd.map((x, j) => j === i ? { ...x, section: e.target.value } : x))}
                    className="w-full border border-gray-200 rounded px-2 py-1 text-xs">
                    {['192', '194A', '194C', '194H', '194I', '194J', '194Q', '206C'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Challans */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-sm text-gray-800">Challans (ITNS 281)</h4>
            <button onClick={() => setChallans(c => [...c, emptyCh()])}
              className="text-xs text-blue-600 flex items-center gap-1 hover:underline">
              <Plus className="w-3 h-3" /> Add Row
            </button>
          </div>
          <div className="space-y-3">
            {challans.map((c, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-3 space-y-2 relative">
                <button onClick={() => setChallans(cc => cc.filter((_, j) => j !== i))}
                  className="absolute top-2 right-2 text-gray-300 hover:text-red-500">
                  <Trash2 className="w-3 h-3" />
                </button>
                {[
                  ['challan_number', 'Challan Number', 'text'],
                  ['bsr_code', 'BSR Code', 'text'],
                  ['deposit_date', 'Deposit Date', 'date'],
                  ['amount', 'Amount (₹)', 'number'],
                ].map(([k, label, type]) => (
                  <div key={k as string}>
                    <label className="block text-xs text-gray-400 mb-0.5">{label as string}</label>
                    <input type={type as string} value={(c as any)[k as string] || ''}
                      onChange={e => setChallans(cc => cc.map((x, j) => j === i
                        ? { ...x, [k as string]: type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value }
                        : x))}
                      className="w-full border border-gray-200 rounded px-2 py-1 text-xs" />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Results */}
      {r && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="grid grid-cols-4 gap-3 mb-5">
            {[
              ['Deductions', r.total_deductions, 'text-gray-800'],
              ['Matched', r.matched, 'text-emerald-600'],
              ['Unmatched', r.unmatched, 'text-red-600'],
              ['Total Interest', `₹${fmt(r.total_interest_234c)}`, 'text-orange-600'],
            ].map(([label, val, color]) => (
              <div key={label as string} className="text-center bg-gray-50 rounded-lg p-3">
                <p className={`text-lg font-bold ${color}`}>{val}</p>
                <p className="text-xs text-gray-500">{label}</p>
              </div>
            ))}
          </div>

          <table className="w-full text-xs">
            <thead>
              <tr className="border-b">
                {['Deductee', 'PAN', 'Section', 'TDS Deducted', 'TDS Deposited', 'Status', 'Delay', 'Interest', 'Remarks'].map(h => (
                  <th key={h} className="text-left py-2 px-2 text-gray-500 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {r.results.map((row: any, i: number) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="py-2 px-2">{row.deductee_name}</td>
                  <td className="py-2 px-2 font-mono">{row.deductee_pan}</td>
                  <td className="py-2 px-2">{row.section}</td>
                  <td className="py-2 px-2 font-mono text-right">₹{fmt(row.tds_deducted)}</td>
                  <td className="py-2 px-2 font-mono text-right">₹{fmt(row.tds_deposited)}</td>
                  <td className="py-2 px-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[row.status] || ''}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-center">{row.delay_days}d</td>
                  <td className={`py-2 px-2 font-mono text-right ${row.interest_234c > 0 ? 'text-red-600' : ''}`}>
                    {row.interest_234c > 0 ? `₹${fmt(row.interest_234c)}` : '—'}
                  </td>
                  <td className="py-2 px-2 text-gray-500 max-w-[200px] truncate">{row.remarks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── TDS Rate Lookup ─────────────────────────────────────────────────────────

function RateLookup() {
  const [section, setSection] = useState('194J')
  const [deducteeType, setDeducteeType] = useState('resident')
  const [amount, setAmount] = useState(0)

  const { data, refetch, isFetching } = useQuery({
    queryKey: ['tds-rate', section, deducteeType, amount],
    queryFn: () => tdsAPI.rateLookup(section, deducteeType, amount),
    enabled: false,
  })

  const { data: sectionsData } = useQuery({
    queryKey: ['tds-sections'],
    queryFn: () => tdsAPI.listSections(),
  })

  const r = data?.data
  const sections = sectionsData?.data || []

  return (
    <div className="max-w-lg space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h3 className="font-semibold text-gray-900">TDS Section & Rate Lookup</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Section</label>
            <select value={section} onChange={e => setSection(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {sections.map((s: any) => (
                <option key={s.section} value={s.section}>
                  {s.section} — {s.description}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Deductee Type</label>
            <select value={deducteeType} onChange={e => setDeducteeType(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {['resident', 'company', 'nri'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-gray-500 mb-1">Payment Amount (₹)</label>
            <input type="number" min={0} value={amount || ''}
              onChange={e => setAmount(parseFloat(e.target.value) || 0)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
        </div>
        <button onClick={() => refetch()} disabled={isFetching}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          <Search className="w-4 h-4" />
          {isFetching ? 'Looking up…' : 'Look Up Rate'}
        </button>
      </div>

      {r && (
        <div className={`bg-white rounded-xl border p-5 ${r.above_threshold ? 'border-blue-200' : 'border-gray-200'}`}>
          <div className="space-y-2 text-sm">
            {[
              ['Section', r.section],
              ['Description', r.description],
              ['TDS Rate', r.rate_percent != null ? `${r.rate_percent}%` : 'As per slab / DTAA'],
              ['Threshold', r.threshold ? `₹${fmt(r.threshold)}` : 'No threshold'],
              ['Above Threshold', r.above_threshold ? '✅ Yes — TDS applicable' : '❌ No — TDS not required'],
              r.tds_deductible != null && ['TDS Deductible', `₹${fmt(r.tds_deductible)}`],
            ].filter(Boolean).map(([label, val]) => (
              <div key={label as string} className="flex justify-between">
                <span className="text-gray-500">{label}</span>
                <span className="font-medium text-gray-900">{val}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-amber-700 mt-3 bg-amber-50 rounded-lg px-3 py-2">{r.note}</p>
        </div>
      )}
    </div>
  )
}

// ── Main Page ───────────────────────────────────────────────────────────────

export default function TDSPage() {
  const { clientId: paramId } = useParams<{ clientId?: string }>()
  const [clientId, setClientId] = useState(paramId || '')
  const [tab, setTab] = useState<Tab>('234e')

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: '234e', label: '234E — Late Fee', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'challan', label: 'Challan Matching', icon: <Link2 className="w-4 h-4" /> },
    { id: 'rates', label: 'TDS Rates', icon: <Search className="w-4 h-4" /> },
    { id: 'history', label: 'Filing History', icon: <Clock className="w-4 h-4" /> },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">TDS Compliance</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            234E calculator · Challan matching · 26Q/24Q validation · Rate lookup
          </p>
        </div>
        <ClientSelector value={clientId} onChange={setClientId} />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === t.id
                ? 'bg-white shadow-sm text-gray-900'
                : 'text-gray-500 hover:text-gray-700'
            }`}>
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === '234e' && <Calc234E />}
      {tab === 'challan' && <ChallanMatcher clientId={clientId} />}
      {tab === 'rates' && <RateLookup />}
      {tab === 'history' && <FilingHistory clientId={clientId} />}
    </div>
  )
}

// ── Filing History ──────────────────────────────────────────────────────────

function FilingHistory({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['tds-filings', clientId],
    queryFn: () => tdsAPI.getFilings(clientId),
    enabled: !!clientId,
  })

  const filings = data?.data || []

  if (!clientId) return (
    <div className="text-center text-gray-400 py-16 text-sm">Select a client to view TDS filing history.</div>
  )

  if (isLoading) return (
    <div className="flex justify-center py-16">
      <div className="animate-spin w-7 h-7 border-2 border-blue-500 border-t-transparent rounded-full" />
    </div>
  )

  if (!filings.length) return (
    <div className="text-center text-gray-400 py-16">
      <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
      <p className="text-sm">No TDS filings yet for this client.</p>
    </div>
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {['FY', 'Quarter', 'Form', 'Total TDS', 'Short Deduction', 'Status', 'Filed On'].map(h => (
              <th key={h} className="text-left py-3 px-4 text-xs text-gray-500 font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {filings.map((f: any) => (
            <tr key={f.id} className="hover:bg-gray-50">
              <td className="py-3 px-4 font-mono">{f.financial_year}</td>
              <td className="py-3 px-4">{f.quarter}</td>
              <td className="py-3 px-4 font-semibold">{f.form_type}</td>
              <td className="py-3 px-4 font-mono">₹{fmt(f.total_tds)}</td>
              <td className={`py-3 px-4 font-mono ${f.short_deduction > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                {f.short_deduction > 0 ? `₹${fmt(f.short_deduction)}` : '—'}
              </td>
              <td className="py-3 px-4">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                  f.status === 'filed' ? 'bg-emerald-100 text-emerald-800'
                  : f.status === 'draft' ? 'bg-gray-100 text-gray-600'
                  : 'bg-amber-100 text-amber-800'
                }`}>{f.status}</span>
              </td>
              <td className="py-3 px-4 text-gray-500">
                {f.filed_at ? new Date(f.filed_at).toLocaleDateString('en-IN') : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
