import { Check, CheckCircle2, Copy, ExternalLink, FileText, Loader2 } from 'lucide-react'
import {
  formatDateTime,
  formatMoney,
  itemStatusMeta,
  settlementModeLabel,
  sourceMeta,
  type InvoicePayload,
  type PaymentOverviewItem,
} from './types'

type PaymentRowProps = {
  item: PaymentOverviewItem
  actionInvoiceId: string | null
  copiedId: string | null
  onCopyRef: (refId: string) => void
  onOpenClient?: (clientId: string) => void
  onConfirmPaid: (invoice: InvoicePayload) => void
  onCloseManually: (invoice: InvoicePayload) => void
}

export function PaymentRow({
  item,
  actionInvoiceId,
  copiedId,
  onCopyRef,
  onOpenClient,
  onConfirmPaid,
  onCloseManually,
}: PaymentRowProps) {
  const src = sourceMeta(item.source)
  const st = itemStatusMeta(item)
  const inv = item.invoice
  const isWorking = Boolean(inv && actionInvoiceId === inv.id)
  const hasProof = Boolean(
    inv && (inv.status === 'proof_submitted' || inv.proof_status === 'submitted' || inv.proof_submitted_at),
  )
  const isOpenInvoice = Boolean(inv && inv.status !== 'paid' && inv.status !== 'cancelled')

  const displayEmail = item.buyer_email || item.client_email
  const displayPhone = item.client_phone
  const displayTelegram = item.client_telegram

  return (
    <tr className={item.status_group === 'failed' ? 'payments-row-muted' : undefined}>
      <td>
        <div className="payments-op-head">
          <span className={`payments-source-badge ${src.className}`}>{src.label}</span>
          <strong>{item.title}</strong>
          {item.source === 'yookassa' && item.reference_id && (
            <button
              type="button"
              className="payments-copy-btn"
              onClick={() => onCopyRef(item.reference_id)}
              title={`Скопировать ID платежа: ${item.reference_id}`}
            >
              {copiedId === item.reference_id ? <Check size={12} /> : <Copy size={12} />}
            </button>
          )}
        </div>
        <small>{formatDateTime(item.effective_at || item.created_at)}</small>
        {item.tariff_name && <small className="payments-tariff-label">{item.tariff_name}</small>}
      </td>

      <td>
        <div className="payments-client-cell">
          {item.client_exists && item.client_id && onOpenClient ? (
            <button
              type="button"
              className="payments-client-link"
              onClick={() => onOpenClient(item.client_id!)}
              title="Открыть карточку клиента"
            >
              {item.client_number ? `#${item.client_number} ` : ''}
              {item.client_name}
            </button>
          ) : (
            <strong>
              {item.buyer_name || item.client_name}
              {!item.client_exists && <span className="payments-deleted-tag"> (удалён)</span>}
            </strong>
          )}
          {item.source === 'invoice' && item.buyer_name && item.buyer_name !== item.client_name && (
            <small>{item.buyer_name}</small>
          )}
          {item.buyer_inn && (
            <small>
              ИНН {item.buyer_inn}
              {item.buyer_kpp ? ` · КПП ${item.buyer_kpp}` : ''}
            </small>
          )}
          {displayEmail && <small>✉️ {displayEmail}</small>}
          {displayPhone && <small>📞 {displayPhone}</small>}
          {displayTelegram && (
            <small>
              💬{' '}
              <a
                href={`https://t.me/${displayTelegram.replace('@', '')}`}
                target="_blank"
                rel="noreferrer"
                style={{ color: '#0284c7' }}
              >
                @{displayTelegram.replace('@', '')}
              </a>
            </small>
          )}
        </div>
      </td>

      <td>
        <strong className="payments-amount">{formatMoney(item.amount_rub)}</strong>
        {item.source !== 'manual' && item.total_credit_rub !== item.amount_rub && (
          <small>На баланс: {formatMoney(item.total_credit_rub)}</small>
        )}
        {item.bonus_rub > 0 && <small className="payments-bonus">Бонус: +{formatMoney(item.bonus_rub)}</small>}
        {item.source === 'manual' && <small>Зачисление на баланс</small>}
      </td>

      <td>
        {item.source === 'yookassa' && (
          <>
            <span className="payments-method-text">{item.payment_method_label}</span>
            <small className="payments-ref-mono" title={item.reference_id}>
              ID: {item.reference_id}
            </small>
            {item.details_text && <small className="payments-error-note">{item.details_text}</small>}
          </>
        )}

        {item.source === 'invoice' && inv && (
          <>
            {hasProof ? (
              <a
                className="download-pill input-file"
                href={`/api/admin/invoices/${encodeURIComponent(inv.id)}/proof`}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={14} />
                <span>{inv.proof_original_name || 'Открыть платёжку'}</span>
                <ExternalLink size={12} />
              </a>
            ) : (
              <small>Платёжка не прикреплена</small>
            )}
            {inv.proof_submitted_at && <small>Отправлена: {formatDateTime(inv.proof_submitted_at)}</small>}
          </>
        )}

        {item.source === 'manual' && (
          <>
            <small className="payments-manual-note">{item.details_text || 'Без комментария'}</small>
            {item.linked_invoice_number && (
              <small className="payments-linked-tag">Учтено в счёте {item.linked_invoice_number}</small>
            )}
          </>
        )}
      </td>

      <td>
        <span className={`payments-status-pill tone-${st.tone}`}>{st.label}</span>
        {item.source === 'invoice' && item.paid_at && <small>Закрыт: {formatDateTime(item.paid_at)}</small>}
        {item.source === 'invoice' && item.status === 'paid' && (
          <small>{settlementModeLabel(item.settlement_mode)}</small>
        )}
        {item.source === 'yookassa' && item.paid_at && <small>Оплачен: {formatDateTime(item.paid_at)}</small>}
      </td>

      <td>
        {isOpenInvoice && inv ? (
          <div className="invoice-actions">
            <button
              type="button"
              className="button-primary small-text"
              disabled={isWorking}
              onClick={() => onConfirmPaid(inv)}
              title="После сверки поступления на расчётный счёт начислит клиенту сумму счёта и бонус"
            >
              {isWorking ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
              {isWorking ? 'Зачисляем…' : 'Зачислить на баланс'}
            </button>
            <button
              type="button"
              className="secondary small-text"
              disabled={isWorking}
              onClick={() => onCloseManually(inv)}
              title="Закрывает счёт без повторного начисления и без добавления в выручку"
            >
              Закрыть без начисления
            </button>
          </div>
        ) : (
          <div className="invoice-actions">
            {item.source === 'invoice' && item.status === 'paid' && (
              <span className="invoice-confirmed">
                <CheckCircle2 size={15} />
                Закрыт
              </span>
            )}
            {item.client_exists && item.client_id && onOpenClient && (
              <button
                type="button"
                className="secondary small-text"
                onClick={() => onOpenClient(item.client_id!)}
              >
                Клиент
              </button>
            )}
          </div>
        )}
      </td>
    </tr>
  )
}
