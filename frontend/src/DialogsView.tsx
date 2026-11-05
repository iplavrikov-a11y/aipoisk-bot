import React, { useState, useEffect, useRef } from 'react'
import {
  MessageSquare,
  Search,
  Send,
  Paperclip,
  Check,
  CheckCheck,
  ExternalLink,
  User,
  Phone,
  Mail,
  Loader2,
  FileText,
  Download,
  RefreshCw,
  Clock,
  Sparkles,
  Tag,
} from 'lucide-react'

export interface DialogJobSummary {
  job_id: string
  job_number?: number | null
  job_title: string
  job_mode: string
  job_mode_label: string
  job_status: string
}

export interface DialogItem {
  client_id: string
  client_number?: number | null
  client_name: string
  client_email: string
  client_phone: string
  telegram_id: string
  last_message: string
  last_message_at: string | null
  last_sender_role: 'admin' | 'client'
  unread_admin_count: number
  total_messages: number
  jobs: DialogJobSummary[]
  job_id?: string
  job_number?: number | null
  job_title?: string
  job_mode?: string
  job_mode_label?: string
  job_status?: string
}

export interface ChatAttachment {
  index: number
  name: string
  label: string
  size: number
  url: string
  customer_url: string
}

export interface ChatMessage {
  id: string
  job_id: string
  client_id: string
  sender_role: 'admin' | 'client'
  message: string
  attachments: ChatAttachment[]
  is_read_by_client: boolean
  is_read_by_admin: boolean
  created_at: string | null
  job_number?: number | null
  job_title?: string
  job_mode_label?: string
  job_info?: DialogJobSummary | null
}

function formatDate(iso?: string | null): string {
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

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'только что'
    if (diffMin < 60) return `${diffMin} мин. назад`
    const diffHours = Math.floor(diffMin / 60)
    if (diffHours < 24) return `${diffHours} ч. назад`
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}

export function DialogsView({
  onOpenJob,
}: {
  onOpenJob?: (jobId: string) => void
}) {
  const [dialogs, setDialogs] = useState<DialogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterUnread, setFilterUnread] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [activeJobFilter, setActiveJobFilter] = useState<string>('all')

  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([])
  const [clientJobs, setClientJobs] = useState<DialogJobSummary[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [replyJobId, setReplyJobId] = useState<string>('')
  const [files, setFiles] = useState<File[]>([])
  const [notifyTelegram, setNotifyTelegram] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const token = localStorage.getItem('tenderlex_admin_token') || sessionStorage.getItem('tenderlex_admin_token') || ''
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  async function loadDialogs(selectFirst = false) {
    try {
      setLoading(true)
      const res = await fetch('/api/admin/dialogs', { headers: authHeaders })
      if (res.ok) {
        const data = await res.json()
        const list: DialogItem[] = data.dialogs || []
        setDialogs(list)
        if (selectFirst && list.length > 0 && !selectedClientId) {
          setSelectedClientId(list[0].client_id)
        }
      }
    } catch (err) {
      console.error('Failed to load dialogs:', err)
    } finally {
      setLoading(false)
    }
  }

  async function loadChatMessages(clientId: string) {
    try {
      setLoadingMessages(true)
      setError('')
      const res = await fetch(`/api/admin/clients/${clientId}/chat`, { credentials: 'same-origin', headers: authHeaders })
      if (res.ok) {
        const data = await res.json()
        setActiveMessages(data.messages || [])
        const jobs: DialogJobSummary[] = data.jobs || []
        setClientJobs(jobs)
        // Reset reply context or default to latest job
        setReplyJobId(jobs.length > 0 ? jobs[0].job_id : '')
        setActiveJobFilter('all')

        // Update local dialog unread badge to 0
        setDialogs(prev =>
          prev.map(d => (d.client_id === clientId ? { ...d, unread_admin_count: 0 } : d))
        )
      } else {
        const errText = await res.text()
        setError(errText || 'Не удалось загрузить историю переписки')
      }
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки переписки')
    } finally {
      setLoadingMessages(false)
    }
  }

  useEffect(() => {
    loadDialogs(true)
  }, [])

  useEffect(() => {
    if (selectedClientId) {
      loadChatMessages(selectedClientId)
    } else {
      setActiveMessages([])
      setClientJobs([])
    }
  }, [selectedClientId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeMessages, activeJobFilter])

  const selectedDialog = dialogs.find(d => d.client_id === selectedClientId)

  const filteredDialogs = dialogs.filter(d => {
    if (filterUnread && d.unread_admin_count === 0) return false
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    const matchesClient =
      d.client_name.toLowerCase().includes(q) ||
      d.client_email.toLowerCase().includes(q) ||
      d.client_phone.toLowerCase().includes(q) ||
      d.last_message.toLowerCase().includes(q) ||
      (d.client_number && String(d.client_number).includes(q))
    const matchesJobs = d.jobs && d.jobs.some(j =>
      j.job_title.toLowerCase().includes(q) ||
      (j.job_number && String(j.job_number).includes(q))
    )
    return matchesClient || Boolean(matchesJobs)
  })

  // Messages filtered by selected job filter within the thread
  const displayedMessages = activeMessages.filter(m => {
    if (activeJobFilter === 'all') return true
    if (activeJobFilter === 'general') return !m.job_id
    return m.job_id === activeJobFilter
  })

  async function handleSendReply(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (!selectedClientId) return
    const text = replyText.trim()
    if (!text && files.length === 0) return

    setSending(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('message', text)
      formData.append('job_id', replyJobId || '')
      formData.append('notify_telegram', String(notifyTelegram))
      files.forEach(f => formData.append('files', f))
      if (files[0]) formData.append('file', files[0])

      const res = await fetch(`/api/admin/clients/${selectedClientId}/chat`, {
        method: 'POST',
        headers: authHeaders,
        body: formData,
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || 'Ошибка отправки')
      }
      const data = await res.json()
      setActiveMessages(data.messages || [])
      setReplyText('')
      setFiles([])

      // Update dialog snippet in left list
      setDialogs(prev =>
        prev.map(d =>
          d.client_id === selectedClientId
            ? {
                ...d,
                last_message: text || '📎 Прикреплен файл',
                last_sender_role: 'admin',
                last_message_at: new Date().toISOString(),
                total_messages: d.total_messages + 1,
              }
            : d
        )
      )
    } catch (err: any) {
      setError(err.message || 'Не удалось отправить сообщение')
    } finally {
      setSending(false)
    }
  }

  const totalUnread = dialogs.reduce((sum, d) => sum + (d.unread_admin_count || 0), 0)

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 120px)', minHeight: 520, gap: 14, background: '#f8fafc', padding: '12px 14px', borderRadius: 10, border: '1px solid #e2e8f0' }}>
      {/* Left Column: Client Dialogs List */}
      <div style={{ width: 340, minWidth: 300, display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 8, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        {/* Top filter bar */}
        <div style={{ padding: '10px 12px', borderBottom: '1px solid #f1f5f9', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13, color: '#1e293b' }}>
              <MessageSquare size={16} color="#0d9488" />
              <span>Диалоги с клиентами</span>
              {totalUnread > 0 && (
                <span style={{ background: '#ef4444', color: '#fff', fontSize: 10.5, fontWeight: 700, padding: '1px 6px', borderRadius: 10 }}>
                  +{totalUnread}
                </span>
              )}
            </div>
            <button
              type="button"
              className="ghost small-text"
              onClick={() => loadDialogs(false)}
              disabled={loading}
              title="Обновить список"
              style={{ padding: 4, height: 'auto', color: '#64748b' }}
            >
              <RefreshCw size={13} className={loading ? 'spin' : ''} />
            </button>
          </div>

          {/* Search box */}
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Поиск по клиенту, задаче..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: '100%', padding: '6px 8px 6px 26px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 6, background: '#f8fafc' }}
            />
          </div>

          {/* Filter tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => setFilterUnread(false)}
              style={{
                flex: 1,
                fontSize: 11.5,
                fontWeight: 600,
                padding: '4px 8px',
                borderRadius: 5,
                border: 'none',
                background: !filterUnread ? '#0d9488' : '#f1f5f9',
                color: !filterUnread ? '#fff' : '#64748b',
                cursor: 'pointer',
              }}
            >
              Все ({dialogs.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterUnread(true)}
              style={{
                flex: 1,
                fontSize: 11.5,
                fontWeight: 600,
                padding: '4px 8px',
                borderRadius: 5,
                border: 'none',
                background: filterUnread ? '#ef4444' : '#f1f5f9',
                color: filterUnread ? '#fff' : '#64748b',
                cursor: 'pointer',
              }}
            >
              Непрочитанные ({totalUnread})
            </button>
          </div>
        </div>

        {/* Scrollable list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading && dialogs.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160, color: '#94a3b8', fontSize: 12, gap: 8 }}>
              <Loader2 size={16} className="spin" />
              <span>Загрузка диалогов...</span>
            </div>
          ) : filteredDialogs.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
              {filterUnread ? 'Нет непрочитанных диалогов' : 'Диалоги не найдены'}
            </div>
          ) : (
            filteredDialogs.map(d => {
              const isSelected = d.client_id === selectedClientId
              return (
                <div
                  key={d.client_id}
                  onClick={() => setSelectedClientId(d.client_id)}
                  style={{
                    padding: '10px 12px',
                    borderBottom: '1px solid #f1f5f9',
                    background: isSelected ? '#f0fdfa' : '#fff',
                    borderLeft: isSelected ? '3px solid #0d9488' : '3px solid transparent',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: isSelected ? '#0f766e' : '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 190 }}>
                      {d.client_name}
                    </span>
                    <span style={{ fontSize: 10.5, color: '#94a3b8', flexShrink: 0 }}>
                      {formatRelativeTime(d.last_message_at)}
                    </span>
                  </div>

                  {/* Client Subtext / Contacts & Job Chips */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
                    {d.client_phone && (
                      <span style={{ fontSize: 10.5, color: '#0f766e', fontWeight: 600, marginRight: 4 }}>
                        {d.client_phone}
                      </span>
                    )}
                    {d.jobs && d.jobs.length > 0 && d.jobs.slice(0, 3).map(j => (
                      <span
                        key={j.job_id}
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          background: '#e0f2fe',
                          color: '#0369a1',
                          padding: '1px 5px',
                          borderRadius: 3,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        #{j.job_number || j.job_id.slice(0, 4)}
                      </span>
                    ))}
                    {d.jobs && d.jobs.length > 3 && (
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        +{d.jobs.length - 3}
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                    <p style={{ margin: 0, fontSize: 11.5, color: d.unread_admin_count > 0 ? '#1e293b' : '#64748b', fontWeight: d.unread_admin_count > 0 ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 240 }}>
                      {d.last_sender_role === 'admin' && <span style={{ color: '#0d9488', marginRight: 4 }}>Вы:</span>}
                      {d.last_message || 'Диалог с клиентом'}
                    </p>
                    {d.unread_admin_count > 0 && (
                      <span style={{ background: '#ef4444', color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 8, flexShrink: 0 }}>
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

      {/* Right Column: Unified Client Dialogue Thread */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 8, border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        {selectedDialog ? (
          <>
            {/* Thread Header */}
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #f1f5f9', background: '#fafafa', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#1e293b' }}>
                    {selectedDialog.client_name}
                  </h4>
                  {selectedDialog.client_number && (
                    <span style={{ background: '#f1f5f9', color: '#475569', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                      Клиент #{selectedDialog.client_number}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4, fontSize: 11, color: '#64748b', flexWrap: 'wrap' }}>
                  {selectedDialog.client_phone && (
                    <a href={`tel:${selectedDialog.client_phone}`} style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#0f766e', textDecoration: 'none', fontWeight: 600 }}>
                      <Phone size={12} />
                      <span>{selectedDialog.client_phone}</span>
                    </a>
                  )}
                  {selectedDialog.client_email && (
                    <a href={`mailto:${selectedDialog.client_email}`} style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#475569', textDecoration: 'none' }}>
                      <Mail size={12} />
                      <span>{selectedDialog.client_email}</span>
                    </a>
                  )}
                  {selectedDialog.telegram_id && (
                    <span style={{ color: '#0284c7' }}>
                      ✈️ {selectedDialog.telegram_id}
                    </span>
                  )}
                </div>
              </div>

              {/* Job filter chips */}
              {clientJobs.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 10.5, color: '#64748b', fontWeight: 600 }}>Фильтр:</span>
                  <button
                    type="button"
                    onClick={() => setActiveJobFilter('all')}
                    style={{
                      border: 'none',
                      fontSize: 10.5,
                      fontWeight: 600,
                      padding: '3px 7px',
                      borderRadius: 4,
                      cursor: 'pointer',
                      background: activeJobFilter === 'all' ? '#0d9488' : '#f1f5f9',
                      color: activeJobFilter === 'all' ? '#fff' : '#475569',
                    }}
                  >
                    Все ({activeMessages.length})
                  </button>
                  {clientJobs.map(j => (
                    <button
                      key={j.job_id}
                      type="button"
                      onClick={() => setActiveJobFilter(j.job_id)}
                      style={{
                        border: 'none',
                        fontSize: 10.5,
                        fontWeight: 600,
                        padding: '3px 7px',
                        borderRadius: 4,
                        cursor: 'pointer',
                        background: activeJobFilter === j.job_id ? '#0284c7' : '#f1f5f9',
                        color: activeJobFilter === j.job_id ? '#fff' : '#475569',
                      }}
                      title={j.job_title}
                    >
                      #{j.job_number || j.job_id.slice(0, 4)}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setActiveJobFilter('general')}
                    style={{
                      border: 'none',
                      fontSize: 10.5,
                      fontWeight: 600,
                      padding: '3px 7px',
                      borderRadius: 4,
                      cursor: 'pointer',
                      background: activeJobFilter === 'general' ? '#64748b' : '#f1f5f9',
                      color: activeJobFilter === 'general' ? '#fff' : '#475569',
                    }}
                  >
                    Общие
                  </button>
                </div>
              )}
            </div>

            {/* Messages Thread */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12, background: '#f8fafc' }}>
              {loadingMessages ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 12, gap: 8 }}>
                  <Loader2 size={16} className="spin" />
                  <span>Загрузка сообщений...</span>
                </div>
              ) : displayedMessages.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 12, gap: 6 }}>
                  <MessageSquare size={28} color="#cbd5e1" />
                  <span>{activeJobFilter !== 'all' ? 'По этой задаче пока нет сообщений.' : 'В диалоге с клиентом пока нет сообщений. Напишите первое сообщение.'}</span>
                </div>
              ) : (
                displayedMessages.map(msg => {
                  const isAdmin = msg.sender_role === 'admin'
                  return (
                    <div
                      key={msg.id}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: isAdmin ? 'flex-end' : 'flex-start',
                        maxWidth: '85%',
                        alignSelf: isAdmin ? 'flex-end' : 'flex-start',
                      }}
                    >
                      {/* Context badge if tied to a job */}
                      {msg.job_id ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3, fontSize: 10, color: '#0369a1', background: '#e0f2fe', padding: '1px 7px', borderRadius: 4, fontWeight: 600 }}>
                          <span>📌 Задача #{msg.job_number || msg.job_id.slice(0, 4)}: {msg.job_title}</span>
                          {onOpenJob && (
                            <button
                              type="button"
                              onClick={() => onOpenJob(msg.job_id)}
                              style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#0284c7', padding: 0, display: 'flex', alignItems: 'center' }}
                              title="Открыть карточку задачи"
                            >
                              <ExternalLink size={10} />
                            </button>
                          )}
                        </div>
                      ) : (
                        <div style={{ marginBottom: 3, fontSize: 10, color: '#64748b', fontWeight: 500 }}>
                          💬 Общий чат поддержки
                        </div>
                      )}

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3, fontSize: 10.5, color: '#64748b' }}>
                        {isAdmin ? (
                          <>
                            <span style={{ fontWeight: 700, color: '#0d9488' }}>Вы (Эксперт TenderLex)</span>
                            <span>·</span>
                            <span>{formatDate(msg.created_at)}</span>
                          </>
                        ) : (
                          <>
                            <span style={{ fontWeight: 700, color: '#1e293b' }}>Клиент ({selectedDialog.client_name})</span>
                            <span>·</span>
                            <span>{formatDate(msg.created_at)}</span>
                          </>
                        )}
                      </div>

                      <div
                        style={{
                          background: isAdmin ? '#f0fdfa' : '#fff',
                          border: isAdmin ? '1px solid #99f6e4' : '1px solid #e2e8f0',
                          borderRadius: isAdmin ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                          padding: '8px 12px',
                          fontSize: 12,
                          color: '#1e293b',
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.5,
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        }}
                      >
                        {msg.message}

                        {/* Attachments */}
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6, borderTop: isAdmin ? '1px solid #ccfbf1' : '1px solid #f1f5f9', paddingTop: 6 }}>
                            {msg.attachments.map(att => (
                              <a
                                key={att.index}
                                href={att.url}
                                target="_blank"
                                rel="noreferrer"
                                download
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 5,
                                  background: isAdmin ? '#ccfbf1' : '#f1f5f9',
                                  color: isAdmin ? '#0f766e' : '#334155',
                                  fontSize: 11,
                                  padding: '3px 8px',
                                  borderRadius: 5,
                                  textDecoration: 'none',
                                  fontWeight: 600,
                                }}
                              >
                                <Download size={11} />
                                <span>{att.name}</span>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Reply Input Form */}
            <form onSubmit={handleSendReply} style={{ padding: '10px 14px', borderTop: '1px solid #e2e8f0', background: '#fff' }}>
              {error && (
                <div style={{ marginBottom: 8, padding: '4px 8px', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', fontSize: 11, borderRadius: 5 }}>
                  {error}
                </div>
              )}

              {/* Task context selector */}
              {clientJobs.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 11, color: '#475569' }}>
                  <span style={{ fontWeight: 600 }}>Контекст ответа:</span>
                  <select
                    value={replyJobId}
                    onChange={e => setReplyJobId(e.target.value)}
                    style={{ fontSize: 11, padding: '3px 6px', borderRadius: 4, border: '1px solid #cbd5e1', background: '#f8fafc', color: '#1e293b' }}
                  >
                    <option value="">Общий диалог (без привязки к задаче)</option>
                    {clientJobs.map(j => (
                      <option key={j.job_id} value={j.job_id}>
                        Задача #{j.job_number || j.job_id.slice(0, 4)}: {j.job_title}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {files.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                  {files.map((f, i) => (
                    <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, background: '#f0fdfa', border: '1px solid #99f6e4', color: '#0f766e', fontSize: 11, padding: '2px 8px', borderRadius: 4 }}>
                      📎 {f.name}
                      <button
                        type="button"
                        onClick={() => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#0f766e', fontWeight: 700, padding: 0 }}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                  <textarea
                    rows={2}
                    value={replyText}
                    onChange={e => setReplyText(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault()
                        handleSendReply()
                      }
                    }}
                    placeholder="Напишите ответ клиенту... (Ctrl+Enter для отправки)"
                    style={{ width: '100%', padding: '8px 10px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 6, resize: 'vertical' }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
                  {selectedDialog.telegram_id && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5, color: '#0284c7', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={notifyTelegram}
                        onChange={e => setNotifyTelegram(e.target.checked)}
                      />
                      <span>Уведомить в Telegram</span>
                    </label>
                  )}

                  <div style={{ display: 'flex', gap: 6 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#64748b', cursor: 'pointer', padding: '5px 8px', border: '1px solid #cbd5e1', borderRadius: 6, background: '#f8fafc' }}>
                      <Paperclip size={13} />
                      <span>Файл</span>
                      <input
                        type="file"
                        multiple
                        style={{ display: 'none' }}
                        accept=".xlsx,.xls,.docx,.doc,.pdf,.zip"
                        onChange={e => {
                          if (e.target.files) {
                            setFiles(Array.from(e.target.files))
                          }
                        }}
                      />
                    </label>

                    <button
                      type="submit"
                      disabled={sending || (!replyText.trim() && files.length === 0)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        background: '#0d9488',
                        color: '#fff',
                        border: 'none',
                        padding: '6px 14px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {sending ? <Loader2 size={13} className="spin" /> : <Send size={13} />}
                      <span>Отправить</span>
                    </button>
                  </div>
                </div>
              </div>
            </form>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13, gap: 8 }}>
            <MessageSquare size={36} color="#cbd5e1" />
            <span>Выберите диалог слева для просмотра и ответа</span>
          </div>
        )}
      </div>
    </div>
  )
}
