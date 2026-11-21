export type PaymentPeriod = 'today' | '7d' | '30d' | 'all'
export type PaymentTab = 'all' | 'yookassa' | 'invoices' | 'manual'
export type PaymentStatusFilter = 'active' | 'all' | 'succeeded' | 'pending' | 'failed'

export type InvoicePayload = {
  id: string
  invoice_number: string
  client_id: string
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
  settlement_mode?: 'credited' | 'manual_closed' | 'manual_grant' | 'admin_grant_sync' | string | null
}

export type PaymentOverviewItem = {
  id: string
  source: 'yookassa' | 'invoice' | 'manual'
  reference_id: string
  title: string
  tariff_name: string
  status: string
  status_group: 'succeeded' | 'pending' | 'failed'
  amount_rub: number
  bonus_rub: number
  total_credit_rub: number
  created_at?: string | null
  paid_at?: string | null
  effective_at?: string | null
  payment_method_type: string
  payment_method_label: string
  details_text: string
  buyer_name: string
  buyer_inn: string
  buyer_kpp: string
  buyer_email: string
  settlement_mode: string
  manual_category: '' | 'direct_topup' | 'refund' | 'invoice_linked'
  linked_invoice_number: string
  client_id: string | null
  client_exists: boolean
  client_number: number | null
  client_name: string
  client_email: string
  client_phone: string
  client_telegram: string
  invoice: InvoicePayload | null
}

export type PaymentOverviewSummary = {
  period: PaymentPeriod
  total_revenue_rub: number
  total_paid_count: number
  yookassa: {
    succeeded_rub: number
    succeeded_count: number
    pending_count: number
    canceled_count: number
  }
  invoices: {
    paid_rub: number
    paid_count: number
    issued_count: number
    proof_submitted_count: number
    manual_closed_count: number
    cancelled_count: number
    proof_submitted_all_time: number
    open_all_time: number
  }
  manual: {
    direct_rub: number
    direct_count: number
    refund_rub: number
    refund_count: number
    invoice_linked_rub: number
    invoice_linked_count: number
    total_rub: number
    total_count: number
  }
}

export type PaymentOverviewResponse = {
  summary: PaymentOverviewSummary
  tab_counts: {
    all: number
    all_active: number
    yookassa: number
    invoices: number
    manual: number
    yookassa_total: number
    invoices_total: number
    manual_total: number
  }
  status_counts: {
    active: number
    all: number
    succeeded: number
    pending: number
    failed: number
  }
  items: PaymentOverviewItem[]
  total: number
  limit: number
  offset: number
}

export const PERIOD_OPTIONS: Array<{ id: PaymentPeriod; label: string }> = [
  { id: 'today', label: 'Сегодня' },
  { id: '7d', label: '7 дней' },
  { id: '30d', label: '30 дней' },
  { id: 'all', label: 'Всё время' },
]

export function formatMoney(value: number): string {
  const num = Number(value || 0)
  const hasFraction = Math.abs(num - Math.trunc(num)) > 0.001
  return (
    num.toLocaleString('ru-RU', {
      minimumFractionDigits: hasFraction ? 2 : 0,
      maximumFractionDigits: hasFraction ? 2 : 0,
    }) + ' ₽'
  )
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString('ru-RU')
}

export function settlementModeLabel(mode?: string | null): string {
  switch ((mode || '').trim().toLowerCase()) {
    case 'credited':
      return 'Зачислено через счёт'
    case 'manual_grant':
      return 'Оплачен (начислено вручную)'
    case 'admin_grant_sync':
      return 'Оплачен (синхр. с ручным начислением)'
    case 'manual_closed':
      return 'Закрыт без начисления (не в выручке)'
    default:
      return 'Оплачен'
  }
}

export function itemStatusMeta(item: PaymentOverviewItem): { label: string; tone: 'success' | 'warning' | 'info' | 'muted' } {
  if (item.source === 'yookassa') {
    if (item.status === 'succeeded') return { label: 'Оплачен', tone: 'success' }
    if (item.status === 'pending' || item.status === 'waiting_for_capture') {
      return { label: 'Ожидает оплаты', tone: 'warning' }
    }
    return { label: 'Отменён', tone: 'muted' }
  }
  if (item.source === 'invoice') {
    if (item.status === 'paid') {
      if (item.settlement_mode === 'manual_closed') {
        return { label: 'Закрыт без начисления', tone: 'muted' }
      }
      return { label: 'Оплачен', tone: 'success' }
    }
    if (item.status === 'proof_submitted') return { label: 'Платёжка на проверке', tone: 'info' }
    if (item.status === 'issued') return { label: 'Ожидает оплаты', tone: 'warning' }
    return { label: 'Отменён', tone: 'muted' }
  }
  if (item.manual_category === 'refund') return { label: 'Возврат на баланс', tone: 'muted' }
  if (item.manual_category === 'invoice_linked') return { label: 'Учтён в счёте', tone: 'info' }
  return { label: 'Зачислено вручную', tone: 'success' }
}

export function sourceMeta(source: PaymentOverviewItem['source']): { label: string; className: string } {
  if (source === 'yookassa') return { label: 'ЮKassa', className: 'source-yookassa' }
  if (source === 'invoice') return { label: 'Счёт', className: 'source-invoice' }
  return { label: 'Вручную', className: 'source-manual' }
}
