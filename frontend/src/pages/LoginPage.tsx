import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI, demoAPI } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { BadgeIndianRupee, Loader2, FlaskConical } from 'lucide-react'

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore(s => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await authAPI.login(email, password)
      login(res.data.access_token, res.data.user)
      navigate('/')
    } catch {
      setError('Invalid email or password.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDemoLogin() {
    setDemoLoading(true)
    setError('')
    try {
      const res = await demoAPI.login()
      login(res.data.access_token, res.data.user)
      navigate('/')
    } catch {
      setError('Demo login failed. Make sure the server is running with DEMO_MODE=true.')
    } finally {
      setDemoLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-8">
        <div className="flex items-center gap-2 mb-8">
          <BadgeIndianRupee className="w-8 h-8 text-blue-600" />
          <h1 className="text-xl font-bold text-gray-900">TaxCompliance AI</h1>
          {IS_DEMO && (
            <span className="ml-auto bg-amber-100 text-amber-700 text-xs font-bold px-2 py-1 rounded-full">
              DEMO
            </span>
          )}
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-1">Sign in</h2>
        <p className="text-sm text-gray-500 mb-6">Access your tax compliance dashboard</p>

        {/* Demo mode call-to-action */}
        {IS_DEMO && (
          <div className="mb-5 rounded-xl border-2 border-amber-300 bg-amber-50 p-4">
            <div className="flex items-start gap-3 mb-3">
              <FlaskConical className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold text-amber-800">Try the demo — no signup needed</p>
                <p className="text-xs text-amber-600 mt-0.5">
                  5 pre-loaded clients · Full tax computations · AI assistant · No real data
                </p>
              </div>
            </div>
            <button
              onClick={handleDemoLogin}
              disabled={demoLoading}
              className="w-full bg-amber-500 hover:bg-amber-600 text-white font-semibold text-sm py-2.5 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {demoLoading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Entering demo…</>
                : <><FlaskConical className="w-4 h-4" /> Enter Demo Mode</>
              }
            </button>
            <p className="text-center text-xs text-amber-500 mt-2">
              Or use: demo@taxcomplianceai.in / demo123
            </p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">
            {error}
          </div>
        )}

        <div className="relative mb-5">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-white px-3 text-gray-400 font-medium">
              {IS_DEMO ? 'or sign in with your own account' : 'Sign in'}
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@cafirm.in"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium text-sm hover:bg-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Don't have an account?{' '}
          <a href="/register" className="text-blue-600 font-medium hover:underline">Register</a>
        </p>
      </div>
    </div>
  )
}
