import { request } from './api'
import type {
  BookingCreatePayload,
  BookingDetail,
  BookingSummary,
  BookingUpdatePayload
} from './types'

export function createBooking(
  payload: BookingCreatePayload,
  idempotencyKey: string
): Promise<BookingDetail> {
  return request('/bookings', {
    method: 'POST',
    data: payload,
    headers: { 'Idempotency-Key': idempotencyKey },
    auth: true
  })
}

export function listBookings(): Promise<{ items: BookingSummary[]; next_cursor?: string }> {
  return request('/bookings?limit=20', { auth: true })
}

export function fetchBookingDetail(bookingNo: string): Promise<BookingDetail> {
  return request(`/bookings/${encodeURIComponent(bookingNo)}`, { auth: true })
}

export function updateBooking(
  bookingNo: string,
  payload: BookingUpdatePayload
): Promise<BookingDetail> {
  return request(`/bookings/${encodeURIComponent(bookingNo)}`, {
    method: 'PATCH',
    data: payload,
    auth: true
  })
}

export function cancelBooking(
  bookingNo: string,
  version: number
): Promise<BookingDetail> {
  return request(`/bookings/${encodeURIComponent(bookingNo)}/cancel`, {
    method: 'POST',
    data: { version },
    auth: true
  })
}

export function requestDataDeletion(): Promise<{ id: number; status: string; created_at: string }> {
  return request('/me/data-deletion-requests', { method: 'POST', auth: true })
}
