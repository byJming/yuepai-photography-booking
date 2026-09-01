export interface ApiEnvelope<T> {
  data: T
  request_id: string
}

export interface ApiErrorEnvelope {
  error: { code: string; message: string; details?: Record<string, unknown> }
  request_id?: string
}

export interface AdminSummary {
  id: number
  username: string
  totp_enabled: boolean
}

export interface BookingSummary {
  booking_no: string
  status: string
  status_text: string
  requested_date: string
  requested_period_code: string
  contact_name: string
  phone_masked: string
  shoot_type?: string
  submitted_at: string
  updated_at: string
  version: number
}

export interface BookingDetail extends BookingSummary {
  status_note: string
  participant_count: number
  budget_code?: string
  location: { type: string; code?: string; text?: string }
  contact: { name: string; phone_masked: string; phone: string }
  remark: string
  selections: Record<string, Array<{ code: string; name: string }>>
  confirmed_slot?: { start_at: string; end_at: string; public_note?: string }
  timeline: Array<{ event_type: string; message?: string; created_at: string }>
  internal_events: Array<{ event_type: string; internal_note: string; created_at: string }>
}

export interface Slot {
  id: number
  start_at: string
  end_at: string
  status: string
  public_note?: string
  internal_note?: string
  version: number
  booking_no?: string
}

export interface Portfolio {
  id: number
  slug: string
  title: string
  subtitle?: string
  description?: string
  category_code: string
  style_tags: string[]
  location_text?: string
  shot_on?: string
  cover_media_id?: number
  status: string
  sort_order: number
  published_at?: string
}

export interface PortfolioMedia {
  id: number
  url: string
  thumbnail_url: string
  width: number
  height: number
  file_size: number
  caption?: string
  status: string
}

export interface PortfolioDetail extends Portfolio {
  media: PortfolioMedia[]
}

export interface OptionItem {
  id: number
  code: string
  name: string
  description?: string
  reference_media_id?: number
  metadata: Record<string, unknown>
  status: 'active' | 'disabled'
  sort_order: number
}

export interface OptionGroup {
  id: number
  code: string
  name: string
  selection_mode: 'single' | 'multiple'
  is_required: boolean
  min_select: number
  max_select: number
  status: 'active' | 'disabled'
  sort_order: number
  items: OptionItem[]
}

export interface DataDeletionRequest {
  id: number
  user_id: number
  status: 'pending' | 'completed' | 'rejected'
  active_booking_count: number
  created_at: string
  processed_at?: string
}
