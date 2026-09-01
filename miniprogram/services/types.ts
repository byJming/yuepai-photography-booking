export interface ApiEnvelope<T> {
  data: T
  request_id: string
}

export interface ApiErrorEnvelope {
  error: {
    code: string
    message: string
    details?: Record<string, any>
  }
  request_id?: string
}

export interface BrandConfig {
  name: string
  eyebrow: string
  monthly_title: string
  monthly_subtitle: string
  availability_text: string
  service_area: string
  about_text?: string
}

export interface PolicyVersions {
  privacy: string
  service_terms: string
}

export interface PolicyContent {
  service_scope?: string
  schedule_and_pricing?: string
  safety_and_reschedule?: string
  privacy_and_display?: string
  cancellation_rules?: string
}

export interface BootstrapData {
  brand: BrandConfig
  availability_status: {
    available: boolean
    text: string
    next_date?: string
  }
  feature_flags: {
    subscription_message: boolean
    reference_upload: boolean
  }
  policy_versions: PolicyVersions
  policy_content?: PolicyContent
  booking_horizon_months: number
}

export interface MediaView {
  url: string
  thumbnail_url?: string
  width: number
  height: number
}

export interface PortfolioSummary {
  id: number
  slug: string
  title: string
  subtitle?: string
  category_code: string
  style_tags: string[]
  location?: string
  shot_on?: string
  cover: MediaView
}

export interface PortfolioDetail {
  id: number
  slug: string
  title: string
  subtitle?: string
  description?: string
  category_code: string
  style_tags: string[]
  location?: string
  shot_on?: string
  images: Array<MediaView & { id: number; caption?: string }>
}

export interface BookingOptionItem {
  code: string
  name: string
  description?: string
  metadata: Record<string, any>
  reference?: {
    url: string
    width: number
    height: number
  }
}

export interface BookingOptionGroup {
  code: string
  name: string
  selection_mode: 'single' | 'multiple'
  is_required: boolean
  min_select: number
  max_select: number
  items: BookingOptionItem[]
}

export interface AvailabilityPeriod {
  slot_id: number
  code: 'morning' | 'afternoon' | 'sunset'
  label: string
  start_at: string
  end_at: string
  available: boolean
  public_note?: string
}

export interface AvailabilityDate {
  date: string
  periods: AvailabilityPeriod[]
}

export interface AvailabilityResponse {
  month: string
  dates: AvailabilityDate[]
}

export interface BookingSummary {
  booking_no: string
  status: string
  status_text: string
  requested_date: string
  requested_period_code: string
  shoot_type?: { code: string; name: string }
  updated_at: string
  version: number
}

export interface BookingTimelineItem {
  event_type: string
  from_status?: string
  to_status?: string
  message?: string
  created_at: string
}

export interface BookingDetail extends BookingSummary {
  status_note: string
  participant_count: number
  budget_code?: string
  location: {
    type: 'preset' | 'custom'
    code?: string
    text?: string
  }
  contact: {
    name: string
    phone_masked: string
  }
  remark: string
  selections: Record<string, Array<{ code: string; name: string }>>
  confirmed_slot?: {
    start_at: string
    end_at: string
    public_note?: string
  }
  timeline: BookingTimelineItem[]
}

export interface BookingCreatePayload {
  requested_date: string
  requested_period_code: string
  participant_count: number
  budget_code?: string
  location: {
    type: 'preset' | 'custom'
    code?: string
    text?: string
  }
  selections: Record<string, string[]>
  contact: {
    name: string
    phone: string
  }
  remark: string
  privacy_policy_version: string
  service_terms_version: string
}

export interface BookingUpdatePayload {
  version: number
  requested_date?: string
  requested_period_code?: string
  participant_count?: number
  budget_code?: string
  location?: {
    type: 'preset' | 'custom'
    code?: string
    text?: string
  }
  selections?: Record<string, string[]>
  contact?: {
    name: string
    phone: string
  }
  remark?: string
}
