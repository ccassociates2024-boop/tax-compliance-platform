import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { subscriptionAPI } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { CheckCircle2, Zap, Building2, Users, BadgeIndianRupee, ArrowRight, Loader2 } from 'lucide-react'

declare global { interface Window { Razorpay: any } }

function fmt(n: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(n)
}

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <BadgeIndianRupee className="w-5 h-5" />,
  starter: <Zap className="w-5 h-5" />,
  professional: <Users className="w-5 h-5" />,
  enterprise: <Building2 className="w-5 h-5" />,
}

const PLAN_COLORS: Record<string, string> = {
  free: 'border-gray-200',
  starter: 'border-blue-200',
  professional: 'border-violet-400 shadow-lg shadow-violet-100',
  enterprise: 'border-gray-300',
}

export default function PricingPage() {
  const [billing, setBilling] = useState<'monthly' | 'annual'>('annual')
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)

  const { data } = useQuery({
    queryKey: ['plans'],
    queryFn: () => subscriptionAPI.listPlans(),
  })

  const { data: subData } = useQuery({
    queryKey: ['my-subscription'],
    queryFn: () => subscriptionAPI.mySubscription(),
    enabled: isAuthenticated,
  })

  const plans = data?.data || []
  const currentPlan = subData?.data?.plan_id || 'free'

  const orderMutation = useMutation({
    mutationFn: (planId: string) =>
      subscriptionAPI.createOrder({ plan_id: planId, billing }),
    onSuccess: (res) => launchRazorpay(res.data),
  })

  function launchRazorpay(order: any) {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => {
      const rzp = new window.Razorpay({
        key: order.razorpay_key,
        amount: order.amount,
        currency: order.currency,
        name: 'TaxCompliance AI',
        description: `${order.plan_name} — ${billing === 'annual' ? 'Annual' : 'Monthly'}`,
        order_id: order.order_id,
        prefill: order.prefill,
        theme: { color: '#2563eb' },
        handler: async (response: any) => {
          await subscriptionAPI.verifyPayment({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
            plan_id: order.plan_name.toLowerCase(),
            billing,
          })
          window.location.reload()
        },
      })
      rzp.open()
    }
    document.body.appendChild(script)
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-blue-50 py-16 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-3">Simple, transparent pricing</h1>
          <p className="text-lg text-gray-500 mb-6">
            Built for Indian CAs, tax consultants, and business owners. No hidden charges.
          </p>

          {/* Billing toggle */}
          <div className="inline-flex items-center gap-3 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setBilling('monthly')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition ${
                billing === 'monthly' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling('annual')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition ${
                billing === 'annual' ? 'bg-white shadow text-gray-900' : 'text-gray-500'
              }`}
            >
              Annual
              <span className="ml-2 text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-semibold">
                Save 25%
              </span>
            </button>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-4 gap-5">
          {plans.map((plan: any) => {
            const isCurrent = plan.id === currentPlan
            const isPopular = plan.is_popular
            const isCustom = plan.is_custom
            const price = billing === 'annual' ? plan.price_annual_per_month_inr : plan.price_monthly_inr

            return (
              <div
                key={plan.id}
                className={`relative bg-white rounded-2xl border-2 p-6 flex flex-col ${PLAN_COLORS[plan.id]}`}
              >
                {isPopular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                    <span className="bg-violet-600 text-white text-xs font-bold px-4 py-1 rounded-full">
                      MOST POPULAR
                    </span>
                  </div>
                )}

                <div className="flex items-center gap-2 mb-4">
                  <span className={`p-2 rounded-lg ${
                    plan.id === 'professional' ? 'bg-violet-100 text-violet-600'
                    : plan.id === 'starter' ? 'bg-blue-100 text-blue-600'
                    : 'bg-gray-100 text-gray-600'
                  }`}>
                    {PLAN_ICONS[plan.id]}
                  </span>
                  <h3 className="font-bold text-gray-900">{plan.name}</h3>
                </div>

                {isCustom ? (
                  <div className="mb-5">
                    <p className="text-2xl font-bold text-gray-900">Custom</p>
                    <p className="text-xs text-gray-500">Contact us for pricing</p>
                  </div>
                ) : plan.id === 'free' ? (
                  <div className="mb-5">
                    <p className="text-3xl font-bold text-gray-900">₹0</p>
                    <p className="text-xs text-gray-500">Forever free</p>
                  </div>
                ) : (
                  <div className="mb-5">
                    <div className="flex items-end gap-1">
                      <p className="text-3xl font-bold text-gray-900">₹{fmt(price)}</p>
                      <p className="text-sm text-gray-500 mb-1">/mo</p>
                    </div>
                    {billing === 'annual' && (
                      <p className="text-xs text-emerald-600 font-medium">
                        ₹{fmt(plan.price_annual_inr)}/year · Save {plan.annual_saving_pct}%
                      </p>
                    )}
                  </div>
                )}

                {/* Limits */}
                <div className="space-y-1.5 mb-5 text-xs">
                  <div className="flex justify-between text-gray-600">
                    <span>Clients</span>
                    <span className="font-medium">{plan.clients_limit === -1 ? 'Unlimited' : plan.clients_limit}</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>AI queries/mo</span>
                    <span className="font-medium">{plan.ai_queries_per_month === -1 ? 'Unlimited' : plan.ai_queries_per_month}</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>Portal fetches/mo</span>
                    <span className="font-medium">{plan.portal_fetches_per_month === -1 ? 'Unlimited' : plan.portal_fetches_per_month}</span>
                  </div>
                </div>

                {/* Features */}
                <ul className="space-y-2 mb-6 flex-1">
                  {plan.features.map((f: string) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-gray-700">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                {/* CTA */}
                {isCurrent ? (
                  <button disabled
                    className="w-full py-2.5 rounded-xl text-sm font-medium bg-gray-100 text-gray-400 cursor-not-allowed">
                    Current Plan
                  </button>
                ) : isCustom ? (
                  <a href="mailto:sales@taxcomplianceai.in"
                    className="w-full py-2.5 rounded-xl text-sm font-medium text-center bg-gray-900 text-white hover:bg-gray-700 transition flex items-center justify-center gap-2">
                    Contact Sales <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                ) : plan.id === 'free' ? (
                  <a href="/register"
                    className="w-full py-2.5 rounded-xl text-sm font-medium text-center border border-gray-200 text-gray-700 hover:bg-gray-50 transition">
                    Get Started Free
                  </a>
                ) : (
                  <button
                    onClick={() => orderMutation.mutate(plan.id)}
                    disabled={orderMutation.isPending || !isAuthenticated}
                    className={`w-full py-2.5 rounded-xl text-sm font-medium flex items-center justify-center gap-2 transition ${
                      isPopular
                        ? 'bg-violet-600 text-white hover:bg-violet-700'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    } disabled:opacity-50`}
                  >
                    {orderMutation.isPending
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Processing…</>
                      : <>Upgrade to {plan.name} <ArrowRight className="w-3.5 h-3.5" /></>
                    }
                  </button>
                )}

                {!isAuthenticated && !isCustom && plan.id !== 'free' && (
                  <p className="text-xs text-center text-gray-400 mt-2">
                    <a href="/login" className="text-blue-600 hover:underline">Sign in</a> to upgrade
                  </p>
                )}
              </div>
            )
          })}
        </div>

        {/* Trust section */}
        <div className="mt-16 text-center space-y-3">
          <p className="text-sm text-gray-500 font-medium">
            🔒 Payments secured by Razorpay · PCI DSS compliant · Data stored in India (AWS Mumbai)
          </p>
          <p className="text-xs text-gray-400">
            GST (18%) applicable on all paid plans · Prices shown exclusive of GST ·
            Annual plans are billed once per year · Cancel anytime
          </p>
        </div>
      </div>
    </div>
  )
}
