import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { incomeAPI } from '../api/client'
import {
  Calculator, TrendingDown, FileText, Lightbulb, ChevronDown, ChevronUp,
  CheckCircle2, AlertCircle, ArrowRight, BadgeIndianRupee,
} from 'lucide-react'
import ClientSelector from '../components/ClientSelector'
import RegimeComparisonCard from '../components/income_tax/RegimeComparisonCard'
import ITRFormBadge from '../components/income_tax/ITRFormBadge'
import DeductionTips from '../components/income_tax/DeductionTips'
import AdvanceTaxSchedule from '../components/income_tax/AdvanceTaxSchedule'

const SECTION_LABELS: Record<string, string> = {
  salary: 'Salary Income',
  house_property: 'House Property',
  capital_gains: 'Capital Gains',
  business: 'Business / Profession',
  other_sources: 'Other Sources',
  deductions: 'Deductions (Chapter VI-A)',
  tax_payments: 'Tax Payments & TDS',
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
}

export default function IncomeTaxPage() {
  const { clientId: routeClientId } = useParams<{ clientId: string }>()
  const [clientId, setClientId] = useState(routeClientId || '')
  const [openSection, setOpenSection] = useState<string | null>('salary')
  const [form, setForm] = useState<Record<string, any>>({
    age: 30,
    entity_type: 'individual',
    preferred_regime: 'auto',
    is_salaried: true,
    is_metro: false,
    is_self_occupied: true,
    mediclaim_self_senior: false,
    mediclaim_parents_senior: false,
    is_presumptive: false,
    presumptive_rate: 8,
  })

  const mutation = useMutation({
    mutationFn: () => incomeAPI.computeITR({ client_id: clientId, ...form }),
  })

  const result = mutation.data?.data

  function set(key: string, val: any) {
    setForm(f => ({ ...f, [key]: val }))
  }

  function num(key: string, label: string, placeholder = '0') {
    return (
      <div key={key}>
        <label className="block text-xs text-gray-500 mb-1">{label}</label>
        <input
          type="number"
          min={0}
          placeholder={placeholder}
          value={form[key] || ''}
          onChange={e => set(key, parseFloat(e.target.value) || 0)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
    )
  }

  function toggle(key: string, label: string) {
    return (
      <label key={key} className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={!!form[key]}
          onChange={e => set(key, e.target.checked)}
          className="rounded"
        />
        <span className="text-sm text-gray-700">{label}</span>
      </label>
    )
  }

  function Section({ id, children }: { id: string; children: React.ReactNode }) {
    const open = openSection === id
    return (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-5 py-4 text-left"
          onClick={() => setOpenSection(open ? null : id)}
        >
          <span className="font-semibold text-gray-800">{SECTION_LABELS[id]}</span>
          {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </button>
        {open && <div className="px-5 pb-5 border-t border-gray-100">{children}</div>}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Income Tax Computation</h1>
          <p className="text-sm text-gray-500 mt-0.5">AY 2025-26 — Old vs New Regime with deduction optimizer</p>
        </div>
        <div className="flex items-center gap-3">
          <ClientSelector value={clientId} onChange={setClientId} />
          <button
            onClick={() => mutation.mutate()}
            disabled={!clientId || mutation.isPending}
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg
                       text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            <Calculator className="w-4 h-4" />
            {mutation.isPending ? 'Computing…' : 'Compute Tax'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Input Form */}
        <div className="col-span-1 space-y-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">Income Details</p>

          {/* Taxpayer profile */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700">Taxpayer Profile</p>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Age</label>
              <input
                type="number"
                value={form.age}
                onChange={e => set('age', parseInt(e.target.value) || 30)}
                min={18} max={100}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Entity Type</label>
              <select
                value={form.entity_type}
                onChange={e => set('entity_type', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                {['individual', 'HUF', 'firm', 'company', 'trust'].map(t => (
                  <option key={t} value={t}>{t.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Preferred Regime</label>
              <select
                value={form.preferred_regime}
                onChange={e => set('preferred_regime', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="auto">Auto (Best of both)</option>
                <option value="new">New Regime (115BAC)</option>
                <option value="old">Old Regime</option>
              </select>
            </div>
          </div>

          {/* Accordion sections */}
          <Section id="salary">
            <div className="pt-4 space-y-3">
              {toggle('is_salaried', 'Salaried Employee')}
              {num('gross_salary', 'Gross Salary (₹)')}
              {num('basic_salary', 'Basic Salary (₹)')}
              {num('hra_component', 'HRA Component (₹)')}
              {num('hra_exempt', 'HRA Exempt (₹) — from Form 16')}
              {num('lta_exempt', 'LTA Exempt (₹)')}
              {num('other_exempt_allowances', 'Other Exempt Allowances (₹)')}
              {num('perquisites', 'Taxable Perquisites (₹)')}
              {num('tds_by_employer', 'TDS by Employer (₹) — from Form 16')}
            </div>
          </Section>

          <Section id="house_property">
            <div className="pt-4 space-y-3">
              {toggle('is_self_occupied', 'Self-Occupied Property')}
              {num('annual_letable_value', 'Annual Letable Value / Rent Received (₹)')}
              {num('municipal_tax_paid', 'Municipal Tax Paid (₹)')}
              {num('home_loan_interest_24b', 'Home Loan Interest u/s 24(b) (₹)')}
            </div>
          </Section>

          <Section id="capital_gains">
            <div className="pt-4 space-y-3">
              {num('stcg_111a', 'STCG on Equity/MF — Sec 111A (₹) @ 15%')}
              {num('stcg_other', 'STCG — Other Assets (₹) @ slab')}
              {num('ltcg_112a', 'LTCG on Listed Equity — Sec 112A (₹) @ 10%')}
              {num('ltcg_other', 'LTCG — Other Assets (₹) @ 20% with indexation')}
            </div>
          </Section>

          <Section id="business">
            <div className="pt-4 space-y-3">
              {toggle('is_presumptive', 'Presumptive Taxation (44AD/44ADA/44AE)')}
              {form.is_presumptive ? (
                <>
                  {num('turnover', 'Turnover / Gross Receipts (₹)')}
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Presumptive Rate (%)</label>
                    <select
                      value={form.presumptive_rate}
                      onChange={e => set('presumptive_rate', parseFloat(e.target.value))}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                    >
                      <option value={6}>6% (44AD — digital turnover)</option>
                      <option value={8}>8% (44AD — cash turnover)</option>
                      <option value={50}>50% (44ADA — professionals)</option>
                    </select>
                  </div>
                </>
              ) : (
                num('business_net_profit', 'Net Profit (₹)')
              )}
            </div>
          </Section>

          <Section id="other_sources">
            <div className="pt-4 space-y-3">
              {num('interest_savings', 'Savings Account Interest (₹)')}
              {num('interest_fd', 'FD / Other Interest (₹)')}
              {num('dividend', 'Dividend Income (₹)')}
              {num('family_pension', 'Family Pension (₹)')}
              {num('other_income', 'Other Income (₹)')}
            </div>
          </Section>

          <Section id="deductions">
            <div className="pt-4 space-y-4">
              <p className="text-xs font-semibold text-gray-400 uppercase">80C Investments (Max ₹1,50,000)</p>
              <div className="grid grid-cols-2 gap-3">
                {num('epf', 'EPF (₹)')}
                {num('ppf', 'PPF (₹)')}
                {num('elss', 'ELSS MF (₹)')}
                {num('lic_premium', 'LIC Premium (₹)')}
                {num('nsc', 'NSC (₹)')}
                {num('home_loan_principal', 'Home Loan Principal (₹)')}
                {num('tuition_fees', 'Tuition Fees (₹)')}
                {num('five_yr_fd', '5-Year FD (₹)')}
                {num('sukanya_samriddhi', 'Sukanya Samriddhi (₹)')}
                {num('other_80c', 'Other 80C (₹)')}
              </div>

              <p className="text-xs font-semibold text-gray-400 uppercase pt-2">NPS</p>
              <div className="grid grid-cols-2 gap-3">
                {num('nps_employee_80ccd1', 'NPS Employee 80CCD(1) (₹)')}
                {num('nps_additional_80ccd1b', 'NPS Additional 80CCD(1B) (₹)')}
                {num('nps_employer_80ccd2', 'NPS Employer 80CCD(2) (₹)')}
              </div>

              <p className="text-xs font-semibold text-gray-400 uppercase pt-2">80D — Medical Insurance</p>
              <div className="space-y-2">
                {num('mediclaim_self_family', 'Mediclaim — Self & Family (₹)')}
                {toggle('mediclaim_self_senior', 'Self / Spouse is Senior Citizen')}
                {num('mediclaim_parents', 'Mediclaim — Parents (₹)')}
                {toggle('mediclaim_parents_senior', 'Parents are Senior Citizens')}
                {num('preventive_health_checkup', 'Preventive Health Checkup (₹, max 5,000)')}
              </div>

              <p className="text-xs font-semibold text-gray-400 uppercase pt-2">HRA (if not from employer)</p>
              <div className="grid grid-cols-2 gap-3">
                {num('hra_received', 'HRA Received (₹)')}
                {num('basic_da_for_hra', 'Basic + DA (₹)')}
                {num('rent_paid_actual', 'Actual Rent Paid (₹)')}
                {toggle('is_metro', 'Metro City (50% basic)')}
              </div>

              <p className="text-xs font-semibold text-gray-400 uppercase pt-2">Other Deductions</p>
              <div className="grid grid-cols-2 gap-3">
                {num('education_loan_interest', '80E — Education Loan (₹)')}
                {num('donation_100_percent', '80G — 100% Donation (₹)')}
                {num('donation_50_percent', '80G — 50% Donation (₹)')}
                {num('savings_interest_80tta', '80TTA — Savings Interest (₹)')}
                {num('senior_interest_80ttb', '80TTB — Senior Interest (₹)')}
                {num('rent_paid_80gg', '80GG — Rent (if no HRA) (₹)')}
                {num('professional_tax', 'Professional Tax (₹)')}
              </div>
            </div>
          </Section>

          <Section id="tax_payments">
            <div className="pt-4 space-y-3">
              <p className="text-xs text-gray-500 font-medium">Advance Tax Paid</p>
              {num('advance_tax_q1', 'Q1 — June (₹)')}
              {num('advance_tax_q2', 'Q2 — September (₹)')}
              {num('advance_tax_q3', 'Q3 — December (₹)')}
              {num('advance_tax_q4', 'Q4 — March (₹)')}
              <p className="text-xs text-gray-500 font-medium pt-2">TDS / TCS Credit</p>
              {num('tds_26as_other', 'TDS from Form 26AS — Other (₹)')}
              {num('tcs_collected', 'TCS Collected (₹)')}
              {num('self_assessment_tax', 'Self Assessment Tax Paid (₹)')}
            </div>
          </Section>
        </div>

        {/* Right: Results */}
        <div className="col-span-2 space-y-4">
          {!result && !mutation.isPending && (
            <div className="flex flex-col items-center justify-center h-96 text-center text-gray-400">
              <Calculator className="w-12 h-12 mb-3 opacity-20" />
              <p className="text-sm">Fill in income details and click <strong>Compute Tax</strong></p>
              <p className="text-xs mt-1">Old vs New regime comparison will appear here</p>
            </div>
          )}

          {mutation.isPending && (
            <div className="flex items-center justify-center h-64 text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full" />
            </div>
          )}

          {result && (
            <>
              {/* ITR Form Badge */}
              <ITRFormBadge form={result.itr_form} reason={result.itr_form_reason} />

              {/* Income Summary */}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="font-semibold text-gray-900 mb-4">Income Head Summary</h3>
                <div className="space-y-2">
                  {[
                    ['Salary (Taxable)', result.income_summary.salary_taxable],
                    ['House Property', result.income_summary.house_property],
                    ['Business / Profession', result.income_summary.business_income],
                    ['STCG (111A @15%)', result.income_summary.stcg_111a],
                    ['STCG Other (slab)', result.income_summary.stcg_other],
                    ['LTCG (112A @10%)', result.income_summary.ltcg_112a_taxable],
                    ['LTCG Other (@20%)', result.income_summary.ltcg_other],
                    ['Other Sources', result.income_summary.other_sources],
                  ].filter(([, v]) => (v as number) !== 0).map(([label, val]) => (
                    <div key={label as string} className="flex justify-between text-sm">
                      <span className="text-gray-600">{label as string}</span>
                      <span className={`font-mono font-medium ${(val as number) < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                        {(val as number) < 0 ? '(₹' + fmt(Math.abs(val as number)) + ')' : '₹' + fmt(val as number)}
                      </span>
                    </div>
                  ))}
                  <div className="border-t pt-2 flex justify-between text-sm font-semibold">
                    <span className="text-gray-900">Gross Total Income</span>
                    <span className="font-mono text-blue-700">₹{fmt(result.income_summary.gross_total_income)}</span>
                  </div>
                </div>
              </div>

              {/* Regime Comparison */}
              <RegimeComparisonCard old={result.old_regime} new_={result.new_regime} comparison={result.comparison} />

              {/* Advance Tax Schedule */}
              <AdvanceTaxSchedule schedule={result.advance_tax_schedule} />

              {/* Deduction Optimizer */}
              <DeductionTips tips={result.deduction_optimizer_tips} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
