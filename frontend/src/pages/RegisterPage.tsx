import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { BadgeIndianRupee, Loader2 } from 'lucide-react'

export default function RegisterPage() {
  const navigate = useNavigate()
  const loginStore = useAuthStore(s => s.login)
  const [form, setForm] = useState({ name: '', email: '', password: '', firm_name: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await authAPI.register(form)
      // Auto-login after successful registration
      loginStore(res.data.access_token, res.data.user)
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  function set(k: string, v: string) { setForm(f => ({ ...f, [k]: v })) }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-8">
        <div className="flex items-center gap-2 mb-8">
          <BadgeIndianRupee className="w-8 h-8 text-blue-600" />
          <h1 className="text-xl font-bold text-gray-900">TaxCompliance AI</h1>
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-1">Create Account</h2>
        <p className="text-sm text-gray-500 mb-6">Start your free trial — no credit card required</p>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { k: 'name', label: 'Full Name', type: 'text', ph: 'CA Sourabh Chavan' },
            { k: 'firm_name', label: 'Firm Name', type: 'text', ph: 'C C & Associates' },
            { k: 'email', label: 'Email', type: 'email', ph: 'sourabh@ccassociates.in' },
            { k: 'password', label: 'Password', type: 'password', ph: '8+ characters' },
          ].map(({ k, label, type, ph }) => (
            <div key={k}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
              <input
                type={type}
                required
                value={(form as any)[k]}
                onChange={e => set(k, e.target.value)}
                placeholder={ph}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium text-sm hover:bg-blue-700 transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <a href="/login" className="text-blue-600 font-medium hover:underline">Sign in</a>
        </p>
      </div>
    </div>
  )
}
