import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string
  name?: string           // some endpoints return "name"
  firm_name?: string
  role: string
  subscription_plan: string
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  login: (token: string, user: User) => void   // alias for setAuth
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => {
        // Normalise: API may return "name" or "full_name"
        const normalised = { ...user, full_name: user.full_name || (user as any).name || '' }
        localStorage.setItem('access_token', token)
        set({ token, user: normalised, isAuthenticated: true })
      },
      login: (token, user) => {
        const normalised = { ...user, full_name: user.full_name || (user as any).name || '' }
        localStorage.setItem('access_token', token)
        set({ token, user: normalised, isAuthenticated: true })
      },
      logout: () => {
        localStorage.removeItem('access_token')
        set({ token: null, user: null, isAuthenticated: false })
      },
    }),
    { name: 'auth-store' }
  )
)
