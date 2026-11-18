import { QuickReplyTemplate } from './types'

export function channelBadgeLabel(channel?: string): string {
  switch (channel) {
    case 'guest_web':
      return '🌐 Сайт'
    case 'web':
      return '🌐 Кабинет'
    case 'tg_bot':
      return '✈️ TG-бот'
    case 'tg_dm':
      return '💬 ЛС бота'
    case 'tg_topic':
      return '🗂 Группа TG'
    case 'admin_web':
      return '🖥 Админка'
    case 'system':
      return '⚙️ Система'
    default:
      return ''
  }
}

export function jobStatusMeta(status?: string): { label: string; bg: string; color: string; border: string } {
  switch (status) {
    case 'completed':
      return { label: 'Готово', bg: '#ecfdf5', color: '#047857', border: '#a7f3d0' }
    case 'partial':
      return { label: 'Частично', bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' }
    case 'running':
      return { label: 'В работе', bg: '#fffbeb', color: '#b45309', border: '#fde68a' }
    case 'pending':
      return { label: 'В очереди', bg: '#f8fafc', color: '#475569', border: '#cbd5e1' }
    case 'failed':
      return { label: 'Ошибка', bg: '#fef2f2', color: '#b91c1c', border: '#fecaca' }
    case 'cancelled':
      return { label: 'Отменено', bg: '#f1f5f9', color: '#64748b', border: '#cbd5e1' }
    case 'awaiting_customer_confirmation':
    case 'awaiting_exact_selection':
    case 'awaiting_position_selection':
      return { label: 'Ждёт клиента', bg: '#fefce8', color: '#a16207', border: '#fef08a' }
    case 'resolved':
      return { label: 'Решено', bg: '#f0fdfa', color: '#0f766e', border: '#99f6e4' }
    default:
      return { label: status || 'Статус', bg: '#f1f5f9', color: '#475569', border: '#e2e8f0' }
  }
}

export function formatDate(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function formatTimeOnly(iso?: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function formatDayKey(iso?: string | null): string {
  if (!iso) return 'unknown'
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return 'unknown'
  }
}

export function formatDayDivider(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const todayKey = formatDayKey(now.toISOString())
    const yesterday = new Date(now.getTime() - 86400000)
    const yesterdayKey = formatDayKey(yesterday.toISOString())
    const targetKey = formatDayKey(iso)
    if (targetKey === todayKey) return 'Сегодня'
    if (targetKey === yesterdayKey) return 'Вчера'
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined })
  } catch {
    return ''
  }
}

export function formatRelativeTime(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'сейчас'
    if (diffMin < 60) return `${diffMin} мин`
    const diffHours = Math.floor(diffMin / 60)
    if (diffHours < 24) return `${diffHours} ч`
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

export function formatMoneyKopeks(kopeks?: number | null): string {
  const rub = Math.round(Number(kopeks || 0) / 100)
  return `${rub.toLocaleString('ru-RU')} ₽`
}

export function formatFileSize(bytes?: number | null): string {
  const size = Number(bytes || 0)
  if (!size) return ''
  if (size < 1024) return `${size} Б`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} КБ`
  return `${(size / (1024 * 1024)).toFixed(1)} МБ`
}

export function isImageFilename(name?: string): boolean {
  if (!name) return false
  return /\.(png|jpe?g|webp|gif)$/i.test(name.trim())
}

export const QUICK_REPLY_TEMPLATES: QuickReplyTemplate[] = [
  {
    id: 'report_ready',
    title: 'Отчёт готов',
    text: 'Добрый день! Подготовили и прикрепили обновлённый отчёт по вашей задаче. Если потребуются уточнения или дополнительные позиции — напишите, пожалуйста, здесь.',
  },
  {
    id: 'need_tz',
    title: 'Уточнить ТЗ',
    text: 'Здравствуйте! Чтобы подобрать максимально точные варианты, уточните, пожалуйста, ключевые требования из ТЗ (или прикрепите исходный документ).',
  },
  {
    id: 'analogs_ready',
    title: 'Аналоги подобраны',
    text: 'Здравствуйте! Подобрали подходящие товары и аналоги с характеристиками и ссылками на производителей. Готовый отчёт в формате Word прикрепили к задаче.',
  },
  {
    id: 'suppliers_extra',
    title: 'Доп. поставщики',
    text: 'Добрый день! Провели дополнительную проверку поставщиков и обновили перечень контактов. Проверьте, пожалуйста, прикреплённый файл.',
  },
  {
    id: 'in_progress',
    title: 'Взяли в работу',
    text: 'Здравствуйте! Передали вашу задачу в экспертную проверку. Как только сформируем итоговый результат — сразу направим его вам в этом чате.',
  },
]
