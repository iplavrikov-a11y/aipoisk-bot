import React, { useState, useEffect, useRef } from 'react'
import { DialogSidebar } from './dialogs/DialogSidebar'
import { DialogThread } from './dialogs/DialogThread'
import { DialogContextPanel } from './dialogs/DialogContextPanel'
import {
  ChatMessage,
  DialogClientCandidate,
  DialogClientProfile,
  DialogItem,
  DialogJobSummary,
  DialogQueueTab,
  PendingJobFileAttachment,
} from './dialogs/types'

export type { DialogItem, DialogJobSummary, ChatMessage }

export function DialogsView({
  clients = [],
  initialClientId = '',
  onClearInitialClient,
  onOpenJob,
  onOpenClient,
  onUnreadCountChange,
}: {
  clients?: DialogClientCandidate[]
  initialClientId?: string
  onClearInitialClient?: () => void
  onOpenJob?: (jobId: string, clientId?: string, jobNumber?: number | null) => void
  onOpenClient?: (clientId: string) => void
  onUnreadCountChange?: (count: number) => void
}) {
  const [dialogs, setDialogs] = useState<DialogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [queueTab, setQueueTab] = useState<DialogQueueTab>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedClientId, setSelectedClientId] = useState<string | null>(initialClientId || null)
  const [activeJobFilter, setActiveJobFilter] = useState<string>('all')

  const [clientProfile, setClientProfile] = useState<DialogClientProfile | null>(null)
  const [activeMessages, setActiveMessages] = useState<ChatMessage[]>([])
  const [clientJobs, setClientJobs] = useState<DialogJobSummary[]>([])
  const [generalMessagesCount, setGeneralMessagesCount] = useState<number>(0)
  const [loadingMessages, setLoadingMessages] = useState(false)

  const [replyText, setReplyText] = useState('')
  const [replyJobId, setReplyJobId] = useState<string>('')
  const [files, setFiles] = useState<File[]>([])
  const [pendingJobFiles, setPendingJobFiles] = useState<PendingJobFileAttachment[]>([])
  const [notifyTelegram, setNotifyTelegram] = useState(true)
  const [sending, setSending] = useState(false)
  const [markingAllRead, setMarkingAllRead] = useState(false)
  const [blockingAction, setBlockingAction] = useState(false)
  const [statusActionLoading, setStatusActionLoading] = useState(false)
  const [showContextPanel, setShowContextPanel] = useState(true)
  const [isMobileViewport, setIsMobileViewport] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(max-width: 980px)').matches : false
  )
  const [mobilePane, setMobilePane] = useState<'list' | 'thread' | 'context'>(() =>
    initialClientId ? 'thread' : 'list'
  )
  const [error, setError] = useState('')

  const dialogsInFlightRef = useRef(false)
  const hasLoadedDialogsRef = useRef(false)
  const selectedClientIdRef = useRef<string | null>(null)
  const isMobileViewportRef = useRef<boolean>(isMobileViewport)
  const mobilePaneRef = useRef<'list' | 'thread' | 'context'>(mobilePane)
  const messagesAbortRef = useRef<AbortController | null>(null)
  const messagesReqSeqRef = useRef(0)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)

  const token = localStorage.getItem('tenderlex_admin_token') || sessionStorage.getItem('tenderlex_admin_token') || ''
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  selectedClientIdRef.current = selectedClientId
  isMobileViewportRef.current = isMobileViewport
  mobilePaneRef.current = mobilePane

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 980px)')
    const onChange = (event: MediaQueryListEvent) => {
      setIsMobileViewport(event.matches)
      isMobileViewportRef.current = event.matches
      if (event.matches && mobilePaneRef.current === 'list' && selectedClientIdRef.current) {
        setSelectedClientId(null)
      }
    }
    setIsMobileViewport(mq.matches)
    isMobileViewportRef.current = mq.matches
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    if (initialClientId) {
      setSelectedClientId(initialClientId)
      setMobilePane('thread')
      onClearInitialClient?.()
    }
  }, [initialClientId])

  async function loadDialogs(selectFirst = false, silent = false) {
    if (silent && dialogsInFlightRef.current) return
    dialogsInFlightRef.current = true
    try {
      if (!silent) setLoading(true)
      const res = await fetch('/api/admin/dialogs', { credentials: 'same-origin', headers: authHeaders })
      if (res.ok) {
        const data = await res.json()
        const list: DialogItem[] = data.dialogs || []
        hasLoadedDialogsRef.current = true
        setDialogs(list)
        if (typeof data.total_unread_admin === 'number') {
          onUnreadCountChange?.(data.total_unread_admin)
        }
        if (selectFirst && list.length > 0 && !selectedClientIdRef.current) {
          setSelectedClientId(list[0].client_id)
        }
      }
    } catch (err) {
      if (!silent) console.error('Failed to load dialogs:', err)
    } finally {
      dialogsInFlightRef.current = false
      if (!silent) setLoading(false)
    }
  }

  async function loadChatMessages(clientId: string, silent = false) {
    if (silent && messagesAbortRef.current) return
    if (!silent && messagesAbortRef.current) {
      messagesAbortRef.current.abort()
    }
    const controller = new AbortController()
    messagesAbortRef.current = controller
    const reqSeq = ++messagesReqSeqRef.current
    try {
      if (!silent) {
        setLoadingMessages(true)
        setError('')
      }
      const res = await fetch(`/api/admin/clients/${encodeURIComponent(clientId)}/chat`, {
        credentials: 'same-origin',
        headers: authHeaders,
        signal: controller.signal,
      })
      if (reqSeq !== messagesReqSeqRef.current || selectedClientIdRef.current !== clientId) {
        return
      }
      if (res.ok) {
        const data = await res.json()
        if (reqSeq !== messagesReqSeqRef.current || selectedClientIdRef.current !== clientId) {
          return
        }
        const loadedMsgs: ChatMessage[] = data.messages || []
        const loadedJobs: DialogJobSummary[] = data.jobs || []
        const loadedProfile: DialogClientProfile | null = data.client || null

        setActiveMessages(loadedMsgs)
        setClientJobs(loadedJobs)
        setClientProfile(loadedProfile)
        setGeneralMessagesCount(
          typeof data.general_messages_count === 'number'
            ? data.general_messages_count
            : loadedMsgs.filter(m => !m.job_id).length
        )

        if (!silent) {
          // Default reply context to the job of the latest message if present, else newest job with chat, else empty
          const latestMsgWithJob = [...loadedMsgs].reverse().find(m => Boolean(m.job_id))
          if (latestMsgWithJob?.job_id) {
            setReplyJobId(latestMsgWithJob.job_id)
          } else {
            const firstChatted = loadedJobs.find(j => (j.chat_messages_count || 0) > 0)
            setReplyJobId(firstChatted ? firstChatted.job_id : '')
          }
          setActiveJobFilter('all')
          setFiles([])
          setPendingJobFiles([])
        }

        const serverBlocked = typeof loadedProfile?.is_blocked === 'boolean' ? loadedProfile.is_blocked : undefined
        const serverStatus = loadedProfile?.dialog_status
        setDialogs(prev =>
          prev.map(d =>
            d.client_id === clientId
              ? {
                  ...d,
                  unread_admin_count: 0,
                  ...(serverBlocked !== undefined ? { is_blocked: serverBlocked } : {}),
                  ...(serverStatus ? { dialog_status: serverStatus } : {}),
                }
              : d
          )
        )
      } else if (!silent) {
        const errText = await res.text()
        setError(errText || 'Не удалось загрузить историю переписки')
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      if (!silent && reqSeq === messagesReqSeqRef.current) {
        setError(err.message || 'Ошибка загрузки переписки')
      }
    } finally {
      if (messagesAbortRef.current === controller) {
        messagesAbortRef.current = null
      }
      if (!silent && reqSeq === messagesReqSeqRef.current) {
        setLoadingMessages(false)
      }
    }
  }

  useEffect(() => {
    const isNarrow = typeof window !== 'undefined' && window.matchMedia('(max-width: 980px)').matches
    // On mobile do NOT auto-open the first dialog, because GET /chat marks unread messages as read on the server.
    void loadDialogs(!initialClientId && !isNarrow)
    return () => {
      messagesAbortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    if (selectedClientId) {
      void loadChatMessages(selectedClientId)
    } else {
      messagesAbortRef.current?.abort()
      setActiveMessages([])
      setClientJobs([])
      setClientProfile(null)
      setGeneralMessagesCount(0)
      setLoadingMessages(false)
    }
  }, [selectedClientId])

  useEffect(() => {
    let cancelled = false
    let timerId: number | null = null

    const runPoll = async () => {
      if (cancelled) return
      if (!document.hidden) {
        const activeId = selectedClientIdRef.current
        const canPollChat = Boolean(activeId) && !(isMobileViewportRef.current && mobilePaneRef.current === 'list')
        await Promise.all([
          loadDialogs(false, true),
          canPollChat && activeId ? loadChatMessages(activeId, true) : Promise.resolve(),
        ])
      }
      if (!cancelled) {
        timerId = window.setTimeout(() => {
          void runPoll()
        }, 5000)
      }
    }

    timerId = window.setTimeout(() => {
      void runPoll()
    }, 5000)

    const onVisibilityChange = () => {
      if (!document.hidden && !cancelled) {
        const activeId = selectedClientIdRef.current
        const canPollChat = Boolean(activeId) && !(isMobileViewportRef.current && mobilePaneRef.current === 'list')
        void loadDialogs(false, true)
        if (canPollChat && activeId) {
          void loadChatMessages(activeId, true)
        }
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      cancelled = true
      if (timerId !== null) window.clearTimeout(timerId)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  const selectedDialog = dialogs.find(d => d.client_id === selectedClientId) || null
  const totalUnread = dialogs.reduce((sum, d) => sum + (d.unread_admin_count || 0), 0)

  useEffect(() => {
    if (hasLoadedDialogsRef.current) {
      onUnreadCountChange?.(totalUnread)
    }
  }, [totalUnread])

  async function handleMarkAllRead() {
    if (markingAllRead) return
    setMarkingAllRead(true)
    setError('')
    try {
      const res = await fetch('/api/admin/dialogs/read-all', {
        method: 'POST',
        credentials: 'same-origin',
        headers: authHeaders,
      })
      if (!res.ok) {
        throw new Error((await res.text()) || 'Не удалось отметить диалоги прочитанными')
      }
      setDialogs(prev => prev.map(d => ({ ...d, unread_admin_count: 0 })))
      setActiveMessages(prev => prev.map(m => (m.sender_role === 'client' ? { ...m, is_read_by_admin: true } : m)))
      onUnreadCountChange?.(0)
    } catch (err: any) {
      setError(err.message || 'Не удалось отметить все диалоги прочитанными')
    } finally {
      setMarkingAllRead(false)
    }
  }

  async function handleToggleBlock() {
    const cid = clientProfile?.id || selectedDialog?.client_id
    if (!cid || blockingAction) return
    const currentlyBlocked = Boolean(clientProfile?.is_blocked ?? selectedDialog?.is_blocked)
    const endpoint = currentlyBlocked
      ? `/api/admin/dialogs/${encodeURIComponent(cid)}/unblock`
      : `/api/admin/dialogs/${encodeURIComponent(cid)}/block`

    setBlockingAction(true)
    setError('')
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: currentlyBlocked ? undefined : JSON.stringify({}),
      })
      if (!res.ok) {
        throw new Error((await res.text()) || 'Не удалось изменить статус блокировки')
      }
      const data = await res.json()
      const nextBlocked = Boolean(data.is_blocked)
      setClientProfile(prev =>
        prev ? { ...prev, is_blocked: nextBlocked, dialog_status: nextBlocked ? 'blocked' : 'open' } : prev
      )
      setDialogs(prev =>
        prev.map(d =>
          d.client_id === cid
            ? {
                ...d,
                is_blocked: nextBlocked,
                dialog_status: nextBlocked ? 'blocked' : 'open',
                unread_admin_count: nextBlocked ? 0 : d.unread_admin_count,
              }
            : d
        )
      )
      if (nextBlocked) {
        setActiveMessages(prev => prev.map(m => (m.sender_role === 'client' ? { ...m, is_read_by_admin: true } : m)))
      }
    } catch (err: any) {
      setError(err.message || 'Ошибка изменения статуса блокировки')
    } finally {
      setBlockingAction(false)
    }
  }

  async function handleCloseOrReopen() {
    const cid = clientProfile?.id || selectedDialog?.client_id
    if (!cid || statusActionLoading) return
    const curStatus = clientProfile?.dialog_status || selectedDialog?.dialog_status || 'open'
    const isClosed = curStatus === 'closed'
    const endpoint = isClosed
      ? `/api/admin/dialogs/${encodeURIComponent(cid)}/reopen`
      : `/api/admin/dialogs/${encodeURIComponent(cid)}/close`

    setStatusActionLoading(true)
    setError('')
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: isClosed ? undefined : JSON.stringify({ send_closing_note: false }),
      })
      if (!res.ok) {
        throw new Error((await res.text()) || 'Не удалось обновить статус диалога')
      }
      const nextStatus = isClosed ? 'open' : 'closed'
      setClientProfile(prev => (prev ? { ...prev, dialog_status: nextStatus } : prev))
      setDialogs(prev =>
        prev.map(d =>
          d.client_id === cid
            ? { ...d, dialog_status: nextStatus, needs_reply: nextStatus === 'closed' ? false : d.needs_reply }
            : d
        )
      )
    } catch (err: any) {
      setError(err.message || 'Ошибка изменения статуса диалога')
    } finally {
      setStatusActionLoading(false)
    }
  }

  async function handleSaveNotes(clientId: string, notes: string) {
    const res = await fetch(`/api/clients/${encodeURIComponent(clientId)}`, {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...authHeaders },
      body: JSON.stringify({ notes }),
    })
    if (!res.ok) {
      setError((await res.text()) || 'Не удалось сохранить заметку')
      return
    }
    setClientProfile(prev => (prev && prev.id === clientId ? { ...prev, notes } : prev))
  }

  async function handleSendReply(e?: React.FormEvent) {
    if (e) e.preventDefault()
    if (!selectedClientId) return
    const text = replyText.trim()
    if (!text && files.length === 0 && pendingJobFiles.length === 0) return

    setSending(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('message', text)
      formData.append('job_id', replyJobId || '')
      formData.append('notify_telegram', String(notifyTelegram))
      if (pendingJobFiles.length > 0) {
        formData.append(
          'attach_job_files',
          JSON.stringify(pendingJobFiles.map(jf => ({ job_id: jf.job_id, kind: jf.kind })))
        )
      }
      files.forEach(f => formData.append('files', f))
      if (files[0]) formData.append('file', files[0])

      const res = await fetch(`/api/admin/clients/${encodeURIComponent(selectedClientId)}/chat`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: authHeaders,
        body: formData,
      })
      if (!res.ok) {
        throw new Error((await res.text()) || 'Ошибка отправки')
      }
      const data = await res.json()
      const updatedMsgs: ChatMessage[] = data.messages || []
      setActiveMessages(updatedMsgs)
      setReplyText('')
      setFiles([])
      setPendingJobFiles([])

      // Refresh dialog list silently if this was a brand-new dialog not yet in the list
      const existsInList = dialogs.some(d => d.client_id === selectedClientId)
      if (!existsInList) {
        void loadDialogs(false, true)
      } else {
        setDialogs(prev =>
          prev.map(d =>
            d.client_id === selectedClientId
              ? {
                  ...d,
                  dialog_status: 'open',
                  needs_reply: false,
                  last_message: text || '📎 Прикреплен файл',
                  last_sender_role: 'admin',
                  last_message_at: new Date().toISOString(),
                  total_messages: updatedMsgs.length || d.total_messages + 1,
                }
              : d
          )
        )
      }
    } catch (err: any) {
      setError(err.message || 'Не удалось отправить сообщение')
    } finally {
      setSending(false)
    }
  }

  const effectiveMobilePane: 'list' | 'thread' | 'context' =
    !selectedClientId ? 'list' : mobilePane

  return (
    <div
      className={`dialogs-workspace dialogs-workspace--mobile-${effectiveMobilePane}`}
      style={{
        display: 'flex',
        height: 'calc(100vh - 114px)',
        minHeight: 540,
        gap: 12,
        background: '#f1f5f9',
        padding: 10,
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
      }}
    >
      <DialogSidebar
        dialogs={dialogs}
        clients={clients}
        loading={loading}
        selectedClientId={selectedClientId}
        onSelectClient={cid => {
          setSelectedClientId(cid)
          if (isMobileViewport) setMobilePane('thread')
        }}
        queueTab={queueTab}
        onQueueTabChange={setQueueTab}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        totalUnread={totalUnread}
        markingAllRead={markingAllRead}
        onMarkAllRead={() => void handleMarkAllRead()}
        onRefresh={() => void loadDialogs(false)}
      />

      <DialogThread
        selectedDialog={selectedDialog}
        clientProfile={clientProfile}
        messages={activeMessages}
        clientJobs={clientJobs}
        generalMessagesCount={generalMessagesCount}
        loadingMessages={loadingMessages}
        activeJobFilter={activeJobFilter}
        onJobFilterChange={setActiveJobFilter}
        replyJobId={replyJobId}
        onReplyJobIdChange={setReplyJobId}
        replyText={replyText}
        onReplyTextChange={setReplyText}
        files={files}
        onFilesChange={setFiles}
        pendingJobFiles={pendingJobFiles}
        onRemovePendingJobFile={idx => setPendingJobFiles(prev => prev.filter((_, i) => i !== idx))}
        onAddPendingJobFile={item =>
          setPendingJobFiles(prev =>
            prev.some(x => x.job_id === item.job_id && x.kind === item.kind) ? prev : [...prev, item].slice(0, 10)
          )
        }
        notifyTelegram={notifyTelegram}
        onNotifyTelegramChange={setNotifyTelegram}
        sending={sending}
        error={error}
        blockingAction={blockingAction}
        statusActionLoading={statusActionLoading}
        onToggleBlock={() => void handleToggleBlock()}
        onCloseOrReopen={() => void handleCloseOrReopen()}
        onSendReply={handleSendReply}
        onOpenJob={onOpenJob}
        showContextPanel={isMobileViewport ? effectiveMobilePane === 'context' : showContextPanel}
        onToggleContextPanel={() => {
          if (isMobileViewport) {
            setMobilePane(prev => (prev === 'context' ? 'thread' : 'context'))
          } else {
            setShowContextPanel(v => !v)
          }
        }}
        onBackToList={isMobileViewport ? () => {
          setMobilePane('list')
          setSelectedClientId(null)
        } : undefined}
        composerRef={composerRef}
      />

      {(isMobileViewport ? effectiveMobilePane === 'context' : (showContextPanel && Boolean(selectedDialog || clientProfile))) && (
        <DialogContextPanel
          client={clientProfile}
          jobs={clientJobs}
          generalMessagesCount={generalMessagesCount}
          activeJobFilter={activeJobFilter}
          onSelectJobFilter={jid => {
            setActiveJobFilter(jid)
            if (isMobileViewport) setMobilePane('thread')
          }}
          onSetReplyJob={jid => {
            setReplyJobId(jid)
            if (isMobileViewport) {
              setMobilePane('thread')
              window.requestAnimationFrame(() => composerRef.current?.focus())
            } else {
              composerRef.current?.focus()
            }
          }}
          onAttachJobFile={item => {
            setPendingJobFiles(prev =>
              prev.some(x => x.job_id === item.job_id && x.kind === item.kind) ? prev : [...prev, item].slice(0, 10)
            )
            if (isMobileViewport) {
              setMobilePane('thread')
              window.requestAnimationFrame(() => composerRef.current?.focus())
            } else {
              composerRef.current?.focus()
            }
          }}
          onOpenJob={onOpenJob}
          onOpenClient={onOpenClient}
          onSaveNotes={handleSaveNotes}
          onBackToThread={isMobileViewport ? () => setMobilePane('thread') : undefined}
        />
      )}
    </div>
  )
}
