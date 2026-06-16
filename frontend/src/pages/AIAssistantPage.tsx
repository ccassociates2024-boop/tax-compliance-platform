import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { clientsAPI, aiAPI } from '../api/client'
import { Bot, Send, User, Loader2, Sparkles, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

const QUICK_PROMPTS = [
  'Compare Old vs New regime for this client',
  'What deductions can this client claim?',
  'Check for AIS vs 26AS mismatches',
  'Compute advance tax for Q1',
  'Prepare GSTR-3B working for this month',
  'Check TDS compliance for Q4',
]

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Namaste! I'm **TaxAI**, your intelligent Indian tax compliance assistant.\n\n" +
        "I can help you with:\n" +
        "- **ITR filing** — Income computation, regime comparison, deduction optimization\n" +
        "- **GST** — GSTR-1 preparation, GSTR-3B working, ITC reconciliation\n" +
        "- **TDS** — Compliance check, default computation, challan matching\n" +
        "- **AIS/26AS analysis** — Mismatch detection, audit risk scoring\n\n" +
        "Select a client and start asking!",
    },
  ])
  const [input, setInput] = useState('')
  const [selectedClient, setSelectedClient] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: clientsData } = useQuery({
    queryKey: ['clients'],
    queryFn: () => clientsAPI.list({ per_page: 100 }),
  })
  const clients = clientsData?.data?.clients || []

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text?: string) => {
    const messageText = text || input.trim()
    if (!messageText || isStreaming) return

    setInput('')
    const newMessages: Message[] = [
      ...messages,
      { role: 'user', content: messageText },
    ]
    setMessages(newMessages)
    setIsStreaming(true)

    const assistantMsg: Message = { role: 'assistant', content: '', streaming: true }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const response = await aiAPI.chat(
        newMessages.map((m) => ({ role: m.role, content: m.content })),
        selectedClient || undefined
      )

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let fullText = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        fullText += decoder.decode(value, { stream: true })
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: fullText,
            streaming: true,
          }
          return updated
        })
      }

      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: fullText }
        return updated
      })
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
        }
        return updated
      })
    } finally {
      setIsStreaming(false)
    }
  }

  const clearChat = () => {
    setMessages([
      {
        role: 'assistant',
        content: "Chat cleared. How can I help you?",
      },
    ])
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col p-4 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Select Client</label>
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">General query</option>
            {clients.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.full_name} ({c.pan})
              </option>
            ))}
          </select>
        </div>

        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">Quick Prompts</p>
          <div className="space-y-1.5">
            {QUICK_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => sendMessage(p)}
                disabled={isStreaming}
                className="w-full text-left text-xs text-gray-700 hover:text-blue-600 hover:bg-blue-50 px-2 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                <Sparkles className="w-3 h-3 inline mr-1 text-blue-500" />
                {p}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={clearChat}
          className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 mt-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Clear conversation
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              )}
              <div
                className={`max-w-3xl rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-900'
                }`}
              >
                {msg.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    {msg.streaming && (
                      <span className="inline-block w-1.5 h-4 bg-blue-500 animate-pulse ml-0.5" />
                    )}
                  </div>
                ) : (
                  <p className="text-sm">{msg.content}</p>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 bg-white p-4">
          <div className="flex gap-3 max-w-4xl mx-auto">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder="Ask about ITR, GST, TDS, deductions..."
              disabled={isStreaming}
              className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || isStreaming}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl px-4 py-2.5 transition-colors"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
