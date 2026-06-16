import { Calendar } from 'lucide-react'

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
}

interface Installment {
  due_date: string
  quarter: string
  cumulative_pct: number
  amount_due: number
}

interface Schedule {
  applicable: boolean
  note?: string
  estimated_annual_tax?: number
  installments?: Installment[]
}

export default function AdvanceTaxSchedule({ schedule }: { schedule: Schedule }) {
  if (!schedule.applicable) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 flex items-center gap-3 text-sm text-gray-500">
        <Calendar className="w-4 h-4" />
        {schedule.note}
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-blue-500" />
          Advance Tax Schedule — FY 2025-26
        </h3>
        <span className="text-sm text-gray-500">
          Estimated annual tax: <strong className="text-gray-800">₹{fmt(schedule.estimated_annual_tax!)}</strong>
        </span>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {schedule.installments!.map((inst, i) => (
          <div key={i} className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-center">
            <p className="text-xs text-blue-500 font-semibold mb-1">{inst.quarter}</p>
            <p className="text-lg font-bold text-blue-800">₹{fmt(inst.amount_due)}</p>
            <p className="text-xs text-blue-600 mt-1">Due {inst.due_date}</p>
            <p className="text-xs text-blue-400">{inst.cumulative_pct}% cumulative</p>
          </div>
        ))}
      </div>

      <p className="text-xs text-amber-700 mt-3 bg-amber-50 rounded-lg px-3 py-2">
        {schedule.note}
      </p>
    </div>
  )
}
