import { useQuery } from '@tanstack/react-query'
import { clientsAPI } from '../api/client'

interface Props {
  value: string
  onChange: (id: string) => void
}

export default function ClientSelector({ value, onChange }: Props) {
  const { data } = useQuery({
    queryKey: ['clients-list'],
    queryFn: () => clientsAPI.list({ limit: 100 }),
  })

  const clients = data?.data?.clients ?? []

  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="border border-gray-200 rounded-lg px-3 py-2 text-sm min-w-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <option value="">Select client…</option>
      {clients.map((c: any) => (
        <option key={c.id} value={c.id}>
          {c.name} — {c.pan}
        </option>
      ))}
    </select>
  )
}
