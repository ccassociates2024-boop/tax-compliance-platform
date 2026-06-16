import { FileText } from 'lucide-react'

const FORM_COLORS: Record<string, string> = {
  'ITR-1': 'bg-emerald-50 border-emerald-200 text-emerald-800',
  'ITR-2': 'bg-blue-50 border-blue-200 text-blue-800',
  'ITR-3': 'bg-violet-50 border-violet-200 text-violet-800',
  'ITR-4': 'bg-amber-50 border-amber-200 text-amber-800',
  'ITR-5': 'bg-orange-50 border-orange-200 text-orange-800',
  'ITR-6': 'bg-red-50 border-red-200 text-red-800',
  'ITR-7': 'bg-gray-50 border-gray-200 text-gray-800',
}

interface Props {
  form: string
  reason: string
}

export default function ITRFormBadge({ form, reason }: Props) {
  const colors = FORM_COLORS[form] ?? FORM_COLORS['ITR-2']
  return (
    <div className={`rounded-xl border p-4 flex items-start gap-3 ${colors}`}>
      <div className="flex-shrink-0 mt-0.5">
        <FileText className="w-5 h-5" />
      </div>
      <div>
        <p className="font-semibold text-sm">Applicable Form: {form}</p>
        <p className="text-xs mt-0.5 opacity-80">{reason}</p>
      </div>
    </div>
  )
}
