import { CheckCircle2, TrendingDown } from 'lucide-react'

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
}

interface TaxComputation {
  regime: string
  gross_total_income: number
  total_deductions: number
  taxable_income: number
  basic_tax: number
  surcharge: number
  health_edu_cess: number
  total_tax_liability: number
  rebate_87a: number
  net_tax_payable: number
  advance_tax_paid: number
  tds_credit: number
  self_assessment_tax: number
  total_tax_paid: number
  tax_payable_refundable: number
  deductions_breakdown: Record<string, any>
}

interface Props {
  old: TaxComputation
  new_: TaxComputation
  comparison: { recommended_regime: string; savings: number; recommendation_reason: string }
}

function RegimeColumn({ tc, recommended }: { tc: TaxComputation; recommended: boolean }) {
  const isNew = tc.regime === 'new'
  const payable = tc.tax_payable_refundable

  return (
    <div className={`flex-1 rounded-xl border-2 p-5 ${recommended
      ? 'border-emerald-400 bg-emerald-50'
      : 'border-gray-200 bg-white'}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-gray-900">
          {isNew ? 'New Regime' : 'Old Regime'}
          <span className="text-xs font-normal text-gray-500 ml-1">
            {isNew ? '(115BAC)' : '(with deductions)'}
          </span>
        </h3>
        {recommended && (
          <span className="flex items-center gap-1 text-xs text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-medium">
            <CheckCircle2 className="w-3 h-3" /> Recommended
          </span>
        )}
      </div>

      <div className="space-y-2 text-sm">
        <Row label="Gross Total Income" val={tc.gross_total_income} />
        <Row label="Total Deductions" val={tc.total_deductions} negative />
        <Row label="Taxable Income" val={tc.taxable_income} bold />
        <div className="border-t my-2" />
        <Row label="Basic Tax (Slab)" val={tc.basic_tax} />
        {tc.surcharge > 0 && <Row label="Surcharge" val={tc.surcharge} />}
        <Row label="Health & Education Cess (4%)" val={tc.health_edu_cess} />
        <Row label="Total Tax Liability" val={tc.total_tax_liability} bold />
        {tc.rebate_87a > 0 && <Row label="Rebate u/s 87A" val={tc.rebate_87a} negative />}
        <Row label="Net Tax Payable" val={tc.net_tax_payable} bold blue />
        <div className="border-t my-2" />
        <Row label="Advance Tax Paid" val={tc.advance_tax_paid} negative />
        <Row label="TDS Credit" val={tc.tds_credit} negative />
        {tc.self_assessment_tax > 0 && <Row label="Self Assessment Tax" val={tc.self_assessment_tax} negative />}
        <div className="border-t pt-2">
          <div className="flex justify-between font-bold text-base">
            <span>{payable >= 0 ? 'Tax Payable' : 'Refund'}</span>
            <span className={payable < 0 ? 'text-emerald-600' : 'text-red-600'}>
              {payable < 0 ? '₹' + fmt(Math.abs(payable)) + ' ↩' : '₹' + fmt(payable)}
            </span>
          </div>
        </div>
      </div>

      {/* Deduction breakdown */}
      {Object.keys(tc.deductions_breakdown).length > 0 && (
        <details className="mt-4">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
            View deduction breakdown
          </summary>
          <div className="mt-2 space-y-1">
            {Object.entries(tc.deductions_breakdown).map(([k, v]) =>
              k === 'NOTE' ? (
                <p key={k} className="text-xs text-amber-700 bg-amber-50 rounded p-2 mt-1">{v as string}</p>
              ) : (
                <div key={k} className="flex justify-between text-xs text-gray-600">
                  <span>{k}</span>
                  <span className="font-mono">₹{fmt(v as number)}</span>
                </div>
              )
            )}
          </div>
        </details>
      )}
    </div>
  )
}

function Row({ label, val, negative = false, bold = false, blue = false }:
  { label: string; val: number; negative?: boolean; bold?: boolean; blue?: boolean }) {
  if (val === 0) return null
  return (
    <div className={`flex justify-between ${bold ? 'font-semibold' : ''}`}>
      <span className="text-gray-600">{label}</span>
      <span className={`font-mono ${blue ? 'text-blue-700' : 'text-gray-900'}`}>
        {negative ? '(₹' + fmt(val) + ')' : '₹' + fmt(val)}
      </span>
    </div>
  )
}

export default function RegimeComparisonCard({ old, new_, comparison }: Props) {
  const oldRecommended = comparison.recommended_regime === 'old'
  const newRecommended = comparison.recommended_regime === 'new'

  return (
    <div className="space-y-3">
      {/* Recommendation Banner */}
      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl p-4">
        <TrendingDown className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-blue-900">
            {comparison.recommended_regime === 'new' ? 'New Regime' : 'Old Regime'} saves ₹{fmt(comparison.savings)}
          </p>
          <p className="text-xs text-blue-700 mt-0.5">{comparison.recommendation_reason}</p>
        </div>
      </div>

      {/* Side-by-side comparison */}
      <div className="flex gap-4">
        <RegimeColumn tc={old} recommended={oldRecommended} />
        <RegimeColumn tc={new_} recommended={newRecommended} />
      </div>
    </div>
  )
}
