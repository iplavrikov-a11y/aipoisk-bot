import React, { useState, useMemo, useRef, useEffect } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  MessageSquare,
  Send,
  Paperclip,
  Check,
  CheckCheck,
  Ban,
  ShieldCheck,
  ExternalLink,
  Loader2,
  Download,
  ChevronDown,
  Search,
  X,
  PanelRightOpen,
  PanelRightClose,
  CheckCircle2,
  RotateCcw,
  Sparkles,
  FolderOpen,
  CornerDownLeft,
} from 'lucide-react'
import {
  ChatMessage,
  DialogClientProfile,
  DialogItem,
  DialogJobSummary,
  PendingJobFileAttachment,
} from './types'
import {
  QUICK_REPLY_TEMPLATES,
  channelBadgeLabel,
  formatDayDivider,
  formatDayKey,
  formatFileSize,
  formatTimeOnly,
  isAiAutoReplyMessage,
  isImageFilename,
  jobStatusMeta,
  stripAiRobotPrefix,
} from './constants'

interface DialogThreadProps {
  selectedDialog: DialogItem | null
  clientProfile: DialogClientProfile | null
  messages: ChatMessage[]
  clientJobs: DialogJobSummary[]
  generalMessagesCount: number
  loadingMessages: boolean
  activeJobFilter: string
  onJobFilterChange: (jobId: string) => void
  replyJobId: string
  onReplyJobIdChange: (jobId: string) => void
  replyText: string
  onReplyTextChange: (text: string) => void
  files: File[]
  onFilesChange: React.Dispatch<React.SetStateAction<File[]>>
  pendingJobFiles: PendingJobFileAttachment[]
  onRemovePendingJobFile: (index: number) => void
  onAddPendingJobFile: (item: PendingJobFileAttachment) => void
  notifyTelegram: boolean
  onNotifyTelegramChange: (val: boolean) => void
  sending: boolean
  error: string
  blockingAction: boolean
  statusActionLoading: boolean
  onToggleBlock: () => void
  onCloseOrReopen: () => void
  onSendReply: (e?: React.FormEvent) => void
  onOpenJob?: (jobId: string, clientId?: string, jobNumber?: number | null) => void
  showContextPanel: boolean
  onToggleContextPanel: () => void
  onBackToList?: () => void
  composerRef?: React.RefObject<HTMLTextAreaElement | null>
}

export function DialogThread({
  selectedDialog,
  clientProfile,
  messages,
  clientJobs,
  generalMessagesCount,
  loadingMessages,
  activeJobFilter,
  onJobFilterChange,
  replyJobId,
  onReplyJobIdChange,
  replyText,
  onReplyTextChange,
  files,
  onFilesChange,
  pendingJobFiles,
  onRemovePendingJobFile,
  onAddPendingJobFile,
  notifyTelegram,
  onNotifyTelegramChange,
  sending,
  error,
  blockingAction,
  statusActionLoading,
  onToggleBlock,
  onCloseOrReopen,
  onSendReply,
  onOpenJob,
  showContextPanel,
  onToggleContextPanel,
  onBackToList,
  composerRef,
}: DialogThreadProps) {
  const [filterDropdownOpen, setFilterDropdownOpen] = useState(false)
  const [filterSearch, setFilterSearch] = useState('')
  const [templatesOpen, setTemplatesOpen] = useState(false)
  const [jobFilesPickerOpen, setJobFilesPickerOpen] = useState(false)
  const [jobFilesSearch, setJobFilesSearch] = useState('')

  const filterRef = useRef<HTMLDivElement>(null)
  const quickToolsRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const lastScrollKeyRef = useRef('')

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      const target = e.target as Node
      if (filterDropdownOpen && filterRef.current && !filterRef.current.contains(target)) {
        setFilterDropdownOpen(false)
      }
      if ((templatesOpen || jobFilesPickerOpen) && quickToolsRef.current && !quickToolsRef.current.contains(target)) {
        setTemplatesOpen(false)
        setJobFilesPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [filterDropdownOpen, templatesOpen, jobFilesPickerOpen])

  const displayedMessages = useMemo(() => {
    return messages.filter(m => {
      if (activeJobFilter === 'all') return true
      if (activeJobFilter === 'general') return !m.job_id
      return m.job_id === activeJobFilter
    })
  }, [messages, activeJobFilter])

  const clientId = clientProfile?.id || selectedDialog?.client_id || ''

  useEffect(() => {
    const lastId = displayedMessages.length > 0 ? displayedMessages[displayedMessages.length - 1].id : ''
    const scrollKey = `${clientId}:${activeJobFilter}:${lastId}:${displayedMessages.length}`
    if (scrollKey === lastScrollKeyRef.current) return
    const prevClient = lastScrollKeyRef.current.split(':')[0]
    lastScrollKeyRef.current = scrollKey
    if (displayedMessages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: prevClient === clientId ? 'smooth' : 'auto' })
    }
  }, [clientId, activeJobFilter, displayedMessages])

  const jobsById = useMemo(() => {
    const map = new Map<string, DialogJobSummary>()
    for (const j of clientJobs) map.set(j.job_id, j)
    return map
  }, [clientJobs])

  const sortedJobsForDropdown = useMemo(() => {
    const q = filterSearch.trim().toLowerCase()
    const filtered = clientJobs.filter(j => {
      if (!q) return true
      return (
        j.job_title.toLowerCase().includes(q) ||
        j.job_mode_label.toLowerCase().includes(q) ||
        (j.job_number && String(j.job_number).includes(q))
      )
    })
    const withChat = filtered.filter(j => (j.chat_messages_count || 0) > 0)
    const withoutChat = filtered.filter(j => !(j.chat_messages_count || 0))
    return { withChat, withoutChat: withoutChat.slice(0, q ? 40 : 25), totalMatches: filtered.length }
  }, [clientJobs, filterSearch])

  const jobsWithResultFiles = useMemo(() => {
    const q = jobFilesSearch.trim().toLowerCase()
    return clientJobs
      .filter(j => (j.result_files && j.result_files.length > 0) || (j.rerun_files && j.rerun_files.length > 0))
      .filter(j => {
        if (!q) return true
        return (
          j.job_title.toLowerCase().includes(q) ||
          (j.job_number && String(j.job_number).includes(q))
        )
      })
      .slice(0, 20)
  }, [clientJobs, jobFilesSearch])

  // Prioritize jobs with chat messages + current replyJobId + latest 30 jobs in reply select
  const replySelectJobs = useMemo(() => {
    const withChat = clientJobs.filter(j => (j.chat_messages_count || 0) > 0)
    const seen = new Set(withChat.map(j => j.job_id))
    const extra: DialogJobSummary[] = []
    if (replyJobId && !seen.has(replyJobId)) {
      const target = jobsById.get(replyJobId)
      if (target) {
        extra.push(target)
        seen.add(target.job_id)
      }
    }
    for (const j of clientJobs) {
      if (!seen.has(j.job_id)) {
        extra.push(j)
        seen.add(j.job_id)
        if (withChat.length + extra.length >= 35) break
      }
    }
    return { withChat, recent: extra }
  }, [clientJobs, replyJobId, jobsById])

  if (!selectedDialog && !clientProfile) {
    return (
      <div
        className="dialogs-thread-col"
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          background: '#fff',
          borderRadius: 10,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
        }}
      >
        {onBackToList && (
          <div style={{ padding: '8px 12px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', flexShrink: 0 }}>
            <button
              type="button"
              className="ghost dialogs-mobile-back-btn"
              onClick={onBackToList}
              style={{ minHeight: 32, padding: '4px 10px', fontSize: 12, fontWeight: 600 }}
            >
              <ArrowLeft size={14} />
              <span>Диалоги</span>
            </button>
          </div>
        )}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#94a3b8',
            fontSize: 13,
            gap: 10,
            padding: 24,
          }}
        >
          {loadingMessages ? (
            <>
              <Loader2 size={28} className="spin" color="#0d9488" />
              <div style={{ fontWeight: 600, color: '#475569' }}>Загрузка переписки…</div>
            </>
          ) : error ? (
            <>
              <AlertTriangle size={32} color="#dc2626" />
              <div style={{ fontWeight: 600, color: '#991b1b', textAlign: 'center' }}>{error}</div>
            </>
          ) : (
            <>
              <MessageSquare size={40} color="#cbd5e1" />
              <div style={{ fontWeight: 600, color: '#475569' }}>Выберите диалог в очереди слева</div>
              <div style={{ fontSize: 12, textAlign: 'center', maxWidth: 340 }}>
                Вся переписка по задачам, результаты и карточка клиента откроются здесь в едином окне.
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  const name = clientProfile?.name || selectedDialog?.client_name || 'Клиент'
  const clientNum = clientProfile?.number ?? selectedDialog?.client_number
  const isGuest = Boolean(clientProfile?.is_guest ?? selectedDialog?.is_guest)
  const isBlocked = Boolean(clientProfile?.is_blocked ?? selectedDialog?.is_blocked)
  const dialogStatus = clientProfile?.dialog_status || selectedDialog?.dialog_status || (isBlocked ? 'blocked' : 'open')
  const isClosed = dialogStatus === 'closed' && !isBlocked
  const telegramId = clientProfile?.telegram_id || selectedDialog?.telegram_id || ''

  const activeFilterJob = activeJobFilter !== 'all' && activeJobFilter !== 'general' ? jobsById.get(activeJobFilter) : null
  const activeFilterLabel =
    activeJobFilter === 'all'
      ? `Вся переписка (${messages.length})`
      : activeJobFilter === 'general'
        ? `Общий чат (${generalMessagesCount})`
        : activeFilterJob
          ? `Задача #${activeFilterJob.job_number || activeFilterJob.job_id.slice(0, 5)}: ${activeFilterJob.job_title}`
          : 'Фильтр по задаче'

  // Group messages with day separators
  let lastDayKey = ''

  return (
    <div
      className="dialogs-thread-col"
      style={{
        flex: 1,
        minWidth: 0,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        background: '#fff',
        borderRadius: 10,
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
      }}
    >
      {/* Compact Fixed Header */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid #e2e8f0', background: '#fafafa', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* Row 1: Identity + Lifecycle Actions */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0, flexWrap: 'wrap' }}>
            {onBackToList && (
              <button
                type="button"
                className="ghost dialogs-mobile-back-btn"
                onClick={onBackToList}
                title="Вернуться к списку диалогов"
                style={{ minHeight: 30, padding: '3px 9px', fontSize: 12, fontWeight: 600 }}
              >
                <ArrowLeft size={14} />
                <span>Диалоги</span>
              </button>
            )}
            <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: '#0f172a' }}>
              {name}
            </h4>
            {clientNum && (
              <span style={{ background: '#f1f5f9', color: '#475569', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                #{clientNum}
              </span>
            )}
            {isGuest && (
              <span style={{ background: '#e0f2fe', color: '#0369a1', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                Гость сайта
              </span>
            )}
            {isBlocked ? (
              <span style={{ background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                Заблокирован
              </span>
            ) : isClosed ? (
              <span style={{ background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                Закрыт
              </span>
            ) : (
              <span style={{ background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0', fontSize: 11, fontWeight: 700, padding: '1px 6px', borderRadius: 4 }}>
                Открыт
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {!isBlocked && (
              <button
                type="button"
                onClick={onCloseOrReopen}
                disabled={statusActionLoading}
                style={{
                  minHeight: 28,
                  padding: '3px 9px',
                  fontSize: 11.5,
                  fontWeight: 600,
                  borderRadius: 6,
                  background: isClosed ? '#0d9488' : '#fff',
                  color: isClosed ? '#fff' : '#0f766e',
                  border: isClosed ? '1px solid #0d9488' : '1px solid #99f6e4',
                }}
                title={isClosed ? 'Вернуть диалог в открытые' : 'Отметить вопрос решённым и закрыть диалог'}
              >
                {statusActionLoading ? (
                  <Loader2 size={12} className="spin" />
                ) : isClosed ? (
                  <RotateCcw size={12} />
                ) : (
                  <CheckCircle2 size={12} />
                )}
                <span>{isClosed ? 'Вернуть в работу' : 'Решено'}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onToggleBlock}
              disabled={blockingAction}
              style={{
                minHeight: 28,
                padding: '3px 9px',
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 6,
                border: isBlocked ? '1px solid #86efac' : '1px solid #fecaca',
                background: isBlocked ? '#f0fdf4' : '#fef2f2',
                color: isBlocked ? '#15803d' : '#dc2626',
              }}
              title={isBlocked ? 'Снять блокировку пользователя' : 'Заблокировать пользователя'}
            >
              {blockingAction ? (
                <Loader2 size={12} className="spin" />
              ) : isBlocked ? (
                <ShieldCheck size={12} />
              ) : (
                <Ban size={12} />
              )}
              <span>{isBlocked ? 'Разблокировать' : 'Заблокировать'}</span>
            </button>

            <button
              type="button"
              onClick={onToggleContextPanel}
              className="ghost"
              style={{
                minHeight: 28,
                padding: '3px 9px',
                fontSize: 11.5,
                fontWeight: 600,
              }}
              title={showContextPanel ? 'Скрыть панель клиента и задач' : 'Показать панель клиента и задач'}
            >
              {showContextPanel ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
              <span>Задачи ({clientJobs.length})</span>
            </button>
          </div>
        </div>

        {/* Row 2: Compact Searchable Job Filter (NEVER wraps into 20 rows!) */}
        {!isGuest && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div ref={filterRef} style={{ position: 'relative', flex: '1 1 260px', maxWidth: 540 }}>
              <button
                type="button"
                onClick={() => setFilterDropdownOpen(v => !v)}
                style={{
                  width: '100%',
                  minHeight: 30,
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: activeJobFilter !== 'all' ? '1px solid #0284c7' : '1px solid #cbd5e1',
                  background: activeJobFilter !== 'all' ? '#f0f9ff' : '#fff',
                  color: activeJobFilter !== 'all' ? '#0369a1' : '#334155',
                  fontSize: 12,
                  fontWeight: 600,
                  justifyContent: 'space-between',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {activeFilterLabel}
                </span>
                <ChevronDown size={14} style={{ flexShrink: 0 }} />
              </button>

              {filterDropdownOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 4px)',
                    left: 0,
                    right: 0,
                    zIndex: 40,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    borderRadius: 8,
                    boxShadow: '0 10px 25px rgba(15, 23, 42, 0.14)',
                    padding: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    maxHeight: 360,
                  }}
                >
                  <div style={{ position: 'relative' }}>
                    <Search size={12} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                    <input
                      type="text"
                      placeholder="Найти задачу по #номеру или названию..."
                      value={filterSearch}
                      onChange={e => setFilterSearch(e.target.value)}
                      style={{ minHeight: 28, padding: '4px 8px 4px 26px', fontSize: 11.5 }}
                      autoFocus
                    />
                  </div>

                  <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <button
                      type="button"
                      onClick={() => {
                        onJobFilterChange('all')
                        setFilterDropdownOpen(false)
                      }}
                      style={{
                        justifyContent: 'space-between',
                        textAlign: 'left',
                        minHeight: 28,
                        padding: '4px 8px',
                        fontSize: 11.5,
                        borderRadius: 5,
                        background: activeJobFilter === 'all' ? '#0d9488' : '#f8fafc',
                        color: activeJobFilter === 'all' ? '#fff' : '#0f172a',
                      }}
                    >
                      <span>Вся переписка с клиентом</span>
                      <span style={{ fontSize: 10.5, opacity: 0.8 }}>{messages.length}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        onJobFilterChange('general')
                        setFilterDropdownOpen(false)
                      }}
                      style={{
                        justifyContent: 'space-between',
                        textAlign: 'left',
                        minHeight: 28,
                        padding: '4px 8px',
                        fontSize: 11.5,
                        borderRadius: 5,
                        background: activeJobFilter === 'general' ? '#475569' : '#f8fafc',
                        color: activeJobFilter === 'general' ? '#fff' : '#334155',
                      }}
                    >
                      <span>💬 Общий чат (без задачи)</span>
                      <span style={{ fontSize: 10.5, opacity: 0.8 }}>{generalMessagesCount}</span>
                    </button>

                    {sortedJobsForDropdown.withChat.length > 0 && (
                      <>
                        <div style={{ fontSize: 10, fontWeight: 700, color: '#0f766e', padding: '6px 6px 2px', textTransform: 'uppercase' }}>
                          Задачи с перепиской ({sortedJobsForDropdown.withChat.length})
                        </div>
                        {sortedJobsForDropdown.withChat.map(j => {
                          const st = jobStatusMeta(j.job_status)
                          const selected = activeJobFilter === j.job_id
                          return (
                            <button
                              key={j.job_id}
                              type="button"
                              onClick={() => {
                                onJobFilterChange(j.job_id)
                                onReplyJobIdChange(j.job_id)
                                setFilterDropdownOpen(false)
                              }}
                              style={{
                                justifyContent: 'space-between',
                                textAlign: 'left',
                                minHeight: 30,
                                padding: '5px 8px',
                                fontSize: 11.5,
                                borderRadius: 5,
                                background: selected ? '#0284c7' : '#f0fdfa',
                                color: selected ? '#fff' : '#0f172a',
                                gap: 8,
                              }}
                            >
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                <strong>#{j.job_number || j.job_id.slice(0, 4)}</strong> · {j.job_title}
                              </span>
                              <span style={{ fontSize: 10, flexShrink: 0, opacity: selected ? 0.95 : 0.8 }}>
                                {st.label} · 💬 {j.chat_messages_count}
                              </span>
                            </button>
                          )
                        })}
                      </>
                    )}

                    {sortedJobsForDropdown.withoutChat.length > 0 && (
                      <>
                        <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', padding: '6px 6px 2px', textTransform: 'uppercase' }}>
                          Другие задачи ({sortedJobsForDropdown.withoutChat.length} из {clientJobs.length})
                        </div>
                        {sortedJobsForDropdown.withoutChat.map(j => {
                          const st = jobStatusMeta(j.job_status)
                          const selected = activeJobFilter === j.job_id
                          return (
                            <button
                              key={j.job_id}
                              type="button"
                              onClick={() => {
                                onJobFilterChange(j.job_id)
                                onReplyJobIdChange(j.job_id)
                                setFilterDropdownOpen(false)
                              }}
                              style={{
                                justifyContent: 'space-between',
                                textAlign: 'left',
                                minHeight: 28,
                                padding: '4px 8px',
                                fontSize: 11.5,
                                borderRadius: 5,
                                background: selected ? '#0284c7' : 'transparent',
                                color: selected ? '#fff' : '#334155',
                                gap: 8,
                              }}
                            >
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                <strong>#{j.job_number || j.job_id.slice(0, 4)}</strong> · {j.job_title}
                              </span>
                              <span style={{ fontSize: 10, color: selected ? '#fff' : st.color, flexShrink: 0 }}>
                                {st.label}
                              </span>
                            </button>
                          )
                        })}
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {activeJobFilter !== 'all' && (
              <button
                type="button"
                onClick={() => onJobFilterChange('all')}
                className="ghost"
                style={{ minHeight: 28, padding: '2px 8px', fontSize: 11, color: '#475569' }}
              >
                <X size={12} />
                <span>Показать всю историю</span>
              </button>
            )}

            {activeFilterJob && onOpenJob && (
              <button
                type="button"
                onClick={() => onOpenJob(activeFilterJob.job_id, clientId, activeFilterJob.job_number)}
                className="ghost"
                style={{ minHeight: 28, padding: '2px 8px', fontSize: 11, color: '#0369a1' }}
              >
                <ExternalLink size={12} />
                <span>Открыть задачу #{activeFilterJob.job_number}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {isBlocked && (
        <div style={{ padding: '7px 14px', background: '#fef2f2', borderBottom: '1px solid #fecaca', color: '#991b1b', fontSize: 11.5, display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <Ban size={13} />
          <span>Пользователь заблокирован: отправка сообщений с сайта, вход в кабинет и обращения в бота ограничены.</span>
        </div>
      )}

      {/* Scrollable Messages Timeline */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10, background: '#f8fafc' }}>
        {loadingMessages ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 12, gap: 8 }}>
            <Loader2 size={16} className="spin" />
            <span>Загрузка истории переписки...</span>
          </div>
        ) : displayedMessages.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 12.5, gap: 8, textAlign: 'center' }}>
            <MessageSquare size={32} color="#cbd5e1" />
            <span>
              {activeJobFilter !== 'all'
                ? 'По выбранному фильтру пока нет сообщений.'
                : 'Переписка с клиентом ещё не начата. Напишите первое сообщение ниже.'}
            </span>
          </div>
        ) : (
          displayedMessages.map(msg => {
            const dayKey = formatDayKey(msg.created_at)
            const showDayDivider = dayKey !== lastDayKey
            lastDayKey = dayKey

            const isAiAuto = isAiAutoReplyMessage(msg.channel, msg.message)
            const isSystem = msg.channel === 'system' && !isAiAuto
            const isAdmin = msg.sender_role === 'admin' || isAiAuto
            const displayMessage = isAiAuto ? stripAiRobotPrefix(msg.message) : msg.message
            const linkedJob = msg.job_id ? jobsById.get(msg.job_id) : undefined
            const jobStatus = linkedJob ? jobStatusMeta(linkedJob.job_status) : null

            return (
              <React.Fragment key={msg.id}>
                {showDayDivider && msg.created_at && (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '4px 0' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 600, color: '#64748b', background: '#e2e8f0', padding: '2px 10px', borderRadius: 99 }}>
                      {formatDayDivider(msg.created_at)}
                    </span>
                  </div>
                )}

                {isSystem ? (
                  <div style={{ display: 'flex', justifyContent: 'center', margin: '2px 0' }}>
                    <div style={{ fontSize: 11, color: '#475569', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: 8, padding: '5px 12px', maxWidth: '80%', textAlign: 'center' }}>
                      ⚙️ {msg.message} · <span style={{ color: '#94a3b8' }}>{formatTimeOnly(msg.created_at)}</span>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: isAdmin ? 'flex-end' : 'flex-start',
                      maxWidth: '82%',
                      alignSelf: isAdmin ? 'flex-end' : 'flex-start',
                    }}
                  >
                    {/* Context Pill */}
                    {msg.job_id ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3, fontSize: 10.5, color: '#0369a1', background: '#e0f2fe', padding: '2px 8px', borderRadius: 5, fontWeight: 600, maxWidth: '100%' }}>
                        <span
                          onClick={() => onJobFilterChange(activeJobFilter === msg.job_id ? 'all' : msg.job_id)}
                          style={{ cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title="Нажмите, чтобы отфильтровать чат по этой задаче"
                        >
                          📌 #{msg.job_number || msg.job_id.slice(0, 4)} · {msg.job_title || linkedJob?.job_title || 'Задача'}
                        </span>
                        {jobStatus && (
                          <span style={{ fontSize: 9.5, background: jobStatus.bg, color: jobStatus.color, border: `1px solid ${jobStatus.border}`, padding: '0 4px', borderRadius: 3, flexShrink: 0 }}>
                            {jobStatus.label}
                          </span>
                        )}
                        {onOpenJob && (
                          <button
                            type="button"
                            onClick={() => onOpenJob(msg.job_id, clientId, msg.job_number)}
                            style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#0284c7', padding: 0, minHeight: 'auto', flexShrink: 0 }}
                            title="Открыть в разделе «Задачи»"
                          >
                            <ExternalLink size={11} />
                          </button>
                        )}
                      </div>
                    ) : null}

                    <div
                      style={{
                        background: isAiAuto ? '#eef2ff' : isAdmin ? '#f0fdfa' : '#fff',
                        border: isAiAuto ? '1px solid #c7d2fe' : isAdmin ? '1px solid #99f6e4' : '1px solid #e2e8f0',
                        borderRadius: isAdmin ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                        padding: '9px 13px',
                        fontSize: 12.5,
                        color: '#0f172a',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        lineHeight: 1.5,
                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
                      }}
                    >
                      {isAiAuto && (
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, marginBottom: 6, fontSize: 10.5, fontWeight: 700, color: '#3730a3', background: '#e0e7ff', border: '1px solid #c7d2fe', padding: '1px 8px', borderRadius: 99 }}>
                          🤖 ИИ-автоответ · отправлен клиенту
                        </div>
                      )}
                      <div>{displayMessage}</div>

                      {msg.attachments && msg.attachments.length > 0 && (
                        <div style={{ marginTop: msg.message ? 8 : 0, display: 'flex', flexDirection: 'column', gap: 6, borderTop: msg.message ? (isAdmin ? '1px solid #ccfbf1' : '1px solid #f1f5f9') : 'none', paddingTop: msg.message ? 7 : 0 }}>
                          {msg.attachments.map(att => (
                            <div key={att.index} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {isImageFilename(att.name) && (
                                <a href={att.url} target="_blank" rel="noreferrer">
                                  <img
                                    src={att.url}
                                    alt={att.name}
                                    style={{ maxWidth: 260, maxHeight: 180, borderRadius: 6, border: '1px solid #cbd5e1', display: 'block' }}
                                  />
                                </a>
                              )}
                              <a
                                href={att.url}
                                target="_blank"
                                rel="noreferrer"
                                download
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  background: isAdmin ? '#ccfbf1' : '#f1f5f9',
                                  color: isAdmin ? '#0f766e' : '#334155',
                                  fontSize: 11,
                                  padding: '4px 9px',
                                  borderRadius: 6,
                                  textDecoration: 'none',
                                  fontWeight: 600,
                                  width: 'fit-content',
                                }}
                              >
                                <Download size={12} />
                                <span>{att.name}</span>
                                {att.size ? <span style={{ opacity: 0.7, fontWeight: 500 }}>({formatFileSize(att.size)})</span> : null}
                              </a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Footer meta row */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3, fontSize: 10.5, color: '#64748b', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, color: isAiAuto ? '#4f46e5' : isAdmin ? '#0d9488' : '#334155' }}>
                        {isAiAuto ? 'ИИ-помощник' : isAdmin ? 'Вы' : name}
                      </span>
                      {(isAiAuto || (msg.channel && channelBadgeLabel(msg.channel))) && (
                        <span style={{ fontSize: 10, color: isAiAuto ? '#3730a3' : '#475569', background: isAiAuto ? '#eef2ff' : '#f1f5f9', padding: '0 5px', borderRadius: 4 }}>
                          {isAiAuto ? '🤖 Автоответ' : channelBadgeLabel(msg.channel)}
                        </span>
                      )}
                      <span>{formatTimeOnly(msg.created_at)}</span>
                      {isAdmin && (
                        <span
                          title={
                            isAiAuto
                              ? 'Автоответ доставлен клиенту в виджет чата'
                              : msg.is_read_by_client
                                ? 'Прочитано клиентом'
                                : 'Отправлено (ещё не прочитано клиентом)'
                          }
                          style={{ display: 'inline-flex', alignItems: 'center', color: isAiAuto ? '#4f46e5' : msg.is_read_by_client ? '#0d9488' : '#94a3b8' }}
                        >
                          {msg.is_read_by_client ? <CheckCheck size={12} /> : <Check size={12} />}
                        </span>
                      )}
                      {!isAdmin && msg.job_id && (
                        <button
                          type="button"
                          onClick={() => {
                            onReplyJobIdChange(msg.job_id)
                            composerRef?.current?.focus()
                          }}
                          style={{
                            minHeight: 'auto',
                            padding: '0 4px',
                            background: 'transparent',
                            color: '#0284c7',
                            fontSize: 10.5,
                            fontWeight: 600,
                          }}
                        >
                          <CornerDownLeft size={10} />
                          Ответить по #{msg.job_number || msg.job_id.slice(0, 4)}
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </React.Fragment>
            )
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <form onSubmit={onSendReply} style={{ padding: '10px 14px', borderTop: '1px solid #e2e8f0', background: '#fff', flexShrink: 0 }}>
        {error && (
          <div style={{ marginBottom: 8, padding: '5px 9px', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', fontSize: 11.5, borderRadius: 6 }}>
            {error}
          </div>
        )}

        {/* Context & Quick Tools Row */}
        <div
          ref={quickToolsRef}
          style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}
        >
          {!isGuest && clientJobs.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, flex: '1 1 240px', minWidth: 200 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#64748b', flexShrink: 0 }}>Ответ в:</span>
              <select
                value={replyJobId}
                onChange={e => onReplyJobIdChange(e.target.value)}
                style={{ fontSize: 11.5, minHeight: 28, padding: '3px 8px', borderRadius: 6, background: '#f8fafc', flex: 1 }}
              >
                <option value="">💬 Общий чат поддержки (без задачи)</option>
                {replySelectJobs.withChat.length > 0 && (
                  <optgroup label="Задачи с перепиской">
                    {replySelectJobs.withChat.map(j => (
                      <option key={j.job_id} value={j.job_id}>
                        #{j.job_number || j.job_id.slice(0, 4)}: {j.job_title} ({j.chat_messages_count} сообщ.)
                      </option>
                    ))}
                  </optgroup>
                )}
                {replySelectJobs.recent.length > 0 && (
                  <optgroup label="Недавние задачи">
                    {replySelectJobs.recent.map(j => (
                      <option key={j.job_id} value={j.job_id}>
                        #{j.job_number || j.job_id.slice(0, 4)}: {j.job_title}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>
          )}

          {/* Templates Trigger */}
          <button
            type="button"
            onClick={() => {
              setTemplatesOpen(v => !v)
              setJobFilesPickerOpen(false)
            }}
            className="ghost"
            style={{ minHeight: 28, padding: '3px 8px', fontSize: 11.5, fontWeight: 600 }}
          >
            <Sparkles size={12} color="#0d9488" />
            <span>Шаблоны</span>
          </button>

          {/* Attach from Job Results Trigger */}
          {!isGuest && clientJobs.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setJobFilesPickerOpen(v => !v)
                setTemplatesOpen(false)
              }}
              className="ghost"
              style={{ minHeight: 28, padding: '3px 8px', fontSize: 11.5, fontWeight: 600 }}
              title="Прикрепить готовый файл результата любой задачи клиента"
            >
              <FolderOpen size={12} color="#0284c7" />
              <span>Из результатов</span>
            </button>
          )}

          {templatesOpen && (
            <div
              style={{
                position: 'absolute',
                bottom: 'calc(100% + 6px)',
                ...( !isGuest && clientJobs.length > 0 ? { right: 0 } : { left: 0 } ),
                zIndex: 40,
                width: 'min(360px, 100%)',
                maxHeight: 340,
                overflowY: 'auto',
                background: '#fff',
                border: '1px solid #cbd5e1',
                borderRadius: 8,
                boxShadow: '0 10px 25px rgba(15, 23, 42, 0.16)',
                padding: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', padding: '2px 4px' }}>
                Быстрая вставка ответа:
              </div>
              {QUICK_REPLY_TEMPLATES.map(tpl => (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => {
                    onReplyTextChange(replyText.trim() ? `${replyText.trim()}\n\n${tpl.text}` : tpl.text)
                    setTemplatesOpen(false)
                    composerRef?.current?.focus()
                  }}
                  style={{
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    textAlign: 'left',
                    background: '#f8fafc',
                    color: '#0f172a',
                    border: '1px solid #e2e8f0',
                    borderRadius: 6,
                    padding: '6px 8px',
                    minHeight: 'auto',
                    gap: 2,
                  }}
                >
                  <strong style={{ fontSize: 11.5, color: '#0f766e' }}>{tpl.title}</strong>
                  <span style={{ fontSize: 10.5, color: '#64748b', fontWeight: 400, lineHeight: 1.3 }}>
                    {tpl.text}
                  </span>
                </button>
              ))}
            </div>
          )}

          {jobFilesPickerOpen && !isGuest && clientJobs.length > 0 && (
            <div
              style={{
                position: 'absolute',
                bottom: 'calc(100% + 6px)',
                right: 0,
                zIndex: 40,
                width: 'min(360px, 100%)',
                maxHeight: 340,
                background: '#fff',
                border: '1px solid #cbd5e1',
                borderRadius: 8,
                boxShadow: '0 10px 25px rgba(15, 23, 42, 0.16)',
                padding: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 700, color: '#0f172a' }}>Прикрепить файл результата задачи:</div>
              <input
                type="text"
                placeholder="Поиск по #номеру или названию..."
                value={jobFilesSearch}
                onChange={e => setJobFilesSearch(e.target.value)}
                style={{ minHeight: 28, padding: '4px 8px', fontSize: 11.5 }}
                autoFocus
              />
              <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {jobsWithResultFiles.length === 0 ? (
                  <div style={{ fontSize: 11, color: '#94a3b8', padding: 12, textAlign: 'center' }}>
                    Готовых файлов не найдено
                  </div>
                ) : (
                  jobsWithResultFiles.map(j => {
                    const jobFiles = [
                      ...(j.result_files || []).map(f => ({ file: f, srcId: j.job_id, isRerun: false })),
                      ...(j.rerun_files || []).map(f => ({ file: f, srcId: j.rerun_id || j.job_id, isRerun: true })),
                    ]
                    return (
                      <div key={j.job_id} style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 6, background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          #{j.job_number || j.job_id.slice(0, 4)} · {j.job_title}
                        </div>
                        {jobFiles.map((entry, idx) => (
                          <button
                            key={`${entry.srcId}-${entry.file.kind}-${idx}`}
                            type="button"
                            onClick={() => {
                              onAddPendingJobFile({
                                job_id: entry.srcId,
                                job_number: j.job_number,
                                kind: entry.file.kind,
                                filename: entry.file.filename,
                                label: entry.file.label || entry.file.filename,
                              })
                              if (!replyJobId) onReplyJobIdChange(j.job_id)
                              setJobFilesPickerOpen(false)
                            }}
                            style={{
                              justifyContent: 'space-between',
                              textAlign: 'left',
                              minHeight: 26,
                              padding: '3px 7px',
                              fontSize: 11,
                              background: '#fff',
                              color: '#0f766e',
                              border: '1px solid #cbd5e1',
                              borderRadius: 5,
                            }}
                          >
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {entry.isRerun ? '👑 ' : '📄 '}{entry.file.label || entry.file.filename}
                            </span>
                            <span style={{ fontSize: 10, color: '#64748b', flexShrink: 0 }}>+ Прикрепить</span>
                          </button>
                        ))}
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Attached Files & Job Result Files Chips */}
        {(files.length > 0 || pendingJobFiles.length > 0) && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            {pendingJobFiles.map((jf, i) => (
              <span key={`${jf.job_id}-${jf.kind}-${i}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: '#e0f2fe', border: '1px solid #bae6fd', color: '#0369a1', fontSize: 11, padding: '2px 8px', borderRadius: 5, fontWeight: 600 }}>
                📄 {jf.job_number ? `#${jf.job_number} ` : ''}{jf.label}
                <button
                  type="button"
                  onClick={() => onRemovePendingJobFile(i)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#0369a1', fontWeight: 700, padding: 0, minHeight: 'auto' }}
                >
                  ×
                </button>
              </span>
            ))}
            {files.map((f, i) => (
              <span key={`${f.name}-${i}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: '#f0fdfa', border: '1px solid #99f6e4', color: '#0f766e', fontSize: 11, padding: '2px 8px', borderRadius: 5, fontWeight: 600 }}>
                📎 {f.name}
                <button
                  type="button"
                  onClick={() => onFilesChange(prev => prev.filter((_, idx) => idx !== i))}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#0f766e', fontWeight: 700, padding: 0, minHeight: 'auto' }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px', minWidth: 0 }}>
            <textarea
              ref={composerRef}
              rows={2}
              value={replyText}
              onChange={e => onReplyTextChange(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault()
                  onSendReply()
                }
              }}
              placeholder="Напишите ответ клиенту... (Ctrl+Enter для отправки)"
              style={{ width: '100%', minHeight: 62, maxHeight: 160, padding: '8px 10px', fontSize: 12.5, fontFamily: 'inherit', border: '1px solid #cbd5e1', borderRadius: 8, resize: 'vertical' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end', flexShrink: 0, marginLeft: 'auto' }}>
            {telegramId && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: '#0284c7', cursor: 'pointer', userSelect: 'none' }}>
                <input
                  type="checkbox"
                  checked={notifyTelegram}
                  onChange={e => onNotifyTelegramChange(e.target.checked)}
                />
                <span>Уведомить в TG</span>
              </label>
            )}

            <div style={{ display: 'flex', gap: 6 }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, fontWeight: 600, color: '#475569', cursor: 'pointer', padding: '0 10px', minHeight: 34, border: '1px solid #cbd5e1', borderRadius: 6, background: '#f8fafc' }}>
                <Paperclip size={13} />
                <span>Файл</span>
                <input
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  accept=".xlsx,.xls,.docx,.doc,.pdf,.zip,.rar,.7z,.txt,.png,.jpg,.jpeg,.webp"
                  onChange={e => {
                    if (e.target.files) {
                      const incoming = Array.from(e.target.files)
                      onFilesChange(prev => [...prev, ...incoming].slice(0, 10))
                      e.target.value = ''
                    }
                  }}
                />
              </label>

              <button
                type="submit"
                disabled={sending || (!replyText.trim() && files.length === 0 && pendingJobFiles.length === 0)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  background: '#0d9488',
                  color: '#fff',
                  border: 'none',
                  padding: '0 14px',
                  minHeight: 34,
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                {sending ? <Loader2 size={13} className="spin" /> : <Send size={13} />}
                <span>Отправить</span>
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}
