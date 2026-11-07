import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, FileText, Loader2, RefreshCw, XCircle } from 'lucide-react'

type Invoice = {
  id: string
  invoice_number: string
  amount_rub: number
  bonus_rub: number
  total_credit_rub: number
  tariff_name: string
  buyer_inn: string
  buyer_kpp?: string
  buyer_name: string
  buyer_email?: string
  buyer_phone?: string
  buyer_telegram?: string
  status: 'issued' | 'proof_submitted' | 'paid' | 'cancelled' | string
  created_at?: string | null
  paid_at?: string | null
  proof_submitted_at?: string | null
  proof_original_name?: string | null
  proof_status?: 'submitted' | 'none' | string
  settlement_mode?: 'credited' | 'manual_closed' | string | null
}

const statusCopy: Record<string, { label: string; color: string }> = {
  issued: { label: 'Ожидает оплаты', color: '#92400e' },
  proof_submitted: { label: 'Платёжка на проверке', color: '#0369a1' },
  paid: { label: 'Закрыт', color: '#047857' },
  cancelled: { label: 'Отменён', color: '#64748b' },
}

const PAGE_SIZE = 25

function money(value: number) {
  return Number(value || 0).toLocaleString('ru-RU') + ' ₽'
}

function date(value?: string | null) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString('ru-RU')
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

function formatError(error: unknown) {
  const raw = error instanceof Error ? error.message : String(error || '')
  try {
    const parsed = JSON.parse(raw)
    return parsed.detail || raw
  } catch {
    return raw || 'Не удалось выполнить действие'
  }
}

export function InvoicesView() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [actionInvoiceId, setActionInvoiceId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async (targetPage = page, manual = false) => {
    if (manual) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(targetPage * PAGE_SIZE) })
      const data = await request<{ invoices?: Invoice[]; total?: number }>(`/api/admin/invoices?${query}`)
      setInvoices(data.invoices || [])
      setTotal(data.total ?? (data.invoices || []).length)
    } catch (err) {
      setError(formatError(err))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [page])

  useEffect(() => {
    void load(page)
  }, [load, page])

  const awaitingReview = useMemo(
    () => invoices.filter(invoice => invoice.status === 'proof_submitted').length,
    [invoices],
  )
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  async function confirmPaid(invoice: Invoice) {
    const confirmation = [
      `Подтвердить фактическое поступление денег по счёту № ${invoice.invoice_number}?`,
      '',
      `На баланс клиента будет зачислено ${money(invoice.total_credit_rub)}${invoice.bonus_rub ? ` (включая бонус ${money(invoice.bonus_rub)})` : ''}.`,
      'Подтверждайте только после сверки с поступлением на расчётный счёт.',
    ].join('\n')
    if (!window.confirm(confirmation)) return

    setActionInvoiceId(invoice.id)
    setError('')
    try {
      const data = await request<{ invoice: Invoice }>(`/api/admin/invoices/${encodeURIComponent(invoice.id)}/mark-paid`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setInvoices(current => current.map(item => item.id === invoice.id ? data.invoice : item))
    } catch (err) {
      setError(formatError(err))
    } finally {
      setActionInvoiceId(null)
    }
  }

  async function closeAlreadyCredited(invoice: Invoice) {
    const confirmation = [
      `Закрыть счёт № ${invoice.invoice_number} без начисления?`,
      '',
      'Используйте это только если баланс клиенту уже начислен вручную другим действием.',
      'Эта кнопка не зачисляет сумму и бонус повторно.',
    ].join('\n')
    if (!window.confirm(confirmation)) return

    setActionInvoiceId(invoice.id)
    setError('')
    try {
      const data = await request<{ invoice: Invoice }>(`/api/admin/invoices/${encodeURIComponent(invoice.id)}/close-manually`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      })
      setInvoices(current => current.map(item => item.id === invoice.id ? data.invoice : item))
    } catch (err) {
      setError(formatError(err))
    } finally {
      setActionInvoiceId(null)
    }
  }

  return (
    <section className="stack invoice-admin-view">
      <div className="toolbar-panel invoice-toolbar">
        <div>
          <strong>Счета на безналичную оплату</strong>
          <small>Платёжка ускоряет проверку, но баланс пополняется только после сверки поступления.</small>
        </div>
        <div className="invoice-toolbar-status">
          {awaitingReview > 0 ? `На странице к проверке: ${awaitingReview}` : 'На странице нет платёжек на проверке'}
        </div>
        <button className="secondary small-text" onClick={() => void load(page, true)} disabled={refreshing}>
          {refreshing ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          Обновить
        </button>
      </div>

      {error && <div className="alert error"><XCircle size={18} />{error}</div>}

      <div className="table-panel">
        {loading ? (
          <div className="invoice-empty"><Loader2 size={20} className="spin" />Загружаем счета…</div>
        ) : invoices.length === 0 ? (
          <div className="invoice-empty">Счета ещё не выставлялись.</div>
        ) : (
          <table className="invoice-table">
            <thead>
              <tr>
                <th>Счёт</th>
                <th>Плательщик</th>
                <th>Сумма</th>
                <th>Платёжка</th>
                <th>Статус</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(invoice => {
                const status = statusCopy[invoice.status] || { label: invoice.status, color: '#475569' }
                const hasProof = invoice.status === 'proof_submitted' || invoice.proof_status === 'submitted' || Boolean(invoice.proof_submitted_at)
                const isWorking = actionInvoiceId === invoice.id
                const settlementLabel = invoice.settlement_mode === 'credited'
                  ? 'Зачислено через счёт'
                  : invoice.settlement_mode === 'manual_closed'
                    ? 'Закрыт без начисления'
                    : 'Способ закрытия не указан'
                return (
                  <tr key={invoice.id}>
                    <td>
                      <strong>{invoice.invoice_number}</strong>
                      <small>Выставлен: {date(invoice.created_at)}</small>
                      <small>{invoice.tariff_name}</small>
                    </td>
                    <td>
                      <strong>{invoice.buyer_name || '—'}</strong>
                      <small>ИНН {invoice.buyer_inn || '—'}{invoice.buyer_kpp ? ` · КПП ${invoice.buyer_kpp}` : ''}</small>
                      {invoice.buyer_email && <small>✉️ {invoice.buyer_email}</small>}
                      {invoice.buyer_phone && <small>📞 {invoice.buyer_phone}</small>}
                      {invoice.buyer_telegram && (
                        <small>
                          💬 <a href={`https://t.me/${invoice.buyer_telegram.replace('@', '')}`} target="_blank" rel="noreferrer" style={{ color: '#0284c7' }}>
                            @{invoice.buyer_telegram.replace('@', '')}
                          </a>
                        </small>
                      )}
                    </td>
                    <td>
                      <strong>{money(invoice.amount_rub)}</strong>
                      <small>На баланс: {money(invoice.total_credit_rub)}</small>
                      {invoice.bonus_rub > 0 && <small>Бонус: +{money(invoice.bonus_rub)}</small>}
                    </td>
                    <td>
                      {hasProof ? (
                        <a className="download-pill input-file" href={`/api/admin/invoices/${encodeURIComponent(invoice.id)}/proof`} target="_blank" rel="noreferrer">
                          <FileText size={14} />
                          <span>{invoice.proof_original_name || 'Открыть платёжку'}</span>
                          <ExternalLink size={12} />
                        </a>
                      ) : (
                        <small>Не прикреплена</small>
                      )}
                      {invoice.proof_submitted_at && <small>Отправлена: {date(invoice.proof_submitted_at)}</small>}
                    </td>
                    <td>
                      <span className="invoice-status" style={{ color: status.color }}>{status.label}</span>
                      {invoice.paid_at && <small>Закрыт: {date(invoice.paid_at)}</small>}
                      {invoice.status === 'paid' && <small>{settlementLabel}</small>}
                    </td>
                    <td>
                      {invoice.status === 'paid' ? (
                        <span className="invoice-confirmed"><CheckCircle2 size={15} />Закрыт</span>
                      ) : (
                        <div className="invoice-actions">
                          <button
                            className="button-primary small-text"
                            disabled={isWorking}
                            onClick={() => void confirmPaid(invoice)}
                            title="После сверки поступления на расчётный счёт начислит клиенту сумму счёта и бонус"
                          >
                            {isWorking ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
                            {isWorking ? 'Зачисляем…' : 'Зачислить на баланс'}
                          </button>
                          <button
                            className="secondary small-text"
                            disabled={isWorking}
                            onClick={() => void closeAlreadyCredited(invoice)}
                            title="Закрывает счёт без повторного начисления"
                          >
                            Закрыть без начисления
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
      {!loading && total > 0 && (
        <div className="invoice-pagination">
          <span>Показано {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} из {total}</span>
          <div>
            <button className="secondary small-text" disabled={page === 0 || refreshing} onClick={() => setPage(current => current - 1)}>Назад</button>
            <span>Страница {page + 1} из {pageCount}</span>
            <button className="secondary small-text" disabled={page + 1 >= pageCount || refreshing} onClick={() => setPage(current => current + 1)}>Далее</button>
          </div>
        </div>
      )}
    </section>
  )
}
