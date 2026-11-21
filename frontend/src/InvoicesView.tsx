import { useCallback, useEffect, useRef, useState } from 'react'
import {
  CreditCard,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  UserRound,
  Wallet,
  X,
  XCircle,
} from 'lucide-react'
import { PaymentRow } from './invoices/PaymentRow'
import {
  formatMoney,
  PERIOD_OPTIONS,
  type InvoicePayload,
  type PaymentOverviewResponse,
  type PaymentPeriod,
  type PaymentStatusFilter,
  type PaymentTab,
} from './invoices/types'

const PAGE_SIZE = 25

type InvoicesViewProps = {
  onOpenClient?: (clientId: string) => void
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

export function InvoicesView({ onOpenClient }: InvoicesViewProps) {
  const [period, setPeriod] = useState<PaymentPeriod>('all')
  const [tab, setTab] = useState<PaymentTab>('all')
  const [statusFilter, setStatusFilter] = useState<PaymentStatusFilter>('active')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [page, setPage] = useState(0)

  const [data, setData] = useState<PaymentOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [actionInvoiceId, setActionInvoiceId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const hasLoadedRef = useRef(false)
  const requestSeqRef = useRef(0)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(searchInput.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const load = useCallback(
    async (manual = false) => {
      const seq = ++requestSeqRef.current
      if (manual || hasLoadedRef.current) setRefreshing(true)
      else setLoading(true)
      setError('')
      try {
        const params = new URLSearchParams({
          period,
          tab,
          status: statusFilter,
          limit: String(PAGE_SIZE),
          offset: String(page * PAGE_SIZE),
        })
        if (debouncedQuery) params.set('q', debouncedQuery)
        const payload = await request<PaymentOverviewResponse>(`/api/admin/payments/overview?${params}`)
        if (seq !== requestSeqRef.current) return
        hasLoadedRef.current = true
        setData(payload)
      } catch (err) {
        if (seq !== requestSeqRef.current) return
        setError(formatError(err))
      } finally {
        if (seq === requestSeqRef.current) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [period, tab, statusFilter, debouncedQuery, page],
  )

  useEffect(() => {
    void load(false)
  }, [load])

  function handlePeriodChange(nextPeriod: PaymentPeriod) {
    setPeriod(nextPeriod)
    setPage(0)
  }

  function handleTabChange(nextTab: PaymentTab) {
    setTab(nextTab)
    setStatusFilter(nextTab === 'all' ? 'active' : 'all')
    setPage(0)
  }

  function handleStatusChange(nextStatus: PaymentStatusFilter) {
    setStatusFilter(nextStatus)
    setPage(0)
  }

  function openProofReview() {
    setPeriod('all')
    setTab('invoices')
    setStatusFilter('pending')
    setPage(0)
  }

  async function copyReference(refId: string) {
    try {
      await navigator.clipboard.writeText(refId)
      setCopiedId(refId)
      window.setTimeout(() => setCopiedId(curr => (curr === refId ? null : curr)), 1600)
    } catch {
      // Clipboard API unavailable
    }
  }

  async function confirmPaid(invoice: InvoicePayload) {
    const confirmation = [
      `Подтвердить фактическое поступление денег по счёту № ${invoice.invoice_number}?`,
      '',
      `На баланс клиента будет зачислено ${formatMoney(invoice.total_credit_rub)}${
        invoice.bonus_rub ? ` (включая бонус ${formatMoney(invoice.bonus_rub)})` : ''
      }.`,
      'Подтверждайте только после сверки с поступлением на расчётный счёт.',
    ].join('\n')
    if (!window.confirm(confirmation)) return

    setActionInvoiceId(invoice.id)
    setError('')
    try {
      await request<{ invoice: InvoicePayload }>(`/api/admin/invoices/${encodeURIComponent(invoice.id)}/mark-paid`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      await load(true)
    } catch (err) {
      setError(formatError(err))
    } finally {
      setActionInvoiceId(null)
    }
  }

  async function closeAlreadyCredited(invoice: InvoicePayload) {
    const confirmation = [
      `Закрыть счёт № ${invoice.invoice_number} без начисления?`,
      '',
      'Используйте это только если баланс клиенту уже начислен вручную другим действием или счёт тестовый.',
      'Эта кнопка не зачисляет сумму и бонус повторно и не добавляет счёт в выручку.',
    ].join('\n')
    if (!window.confirm(confirmation)) return

    setActionInvoiceId(invoice.id)
    setError('')
    try {
      await request<{ invoice: InvoicePayload }>(
        `/api/admin/invoices/${encodeURIComponent(invoice.id)}/close-manually`,
        {
          method: 'POST',
          body: JSON.stringify({ confirm: true }),
        },
      )
      await load(true)
    } catch (err) {
      setError(formatError(err))
    } finally {
      setActionInvoiceId(null)
    }
  }

  const summary = data?.summary
  const items = data?.items || []
  const total = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const tabCounts = data?.tab_counts
  const statusCounts = data?.status_counts

  const statusChips: Array<{ id: PaymentStatusFilter; label: string; count: number; hidden?: boolean }> = [
    { id: 'active', label: 'Актуальные', count: statusCounts?.active ?? 0 },
    {
      id: 'succeeded',
      label: tab === 'manual' ? 'Прямые пополнения' : 'Оплачено',
      count: statusCounts?.succeeded ?? 0,
    },
    {
      id: 'pending',
      label: 'Ожидают',
      count: statusCounts?.pending ?? 0,
      hidden: tab === 'manual',
    },
    {
      id: 'failed',
      label: tab === 'manual' ? 'Возвраты / в счетах' : 'Отменённые / без начисления',
      count: statusCounts?.failed ?? 0,
    },
    { id: 'all', label: 'Все', count: statusCounts?.all ?? 0 },
  ]

  const proofsAllTime = summary?.invoices.proof_submitted_all_time ?? 0
  const openAllTime = summary?.invoices.open_all_time ?? 0

  return (
    <section className="stack invoice-admin-view payments-admin-view">
      <div className="toolbar-panel payments-top-bar">
        <div className="payments-period-group" role="group" aria-label="Период статистики">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.id}
              type="button"
              className={`payments-period-btn${period === opt.id ? ' active' : ''}`}
              onClick={() => handlePeriodChange(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="payments-top-actions">
          {proofsAllTime > 0 ? (
            <button
              type="button"
              className="payments-alert-pill urgent"
              onClick={openProofReview}
              title="Показать счета с прикреплёнными платёжками"
            >
              Платёжек на проверке: {proofsAllTime}
            </button>
          ) : (
            <button
              type="button"
              className="payments-alert-pill neutral"
              onClick={openProofReview}
              title="Показать открытые безналичные счета"
            >
              {openAllTime > 0 ? `Открытых счетов: ${openAllTime}` : 'Нет открытых счетов'}
            </button>
          )}
          <button
            type="button"
            className="secondary small-text"
            onClick={() => void load(true)}
            disabled={refreshing}
          >
            {refreshing ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
            Обновить
          </button>
        </div>
      </div>

      {summary && (
        <div className="payments-kpi-grid">
          <button
            type="button"
            className={`payments-kpi-card highlight${tab === 'all' && statusFilter === 'succeeded' ? ' active' : ''}`}
            onClick={() => {
              setTab('all')
              setStatusFilter('succeeded')
              setPage(0)
            }}
          >
            <div className="payments-kpi-head">
              <span>Выручка (ЮKassa + Счета)</span>
              <Wallet size={16} />
            </div>
            <strong className="payments-kpi-value">{formatMoney(summary.total_revenue_rub)}</strong>
            <small className="payments-kpi-sub">Подтверждённых оплат: {summary.total_paid_count}</small>
          </button>

          <button
            type="button"
            className={`payments-kpi-card${tab === 'yookassa' ? ' active' : ''}`}
            onClick={() => handleTabChange('yookassa')}
          >
            <div className="payments-kpi-head">
              <span>ЮKassa (онлайн)</span>
              <CreditCard size={16} />
            </div>
            <strong className="payments-kpi-value">{formatMoney(summary.yookassa.succeeded_rub)}</strong>
            <small className="payments-kpi-sub">
              Успешно: {summary.yookassa.succeeded_count} · Ждут: {summary.yookassa.pending_count} · Отменено:{' '}
              {summary.yookassa.canceled_count}
            </small>
          </button>

          <button
            type="button"
            className={`payments-kpi-card${tab === 'invoices' ? ' active' : ''}`}
            onClick={() => handleTabChange('invoices')}
          >
            <div className="payments-kpi-head">
              <span>Безналичные счета</span>
              <FileText size={16} />
            </div>
            <strong className="payments-kpi-value">{formatMoney(summary.invoices.paid_rub)}</strong>
            <small className="payments-kpi-sub">
              Оплачено: {summary.invoices.paid_count} · Ждут: {summary.invoices.issued_count}
              {summary.invoices.proof_submitted_count > 0
                ? ` · Платёжек: ${summary.invoices.proof_submitted_count}`
                : ''}
              {summary.invoices.manual_closed_count > 0
                ? ` · Без начисления: ${summary.invoices.manual_closed_count}`
                : ''}
            </small>
          </button>

          <button
            type="button"
            className={`payments-kpi-card muted-card${tab === 'manual' ? ' active' : ''}`}
            onClick={() => handleTabChange('manual')}
          >
            <div className="payments-kpi-head">
              <span>Ручные начисления</span>
              <UserRound size={16} />
            </div>
            <strong className="payments-kpi-value">{formatMoney(summary.manual.direct_rub)}</strong>
            <small className="payments-kpi-sub">
              Прямых: {summary.manual.direct_count} (отдельно от выручки, с бонусами)
            </small>
            {(summary.manual.refund_count > 0 || summary.manual.invoice_linked_count > 0) && (
              <small className="payments-kpi-meta">
                {summary.manual.refund_count > 0 &&
                  `Возвраты: ${formatMoney(summary.manual.refund_rub)} (${summary.manual.refund_count})`}
                {summary.manual.refund_count > 0 && summary.manual.invoice_linked_count > 0 && ' · '}
                {summary.manual.invoice_linked_count > 0 &&
                  `В счетах: ${formatMoney(summary.manual.invoice_linked_rub)} (${summary.manual.invoice_linked_count})`}
              </small>
            )}
          </button>
        </div>
      )}

      <div className="payments-filters-panel">
        <div className="payments-tabs-row">
          <div className="payments-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'all'}
              className={`payments-tab-btn${tab === 'all' ? ' active' : ''}`}
              onClick={() => handleTabChange('all')}
            >
              Все оплаты
              <span className="payments-tab-badge">
                {tab === 'all' ? (tabCounts?.all ?? 0) : (tabCounts?.all_active ?? 0)}
              </span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'yookassa'}
              className={`payments-tab-btn${tab === 'yookassa' ? ' active' : ''}`}
              onClick={() => handleTabChange('yookassa')}
            >
              ЮKassa (онлайн)
              <span className="payments-tab-badge">{tabCounts?.yookassa_total ?? 0}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'invoices'}
              className={`payments-tab-btn${tab === 'invoices' ? ' active' : ''}`}
              onClick={() => handleTabChange('invoices')}
            >
              Счета (безнал)
              <span className="payments-tab-badge">{tabCounts?.invoices_total ?? 0}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'manual'}
              className={`payments-tab-btn${tab === 'manual' ? ' active' : ''}`}
              onClick={() => handleTabChange('manual')}
            >
              Ручные начисления
              <span className="payments-tab-badge">{tabCounts?.manual_total ?? 0}</span>
            </button>
          </div>

          <div className="payments-search-box">
            <Search size={15} className="payments-search-icon" />
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Клиент, #номер, email, ИНН, счёт, ID платежа…"
              aria-label="Поиск по оплатам и счетам"
            />
            {searchInput && (
              <button
                type="button"
                className="payments-search-clear"
                onClick={() => setSearchInput('')}
                aria-label="Очистить поиск"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="payments-status-chips">
          {statusChips
            .filter(chip => !chip.hidden)
            .map(chip => (
              <button
                key={chip.id}
                type="button"
                className={`payments-status-chip${statusFilter === chip.id ? ' active' : ''}`}
                onClick={() => handleStatusChange(chip.id)}
              >
                <span>{chip.label}</span>
                <span className="payments-chip-count">{chip.count}</span>
              </button>
            ))}
        </div>
      </div>

      {error && (
        <div className="alert error">
          <XCircle size={18} />
          {error}
        </div>
      )}

      <div className="table-panel">
        {loading ? (
          <div className="invoice-empty">
            <Loader2 size={20} className="spin" />
            Загружаем счета и оплаты…
          </div>
        ) : items.length === 0 ? (
          <div className="invoice-empty">
            {debouncedQuery
              ? 'По вашему запросу ничего не найдено.'
              : 'За выбранный период и фильтр записей нет.'}
          </div>
        ) : (
          <table className="invoice-table payments-table">
            <thead>
              <tr>
                <th>Операция и дата</th>
                <th>Клиент / Плательщик</th>
                <th>Сумма</th>
                <th>Детали / Платёжка</th>
                <th>Статус</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <PaymentRow
                  key={item.id}
                  item={item}
                  actionInvoiceId={actionInvoiceId}
                  copiedId={copiedId}
                  onCopyRef={copyReference}
                  onOpenClient={onOpenClient}
                  onConfirmPaid={confirmPaid}
                  onCloseManually={closeAlreadyCredited}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!loading && total > 0 && (
        <div className="invoice-pagination">
          <span>
            Показано {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} из {total}
          </span>
          <div>
            <button
              type="button"
              className="secondary small-text"
              disabled={page === 0 || refreshing}
              onClick={() => setPage(current => current - 1)}
            >
              Назад
            </button>
            <span>
              Страница {page + 1} из {pageCount}
            </span>
            <button
              type="button"
              className="secondary small-text"
              disabled={page + 1 >= pageCount || refreshing}
              onClick={() => setPage(current => current + 1)}
            >
              Далее
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
