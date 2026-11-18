import React, { useState, useMemo } from 'react'
import {
  MessageSquare,
  Search,
  RefreshCw,
  CheckCheck,
  Loader2,
  UserPlus,
  X,
} from 'lucide-react'
import { DialogClientCandidate, DialogItem, DialogQueueTab } from './types'
import { channelBadgeLabel, formatRelativeTime } from './constants'

interface DialogSidebarProps {
  dialogs: DialogItem[]
  clients: DialogClientCandidate[]
  loading: boolean
  selectedClientId: string | null
  onSelectClient: (clientId: string) => void
  queueTab: DialogQueueTab
  onQueueTabChange: (tab: DialogQueueTab) => void
  searchQuery: string
  onSearchQueryChange: (q: string) => void
  totalUnread: number
  markingAllRead: boolean
  onMarkAllRead: () => void
  onRefresh: () => void
}

export function DialogSidebar({
  dialogs,
  clients,
  loading,
  selectedClientId,
  onSelectClient,
  queueTab,
  onQueueTabChange,
  searchQuery,
  onSearchQueryChange,
  totalUnread,
  markingAllRead,
  onMarkAllRead,
  onRefresh,
}: DialogSidebarProps) {
  const [showNewDialogPicker, setShowNewDialogPicker] = useState(false)
  const [newDialogSearch, setNewDialogSearch] = useState('')

  const counts = useMemo(() => {
    let needsReply = 0
    let open = 0
    let closed = 0
    let guests = 0
    let blocked = 0
    for (const d of dialogs) {
      if (d.is_blocked || d.dialog_status === 'blocked') {
        blocked++
      } else if (d.dialog_status === 'closed') {
        closed++
      } else {
        open++
      }
      if (d.needs_reply || d.unread_admin_count > 0) needsReply++
      if (d.is_guest) guests++
    }
    return { all: dialogs.length, needsReply, open, closed, guests, blocked }
  }, [dialogs])

  const filteredDialogs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return dialogs.filter(d => {
      if (queueTab === 'needs_reply' && !d.needs_reply && d.unread_admin_count === 0) return false
      if (queueTab === 'open' && (d.is_blocked || d.dialog_status === 'blocked' || d.dialog_status === 'closed')) return false
      if (queueTab === 'closed' && d.dialog_status !== 'closed') return false
      if (queueTab === 'guests' && !d.is_guest) return false
      if (queueTab === 'blocked' && !(d.is_blocked || d.dialog_status === 'blocked')) return false

      if (!q) return true
      const matchesClient =
        d.client_name.toLowerCase().includes(q) ||
        d.client_email.toLowerCase().includes(q) ||
        d.client_phone.toLowerCase().includes(q) ||
        d.last_message.toLowerCase().includes(q) ||
        (d.telegram_id && d.telegram_id.toLowerCase().includes(q)) ||
        (d.client_number && String(d.client_number).includes(q))
      const matchesJobs = d.jobs?.some(
        j => j.job_title.toLowerCase().includes(q) || (j.job_number && String(j.job_number).includes(q))
      )
      return matchesClient || Boolean(matchesJobs)
    })
  }, [dialogs, queueTab, searchQuery])

  const candidateClients = useMemo(() => {
    if (!showNewDialogPicker) return []
    const q = newDialogSearch.trim().toLowerCase()
    return clients
      .filter(c => {
        if (!q) return true
        const email = c.web_users?.[0]?.email || ''
        return (
          (c.name || '').toLowerCase().includes(q) ||
          (c.username || '').toLowerCase().includes(q) ||
          (c.phone || '').toLowerCase().includes(q) ||
          email.toLowerCase().includes(q) ||
          (c.client_number && String(c.client_number).includes(q))
        )
      })
      .slice(0, 20)
  }, [clients, showNewDialogPicker, newDialogSearch])

  const tabs: Array<{ id: DialogQueueTab; label: string; count: number; accent?: string }> = [
    { id: 'all', label: 'Все', count: counts.all },
    { id: 'needs_reply', label: 'Ждут ответа', count: counts.needsReply, accent: counts.needsReply > 0 ? '#ef4444' : undefined },
    { id: 'open', label: 'Открытые', count: counts.open },
    { id: 'closed', label: 'Закрытые', count: counts.closed },
    { id: 'guests', label: 'Гости', count: counts.guests },
    { id: 'blocked', label: 'Блок', count: counts.blocked },
  ]

  return (
    <div
      className="dialogs-sidebar-col"
      style={{
        width: 316,
        minWidth: 260,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        background: '#fff',
        borderRadius: 10,
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
      }}
    >
      {/* Top Bar */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid #f1f5f9', display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13, color: '#0f172a' }}>
            <MessageSquare size={16} color="#0d9488" />
            <span>Очередь диалогов</span>
            {totalUnread > 0 && (
              <span style={{ background: '#ef4444', color: '#fff', fontSize: 10.5, fontWeight: 700, padding: '1px 6px', borderRadius: 10 }}>
                +{totalUnread}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {clients.length > 0 && (
              <button
                type="button"
                onClick={() => setShowNewDialogPicker(v => !v)}
                title="Начать или открыть диалог с любым клиентом"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 7px',
                  minHeight: 26,
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 6,
                  background: showNewDialogPicker ? '#0f766e' : '#f0fdfa',
                  color: showNewDialogPicker ? '#fff' : '#0f766e',
                  border: '1px solid #99f6e4',
                }}
              >
                {showNewDialogPicker ? <X size={12} /> : <UserPlus size={12} />}
                <span>Написать</span>
              </button>
            )}
            <button
              type="button"
              className="ghost"
              onClick={onRefresh}
              disabled={loading}
              title="Обновить список"
              style={{ padding: '4px 6px', minHeight: 26, color: '#64748b' }}
            >
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
            </button>
          </div>
        </div>

        {showNewDialogPicker && (
          <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 8, padding: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#0f172a' }}>Открыть чат с клиентом:</div>
            <input
              type="text"
              placeholder="Имя, #номер, email или телефон..."
              value={newDialogSearch}
              onChange={e => setNewDialogSearch(e.target.value)}
              style={{ fontSize: 11.5, minHeight: 30, padding: '4px 8px' }}
              autoFocus
            />
            <div style={{ maxHeight: 170, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
              {candidateClients.length === 0 ? (
                <div style={{ fontSize: 11, color: '#94a3b8', padding: '6px 4px', textAlign: 'center' }}>Клиенты не найдены</div>
              ) : (
                candidateClients.map(c => {
                  const email = c.web_users?.[0]?.email || ''
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => {
                        onSelectClient(c.id)
                        setShowNewDialogPicker(false)
                        setNewDialogSearch('')
                      }}
                      style={{
                        textAlign: 'left',
                        justifyContent: 'space-between',
                        background: '#fff',
                        color: '#0f172a',
                        border: '1px solid #e2e8f0',
                        borderRadius: 6,
                        padding: '5px 8px',
                        minHeight: 30,
                        fontSize: 11.5,
                        fontWeight: 500,
                      }}
                    >
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.client_number ? `#${c.client_number} ` : ''}
                        <strong>{c.name || 'Без имени'}</strong>
                        {email ? ` · ${email}` : c.username ? ` · @${c.username}` : ''}
                      </span>
                      <span style={{ fontSize: 10.5, color: '#64748b', flexShrink: 0 }}>
                        {c.jobs_count || 0} зад.
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}

        {/* Search box */}
        <div style={{ position: 'relative' }}>
          <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Поиск: клиент, #задача, телефон..."
            value={searchQuery}
            onChange={e => onSearchQueryChange(e.target.value)}
            style={{ width: '100%', minHeight: 32, padding: '5px 26px 5px 28px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 6, background: '#f8fafc' }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchQueryChange('')}
              title="Очистить поиск"
              style={{
                position: 'absolute',
                right: 6,
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                color: '#94a3b8',
                padding: 2,
                minHeight: 'auto',
              }}
            >
              <X size={12} />
            </button>
          )}
        </div>

        {/* Queue tabs */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {tabs.map(t => {
            const active = queueTab === t.id
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onQueueTabChange(t.id)}
                style={{
                  minHeight: 24,
                  padding: '3px 7px',
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 5,
                  border: active ? '1px solid transparent' : '1px solid #e2e8f0',
                  background: active ? (t.accent || '#0d9488') : '#f8fafc',
                  color: active ? '#fff' : '#475569',
                  cursor: 'pointer',
                  gap: 4,
                }}
              >
                <span>{t.label}</span>
                <span style={{ opacity: active ? 0.9 : 0.7, fontSize: 10.5 }}>{t.count}</span>
              </button>
            )
          })}
        </div>

        {totalUnread > 0 && (
          <button
            type="button"
            onClick={onMarkAllRead}
            disabled={markingAllRead}
            title="Отметить все входящие сообщения во всех диалогах как прочитанные"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              width: '100%',
              minHeight: 28,
              padding: '4px 8px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 6,
              border: '1px solid #99f6e4',
              background: '#f0fdfa',
              color: '#0f766e',
              opacity: markingAllRead ? 0.7 : 1,
            }}
          >
            {markingAllRead ? <Loader2 size={12} className="spin" /> : <CheckCheck size={13} />}
            <span>Отметить все прочитанными ({totalUnread})</span>
          </button>
        )}
      </div>

      {/* Scrollable Dialogs List */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        {loading && dialogs.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160, color: '#94a3b8', fontSize: 12, gap: 8 }}>
            <Loader2 size={16} className="spin" />
            <span>Загрузка диалогов...</span>
          </div>
        ) : filteredDialogs.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
            {queueTab !== 'all' || searchQuery ? 'Подходящие диалоги не найдены' : 'Диалогов пока нет'}
          </div>
        ) : (
          filteredDialogs.map(d => {
            const isSelected = d.client_id === selectedClientId
            const jobsCount = d.jobs_count ?? d.jobs?.length ?? 0
            const isClosed = d.dialog_status === 'closed' && !d.is_blocked
            const chLabel = channelBadgeLabel(d.last_channel)
            return (
              <div
                key={d.client_id}
                onClick={() => onSelectClient(d.client_id)}
                style={{
                  padding: '10px 12px',
                  borderBottom: '1px solid #f1f5f9',
                  background: isSelected ? '#f0fdfa' : d.unread_admin_count > 0 ? '#fffbeb' : '#fff',
                  borderLeft: isSelected ? '3px solid #0d9488' : d.unread_admin_count > 0 ? '3px solid #f59e0b' : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'background 0.12s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, marginBottom: 3 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
                    {d.client_number && (
                      <span style={{ fontSize: 10.5, fontWeight: 700, color: '#64748b', flexShrink: 0 }}>
                        #{d.client_number}
                      </span>
                    )}
                    <span
                      style={{
                        fontSize: 12.5,
                        fontWeight: 700,
                        color: isSelected ? '#0f766e' : '#0f172a',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {d.client_name}
                    </span>
                  </div>
                  <span style={{ fontSize: 10.5, color: '#94a3b8', flexShrink: 0 }}>
                    {formatRelativeTime(d.last_message_at)}
                  </span>
                </div>

                {/* Compact single-line status & meta chips */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
                  {d.is_blocked && (
                    <span style={{ fontSize: 10, fontWeight: 700, background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca', padding: '0px 5px', borderRadius: 4 }}>
                      🚫 Блок
                    </span>
                  )}
                  {isClosed && (
                    <span style={{ fontSize: 10, fontWeight: 700, background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', padding: '0px 5px', borderRadius: 4 }}>
                      ✓ Закрыт
                    </span>
                  )}
                  {!d.is_blocked && !isClosed && d.needs_reply && d.unread_admin_count === 0 && (
                    <span style={{ fontSize: 10, fontWeight: 700, background: '#fff7ed', color: '#c2410c', border: '1px solid #fed7aa', padding: '0px 5px', borderRadius: 4 }}>
                      ⏳ Ждёт ответа
                    </span>
                  )}
                  {d.is_guest && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: '#f1f5f9', color: '#475569', padding: '0px 5px', borderRadius: 4 }}>
                      Гость
                    </span>
                  )}
                  {chLabel && (
                    <span style={{ fontSize: 10, color: '#475569', background: '#f8fafc', border: '1px solid #e2e8f0', padding: '0px 5px', borderRadius: 4 }}>
                      {chLabel}
                    </span>
                  )}
                  {jobsCount > 0 && (
                    <span style={{ fontSize: 10, fontWeight: 600, background: '#e0f2fe', color: '#0369a1', padding: '0px 5px', borderRadius: 4 }}>
                      Задач: {jobsCount}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 11.5,
                      color: d.unread_admin_count > 0 ? '#0f172a' : '#64748b',
                      fontWeight: d.unread_admin_count > 0 ? 600 : 400,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      flex: 1,
                    }}
                  >
                    {d.last_sender_role === 'admin' && <span style={{ color: '#0d9488', marginRight: 4 }}>Вы:</span>}
                    {d.last_message || 'Диалог с клиентом'}
                  </p>
                  {d.unread_admin_count > 0 && (
                    <span style={{ background: '#ef4444', color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 99, flexShrink: 0 }}>
                      +{d.unread_admin_count}
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
