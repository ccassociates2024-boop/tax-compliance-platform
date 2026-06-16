import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Download, FileSpreadsheet, AlertCircle, CheckCircle2, Loader2, X, Search } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Props {
  clientId: string
  period: string
  gstin: string
}

interface ParseResult {
  message: string
  parse_summary: { total_rows: number; parsed_invoices: number; error_rows: number }
  gstr1_summary: Record<string, any>
  validation_errors: Record<string, string[]>
  hsn_summary: any[]
  hsn_analysis: string
}

export default function GSTUploadTab({ clientId, period, gstin }: Props) {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<ParseResult | null>(null)
  const [error, setError] = useState('')
  const [hsnSearch, setHsnSearch] = useState('')
  const [hsnResult, setHsnResult] = useState<any>(null)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return
    setUploading(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(
        `${API}/api/v1/gst-data/upload/excel/${clientId}?period=${period}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
          body: formData,
        }
      )
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setResult(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }, [clientId, period])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
    },
    maxFiles: 1,
    disabled: uploading,
  })

  const downloadTemplate = () => {
    window.open(
      `${API}/api/v1/gst-data/template/download?gstin=${gstin}`,
      '_blank'
    )
  }

  const searchHSN = async () => {
    if (!hsnSearch.trim()) return
    try {
      const isCode = /^\d+$/.test(hsnSearch.trim())
      const url = isCode
        ? `${API}/api/v1/gst-data/hsn/lookup?code=${hsnSearch}`
        : `${API}/api/v1/gst-data/hsn/lookup?keyword=${hsnSearch}`
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      })
      const data = await res.json()
      setHsnResult(data)
    } catch {
      setHsnResult({ error: 'HSN lookup failed' })
    }
  }

  const errorCount = result ? Object.keys(result.validation_errors).length : 0
  const summary = result?.gstr1_summary

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Upload area */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Upload Invoice File</h2>
          <button
            onClick={downloadTemplate}
            className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            <Download className="w-4 h-4" />
            Download Template
          </button>
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-emerald-400 bg-emerald-50'
              : uploading
              ? 'border-gray-200 bg-gray-50 cursor-not-allowed'
              : 'border-gray-300 hover:border-emerald-400 hover:bg-emerald-50'
          }`}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-10 h-10 text-emerald-500 animate-spin" />
              <p className="text-gray-600 font-medium">Processing invoices...</p>
              <p className="text-sm text-gray-400">Validating, computing taxes, building GSTR-1</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <FileSpreadsheet className="w-10 h-10 text-gray-400" />
              <div>
                <p className="text-gray-700 font-medium">
                  {isDragActive ? 'Drop the file here' : 'Drag & drop Excel/CSV file'}
                </p>
                <p className="text-sm text-gray-400 mt-1">or click to browse — .xlsx, .xls, .csv supported</p>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
      </div>

      {/* Result */}
      {result && (
        <>
          {/* Parse summary */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Total Rows', value: result.parse_summary.total_rows, color: 'text-gray-900' },
              { label: 'Invoices Parsed', value: result.parse_summary.parsed_invoices, color: 'text-emerald-600' },
              { label: 'Error Rows', value: result.parse_summary.error_rows, color: 'text-red-600' },
              { label: 'Validation Errors', value: errorCount, color: errorCount > 0 ? 'text-orange-600' : 'text-emerald-600' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* GSTR-1 Summary */}
          {summary && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-900 mb-4">GSTR-1 Summary</h3>
              <div className="grid grid-cols-3 gap-4">
                {[
                  ['Total Invoice Value', `₹${summary.total_invoice_value?.toLocaleString('en-IN')}`],
                  ['Total Taxable Value', `₹${summary.total_taxable_value?.toLocaleString('en-IN')}`],
                  ['Total IGST', `₹${summary.total_igst?.toLocaleString('en-IN')}`],
                  ['Total CGST', `₹${summary.total_cgst?.toLocaleString('en-IN')}`],
                  ['Total SGST', `₹${summary.total_sgst?.toLocaleString('en-IN')}`],
                  ['Total CESS', `₹${summary.total_cess?.toLocaleString('en-IN')}`],
                  ['B2B Invoices', `${summary.b2b_count} (₹${summary.b2b_value?.toLocaleString('en-IN')})`],
                  ['B2C Invoices', `${summary.b2cs_count} (₹${summary.b2cs_value?.toLocaleString('en-IN')})`],
                  ['Exports', `${summary.export_count}`],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                    <span className="text-sm text-gray-600">{label}</span>
                    <span className="text-sm font-semibold text-gray-900">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* HSN Summary */}
          {result.hsn_summary?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-900 mb-4">HSN-wise Summary (Table 12)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      {['#', 'HSN/SAC', 'Description', 'UQC', 'Qty', 'Taxable Value', 'IGST', 'CGST', 'SGST'].map(h => (
                        <th key={h} className="text-left text-xs text-gray-500 font-semibold py-2 px-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.hsn_summary.map((row: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="py-2 px-2 text-gray-500">{row.num}</td>
                        <td className="py-2 px-2 font-mono font-medium">{row.hsn_sc}</td>
                        <td className="py-2 px-2 text-gray-700 max-w-xs truncate">{row.desc}</td>
                        <td className="py-2 px-2 text-gray-500">{row.uqc}</td>
                        <td className="py-2 px-2 text-right">{row.qty?.toLocaleString('en-IN')}</td>
                        <td className="py-2 px-2 text-right">₹{row.txval?.toLocaleString('en-IN')}</td>
                        <td className="py-2 px-2 text-right">₹{row.iamt?.toLocaleString('en-IN')}</td>
                        <td className="py-2 px-2 text-right">₹{row.camt?.toLocaleString('en-IN')}</td>
                        <td className="py-2 px-2 text-right">₹{row.samt?.toLocaleString('en-IN')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* AI HSN Analysis */}
              {result.hsn_analysis && (
                <div className="mt-4 bg-blue-50 rounded-lg p-4">
                  <p className="text-xs font-semibold text-blue-700 mb-2">AI Analysis</p>
                  <p className="text-sm text-blue-900 whitespace-pre-wrap">{result.hsn_analysis}</p>
                </div>
              )}
            </div>
          )}

          {/* Validation errors */}
          {errorCount > 0 && (
            <div className="bg-white rounded-xl border border-orange-200 p-5">
              <h3 className="font-semibold text-orange-700 mb-3 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                Validation Errors ({errorCount} invoices)
              </h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {Object.entries(result.validation_errors).map(([invNo, errors]) => (
                  <div key={invNo} className="bg-orange-50 rounded-lg p-3">
                    <p className="text-sm font-medium text-orange-800 mb-1">Invoice: {invNo}</p>
                    <ul className="space-y-0.5">
                      {(errors as string[]).map((e, i) => (
                        <li key={i} className="text-xs text-orange-700">• {e}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* HSN Lookup */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-3">HSN/SAC Code Lookup</h3>
        <div className="flex gap-3">
          <input
            value={hsnSearch}
            onChange={(e) => setHsnSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && searchHSN()}
            placeholder="Enter HSN code (e.g. 8471) or product name (e.g. computer)..."
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500"
          />
          <button
            onClick={searchHSN}
            className="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors flex items-center gap-2 text-sm font-medium"
          >
            <Search className="w-4 h-4" />
            Lookup
          </button>
        </div>

        {hsnResult && (
          <div className="mt-3">
            {hsnResult.error ? (
              <p className="text-sm text-red-600">{hsnResult.error}</p>
            ) : hsnResult.results ? (
              <div className="space-y-2">
                {hsnResult.results.map((r: any) => (
                  <div key={r.hsn_code} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2.5">
                    <div>
                      <span className="font-mono font-bold text-gray-800 mr-3">{r.hsn_code}</span>
                      <span className="text-sm text-gray-700">{r.description}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-gray-500">UQC: {r.uqc}</span>
                      <span className="font-semibold text-emerald-700">GST: {r.igst_rate}%</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-gray-50 rounded-lg px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-mono font-bold text-gray-800 text-lg mr-3">{hsnResult.hsn_code}</span>
                    <span className="text-gray-700">{hsnResult.desc}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-emerald-700 font-bold text-lg">GST {hsnResult.igst}%</p>
                    <p className="text-xs text-gray-500">CGST {hsnResult.cgst}% + SGST {hsnResult.sgst}%</p>
                    {hsnResult.cess > 0 && <p className="text-xs text-orange-600">+ Cess {hsnResult.cess}%</p>}
                  </div>
                </div>
                {hsnResult.uqc && <p className="text-sm text-gray-500 mt-1">Unit: {hsnResult.uqc}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
