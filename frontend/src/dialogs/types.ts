export interface DialogJobResultFile {
  kind: string
  label: string
  filename: string
  is_admin_supplement?: boolean
  created_at?: string | null
}

export interface DialogJobSummary {
  job_id: string
  job_number?: number | null
  job_title: string
  job_mode: string
  job_mode_label: string
  job_status: string
  created_at?: string | null
  completed_at?: string | null
  verified_count?: number
  has_result?: boolean
  has_chat?: boolean
  result_files?: DialogJobResultFile[]
  rerun_id?: string | null
  rerun_status?: string | null
  rerun_files?: DialogJobResultFile[]
  admin_comment?: string
  error?: string
  chat_messages_count?: number
}

export interface DialogItem {
  client_id: string
  client_number?: number | null
  client_name: string
  client_email: string
  client_phone: string
  visitor_contact?: string
  source_url?: string
  client_ip?: string
  is_guest?: boolean
  guest_session_id?: string
  telegram_id: string
  last_channel?: string
  last_is_ai_reply?: boolean
  topic_linked?: boolean
  dialog_status?: 'open' | 'closed' | 'blocked' | string
  is_blocked?: boolean
  needs_reply?: boolean
  last_message: string
  last_message_at: string | null
  last_sender_role: 'admin' | 'client'
  unread_admin_count: number
  total_messages: number
  jobs_count?: number
  jobs_with_chat_count?: number
  jobs: DialogJobSummary[]
  job_id?: string
  job_number?: number | null
  job_title?: string
  job_mode?: string
  job_mode_label?: string
  job_status?: string
}

export interface DialogClientProfile {
  id: string
  number?: number | null
  name: string
  email: string
  phone: string
  visitor_contact?: string
  telegram_id: string
  username?: string
  notes?: string
  is_trial?: boolean
  access_until?: string
  available_kopeks?: number
  money_balance_kopeks?: number
  source_url?: string
  client_ip?: string
  created_at?: string | null
  is_guest?: boolean
  guest_session_id?: string
  is_blocked?: boolean
  dialog_status?: 'open' | 'closed' | 'blocked' | string
  topic_linked?: boolean
  last_channel?: string
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
  guest_session_id?: string
  channel?: string
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

export interface PendingJobFileAttachment {
  job_id: string
  job_number?: number | null
  kind: string
  filename: string
  label: string
}

export type DialogQueueTab = 'all' | 'needs_reply' | 'open' | 'closed' | 'guests' | 'blocked'

export interface QuickReplyTemplate {
  id: string
  title: string
  text: string
}

export interface DialogClientCandidate {
  id: string
  client_number?: number | null
  name?: string
  username?: string
  phone?: string
  telegram_id?: string
  jobs_count?: number
  web_users?: Array<{ email?: string; phone?: string; name?: string }>
}
