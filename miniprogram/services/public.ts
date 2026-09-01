import { request } from './api'
import type {
  AvailabilityResponse,
  BookingOptionGroup,
  BootstrapData,
  PortfolioDetail,
  PortfolioSummary
} from './types'

export function fetchBootstrap(): Promise<BootstrapData> {
  return request('/bootstrap')
}

export function fetchPortfolios(category = '', cursor?: string): Promise<{
  items: PortfolioSummary[]
  next_cursor?: string
}> {
  const query = [
    category ? `category=${encodeURIComponent(category)}` : '',
    cursor ? `cursor=${encodeURIComponent(cursor)}` : '',
    'limit=20'
  ].filter(Boolean).join('&')
  return request(`/portfolio-series?${query}`)
}

export function fetchPortfolioDetail(slug: string): Promise<PortfolioDetail> {
  return request(`/portfolio-series/${encodeURIComponent(slug)}`)
}

export function fetchBookingOptions(): Promise<{ groups: BookingOptionGroup[] }> {
  return request('/booking-options')
}

export function fetchAvailability(month: string): Promise<AvailabilityResponse> {
  return request(`/availability?month=${encodeURIComponent(month)}`)
}
