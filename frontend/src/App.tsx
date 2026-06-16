import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ClientsPage from './pages/ClientsPage'
import ClientDetailPage from './pages/ClientDetailPage'
import IncomeTaxPage from './pages/IncomeTaxPage'
import GSTPage from './pages/GSTPage'
import TDSPage from './pages/TDSPage'
import AIAssistantPage from './pages/AIAssistantPage'
import PricingPage from './pages/PricingPage'
import Layout from './components/Layout'
import DemoBanner from './components/DemoBanner'

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1 } },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {IS_DEMO && <DemoBanner />}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="clients/:id" element={<ClientDetailPage />} />
            <Route path="income-tax/:clientId?" element={<IncomeTaxPage />} />
            <Route path="gst/:clientId?" element={<GSTPage />} />
            <Route path="tds/:clientId?" element={<TDSPage />} />
            <Route path="ai-assistant" element={<AIAssistantPage />} />
            <Route path="billing" element={<PricingPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
