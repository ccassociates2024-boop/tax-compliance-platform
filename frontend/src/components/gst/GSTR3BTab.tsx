import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Calculator, Loader2, AlertCircle, TrendingDown, TrendingUp, IndianRupee } from 'lucide-react'

interface Props { clientId: string; period: string; gstin: string }

const ZERO_OUTWARD = {
  taxable_igst: 0, taxable_cgst: 0, taxable_sgst: 0, taxable_cess: 0,
  taxable_value: 0, zero_rated_value: 0, zero_rated_igst: 0,
  nil_exempt_value: 0, non_gst_value: 0,
  rcm_taxable_value: 0, rcm_igst: 0, rcm_cgst: 0, rcm_sgst: 0,
}
const ZERO_ITC = {
  b2b_igst: 0, b2b_cgst: 0, b2b_sgst: 0, b2b_cess: 0,
  import_goods_igst: 0, import_services_igst: 0,
  rcm_itc_igst: 0, rcm_itc_cgst: 0, rcm_itc_sgst: 0,
  rule_42_43_igst: 0, rule_42_43_cgst: 0, rule_42_43_sgst: 0,
}

export default function GSTR3BTab({ clientId, period, gstin }: Props) {
  const [outward, setOutward] = useState(ZERO_OUTWARD)
  const [itc, setItc] = useState(ZERO_ITC)
  const [openingITC, setOpeningITC] = useState({ igst: 0, cgst: 0, sgst: 0, cess: 0 })
  const [result, setResult] = useState<any>(null)

  const mutation = useMutation({
    mutationFn: () => api.post('/gst-data/gstr3b/compute', {
      client_id: clientId, period,
      ...outward, ...itc,
      opening_igst: openingITC.igst, opening_cgst: openingITC.cgst,
      opening_sgst: openingITC.sgst, opening_cess: openingITC.cess,
    }),
    onSuccess: (res) => setResult(res.data),
  })

  const f = (setter: any, key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setter((prev: any) => ({ ...prev, [key]: parseFloat(e.target.value) || 0 }))

  const N = (v: number) => `₹${(v || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="grid grid-cols-2 gap-6">
        {/* Outward Supplies — Table 3.1 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Table 3.1 — Outward Supplies</h3>
          <div className="space-y-3">
            <Section label="3.1(a) Taxable Supplies">
              <Row label="Taxable Value" value={outward.taxable_value} onChange={f(setOutward, 'taxable_value')} />
              <Row label="IGST" value={outward.taxable_igst} onChange={f(setOutward, 'taxable_igst')} />
              <Row label="CGST" value={outward.taxable_cgst} onChange={f(setOutward, 'taxable_cgst')} />
              <Row label="SGST" value={outward.taxable_sgst} onChange={f(setOutward, 'taxable_sgst')} />
              <Row label="CESS" value={outward.taxable_cess} onChange={f(setOutward, 'taxable_cess')} />
            </Section>
            <Section label="3.1(b) Zero-rated (Exports)">
              <Row label="Taxable Value" value={outward.zero_rated_value} onChange={f(setOutward, 'zero_rated_value')} />
              <Row label="IGST" value={outward.zero_rated_igst} onChange={f(setOutward, 'zero_rated_igst')} />
            </Section>
            <Section label="3.1(c) Nil-rated / Exempt">
              <Row label="Value" value={outward.nil_exempt_value} onChange={f(setOutward, 'nil_exempt_value')} />
            </Section>
            <Section label="3.1(d) Reverse Charge (Inward)">
              <Row label="Taxable Value" value={outward.rcm_taxable_value} onChange={f(setOutward, 'rcm_taxable_value')} />
              <Row label="IGST" value={outward.rcm_igst} onChange={f(setOutward, 'rcm_igst')} />
              <Row label="CGST" value={outward.rcm_cgst} onChange={f(setOutward, 'rcm_cgst')} />
              <Row label="SGST" value={outward.rcm_sgst} onChange={f(setOutward, 'rcm_sgst')} />
            </Section>
          </div>
        </div>

        {/* ITC — Table 4 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Table 4 — ITC Available (from GSTR-2B)</h3>
          <div className="space-y-3">
            <Section label="4(A) ITC from GSTR-2B">
              <Row label="B2B IGST" value={itc.b2b_igst} onChange={f(setItc, 'b2b_igst')} />
              <Row label="B2B CGST" value={itc.b2b_cgst} onChange={f(setItc, 'b2b_cgst')} />
              <Row label="B2B SGST" value={itc.b2b_sgst} onChange={f(setItc, 'b2b_sgst')} />
              <Row label="Import Goods IGST" value={itc.import_goods_igst} onChange={f(setItc, 'import_goods_igst')} />
              <Row label="Import Services IGST" value={itc.import_services_igst} onChange={f(setItc, 'import_services_igst')} />
              <Row label="RCM IGST" value={itc.rcm_itc_igst} onChange={f(setItc, 'rcm_itc_igst')} />
              <Row label="RCM CGST" value={itc.rcm_itc_cgst} onChange={f(setItc, 'rcm_itc_cgst')} />
              <Row label="RCM SGST" value={itc.rcm_itc_sgst} onChange={f(setItc, 'rcm_itc_sgst')} />
            </Section>
            <Section label="4(B) ITC Reversed (Rule 42/43)">
              <Row label="IGST" value={itc.rule_42_43_igst} onChange={f(setItc, 'rule_42_43_igst')} />
              <Row label="CGST" value={itc.rule_42_43_cgst} onChange={f(setItc, 'rule_42_43_cgst')} />
              <Row label="SGST" value={itc.rule_42_43_sgst} onChange={f(setItc, 'rule_42_43_sgst')} />
            </Section>
            <Section label="Opening ITC Ledger Balance">
              <Row label="IGST Balance" value={openingITC.igst} onChange={(e) => setOpeningITC(p => ({ ...p, igst: parseFloat(e.target.value) || 0 }))} />
              <Row label="CGST Balance" value={openingITC.cgst} onChange={(e) => setOpeningITC(p => ({ ...p, cgst: parseFloat(e.target.value) || 0 }))} />
              <Row label="SGST Balance" value={openingITC.sgst} onChange={(e) => setOpeningITC(p => ({ ...p, sgst: parseFloat(e.target.value) || 0 }))} />
            </Section>
          </div>
        </div>
      </div>

      {/* Compute Button */}
      <div className="flex justify-center">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold px-8 py-3 rounded-xl flex items-center gap-2 transition-colors disabled:opacity-50"
        >
          {mutation.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Calculator className="w-5 h-5" />}
          Compute GSTR-3B
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Challan Summary — most important */}
          <div className="bg-emerald-900 rounded-xl p-6 text-white">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
              <IndianRupee className="w-5 h-5" />
              Challan Amount Required
            </h3>
            <div className="grid grid-cols-4 gap-4 mb-4">
              {[
                ['IGST Cash', result.challan_summary?.igst_cash],
                ['CGST Cash', result.challan_summary?.cgst_cash],
                ['SGST Cash', result.challan_summary?.sgst_cash],
                ['CESS Cash', result.challan_summary?.cess_cash],
              ].map(([label, val]) => (
                <div key={label as string} className="bg-white/10 rounded-lg p-3 text-center">
                  <p className="text-emerald-300 text-xs mb-1">{label}</p>
                  <p className="text-white font-bold text-lg">{N(val as number)}</p>
                </div>
              ))}
            </div>
            <div className="border-t border-white/20 pt-4 flex items-center justify-between">
              <div className="flex gap-6 text-sm">
                <span className="text-emerald-300">Late Fee: {N((result.challan_summary?.late_fee_cgst || 0) + (result.challan_summary?.late_fee_sgst || 0))}</span>
                {result.interest?.delay_days > 0 && (
                  <span className="text-orange-300 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Interest ({result.interest.delay_days} days delay)
                  </span>
                )}
              </div>
              <div className="text-right">
                <p className="text-emerald-300 text-sm">Total Challan</p>
                <p className="text-white font-bold text-2xl">{N(result.challan_summary?.total_challan)}</p>
              </div>
            </div>
          </div>

          {/* ITC Utilization */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-900 mb-4">ITC Utilization Working</h3>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 font-semibold uppercase mb-3">ITC Used</p>
                <div className="space-y-2">
                  {Object.entries(result.itc_utilization?.itc_used || {}).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-gray-600">{key.replace(/_/g, ' ')}</span>
                      <span className="font-medium">{N(val as number)}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 font-semibold uppercase mb-3">Closing ITC Ledger</p>
                <div className="space-y-2">
                  {Object.entries(result.itc_utilization?.closing_itc_ledger || {}).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-gray-600">{key.toUpperCase()} Balance</span>
                      <span className={`font-medium ${(val as number) > 0 ? 'text-emerald-600' : 'text-gray-500'}`}>
                        {N(val as number)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 mt-3">{label}</p>
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

function Row({ label, value, onChange }: { label: string; value: number; onChange: any }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <label className="text-sm text-gray-700 flex-1">{label}</label>
      <input
        type="number"
        value={value || ''}
        onChange={onChange}
        placeholder="0.00"
        className="w-36 border border-gray-300 rounded-lg px-2.5 py-1.5 text-sm text-right focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
      />
    </div>
  )
}
