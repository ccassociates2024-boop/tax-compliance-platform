import { Lightbulb, TrendingUp } from 'lucide-react'

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
}

interface Tip {
  section: string
  tip: string
  potential_saving: number | null
}

export default function DeductionTips({ tips }: { tips: Tip[] }) {
  if (!tips.length) return null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-900 flex items-center gap-2 mb-4">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        Deduction Optimizer — Tax Saving Opportunities
      </h3>
      <div className="space-y-3">
        {tips.map((tip, i) => (
          <div key={i} className="flex items-start gap-3 bg-amber-50 border border-amber-100 rounded-lg p-3">
            <span className="text-xs font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded shrink-0 mt-0.5">
              {tip.section}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-800">{tip.tip}</p>
            </div>
            {tip.potential_saving != null && tip.potential_saving > 0 && (
              <div className="flex items-center gap-1 text-emerald-700 shrink-0">
                <TrendingUp className="w-3.5 h-3.5" />
                <span className="text-xs font-semibold">Save ₹{fmt(tip.potential_saving)}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
