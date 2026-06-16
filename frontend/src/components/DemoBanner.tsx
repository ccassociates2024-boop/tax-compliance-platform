/**
 * DemoBanner — shown at the very top of the app when VITE_DEMO_MODE=true.
 * Orange stripe that clearly tells testers this is sandbox data.
 */
import { useState } from 'react'
import { X, FlaskConical, ChevronDown, ChevronUp } from 'lucide-react'

const DEMO_CLIENTS = [
  { name: 'Rajesh Deshmukh',          pan: 'ABCPD1234R', type: 'Salaried',        badge: 'ITR-1' },
  { name: 'Sunita Joshi',             pan: 'BFXPJ5678S', type: 'Freelancer + GST', badge: 'ITR-4' },
  { name: 'Sahyadri Software Solutions Pvt Ltd', pan: 'AADCS3456M', type: 'Company + TDS', badge: 'ITR-6' },
  { name: 'Vikram Patil',             pan: 'CLHPP7890V', type: 'Business + LTCG', badge: 'ITR-3' },
  { name: 'Pushpa Kulkarni',          pan: 'DFZPK2345P', type: 'Senior Citizen',  badge: 'ITR-1' },
]

export default function DemoBanner() {
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="bg-amber-500 text-white text-sm font-medium">
      {/* Main bar */}
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-4 h-4 flex-shrink-0" />
          <span>
            <strong>🎭 DEMO MODE</strong> — Sample data only. No real portals, no real payments.
            Login: <code className="bg-amber-600 px-1.5 py-0.5 rounded text-xs font-mono">demo@taxcomplianceai.in</code>{' '}
            / <code className="bg-amber-600 px-1.5 py-0.5 rounded text-xs font-mono">demo123</code>
          </span>
        </div>
        <div className="flex items-center gap-3 ml-4 flex-shrink-0">
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center gap-1 text-amber-100 hover:text-white text-xs"
          >
            {expanded ? 'Hide' : 'Show'} demo clients
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="text-amber-200 hover:text-white"
            aria-label="Dismiss demo banner"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded: show demo clients */}
      {expanded && (
        <div className="border-t border-amber-400 bg-amber-600 px-4 py-3">
          <p className="text-amber-100 text-xs mb-2 font-normal">
            5 pre-seeded demo clients are available in your dashboard:
          </p>
          <div className="flex flex-wrap gap-2">
            {DEMO_CLIENTS.map(c => (
              <div key={c.pan} className="bg-amber-500 rounded-lg px-3 py-1.5 flex items-center gap-2">
                <div>
                  <span className="font-semibold text-xs">{c.name}</span>
                  <span className="text-amber-200 font-normal text-xs"> · {c.type}</span>
                </div>
                <span className="bg-amber-700 text-amber-100 text-[10px] font-bold px-1.5 py-0.5 rounded">
                  {c.badge}
                </span>
              </div>
            ))}
          </div>
          <p className="text-amber-200 text-xs mt-2 font-normal">
            All AI answers, tax computations, GST & TDS data are pre-computed for these clients.
            The AI assistant also responds to plain-English questions in demo mode.
          </p>
        </div>
      )}
    </div>
  )
}
