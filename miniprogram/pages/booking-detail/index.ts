import { cancelBooking, fetchBookingDetail } from '../../services/bookings'
import type { BookingDetail } from '../../services/types'
import { formatDate, formatDateTime, formatTime, periodName } from '../../utils/format'

const EVENT_TITLES: Record<string, string> = {
  submitted: '预约意向已提交',
  customer_updated: '预约信息已更新',
  info_requested: '摄影师请求补充信息',
  reschedule_proposed: '摄影师建议改期',
  confirmed: '预约已确认',
  declined: '摄影师暂时无法接单',
  customer_cancelled: '预约已取消',
  admin_cancelled: '预约已取消',
  completed: '拍摄已完成'
}

function selectionName(detail: BookingDetail, code: string, fallback = '待确认'): string {
  return detail.selections[code]?.map((item) => item.name).join('、') || fallback
}

Page({
  data: {
    bookingNo: '',
    booking: null as any,
    isNew: false,
    loading: true,
    cancelling: false,
    errorMessage: '',
    canModify: false,
    canCancel: false,
    timeline: [] as any[]
  },

  onLoad(options: Record<string, string>) {
    this.setData({ bookingNo: options.bookingNo || '', isNew: options.new === '1' })
    if (!options.bookingNo) {
      this.setData({ loading: false, errorMessage: '预约参数无效。' })
      return
    }
    this.loadBooking(options.bookingNo)
  },

  async loadBooking(bookingNo = this.data.bookingNo) {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const detail = await fetchBookingDetail(bookingNo)
      const locationName = detail.location.type === 'custom'
        ? detail.location.text || '一起商量'
        : selectionName(detail, 'location')
      const timeline = detail.timeline.map((item) => ({
        title: EVENT_TITLES[item.event_type] || EVENT_TITLES[item.to_status || ''] || '预约状态已更新',
        note: item.message || '预约状态发生变化。',
        time: formatDateTime(item.created_at),
        done: true
      }))
      if (!timeline.length) {
        timeline.push({
          title: '预约意向已提交',
          note: '摄影师会尽快与你确认档期与费用。',
          time: formatDateTime(detail.updated_at),
          done: true
        })
      }
      this.setData({
        loading: false,
        booking: {
          ...detail,
          bookingNo: detail.booking_no,
          statusText: detail.status_text,
          statusNote: detail.status_note,
          shootTypeName: selectionName(detail, 'shoot_type'),
          styleName: selectionName(detail, 'style'),
          shootMethodName: selectionName(detail, 'equipment_feel'),
          propsName: selectionName(detail, 'props', '未选择'),
          budgetName: selectionName(detail, 'budget', detail.budget_code || '待确认'),
          date: formatDate(detail.requested_date),
          period: periodName(detail.requested_period_code),
          location: locationName,
          contactName: detail.contact.name,
          phoneMasked: detail.contact.phone_masked,
          confirmedTime: detail.confirmed_slot
            ? `${formatDateTime(detail.confirmed_slot.start_at)}–${formatTime(detail.confirmed_slot.end_at)}`
            : ''
        },
        timeline,
        canModify: ['submitted', 'needs_info', 'reschedule_proposed'].includes(detail.status),
        canCancel: ['submitted', 'needs_info', 'reschedule_proposed'].includes(detail.status)
      })
      wx.setNavigationBarTitle({ title: `预约 ${detail.booking_no}` })
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '预约详情加载失败，请稍后重试。'
      })
    }
  },

  retryLoad() {
    this.loadBooking()
  },

  modifyBooking() {
    wx.navigateTo({
      url: `/pages/booking-form/index?bookingNo=${encodeURIComponent(this.data.bookingNo)}`
    })
  },

  cancelBooking() {
    if (!this.data.booking || this.data.cancelling) return
    wx.showModal({
      title: '确认取消预约？',
      content: '取消后不能由客户自行恢复，如需重新预约可以再次提交意向。',
      success: async (result: any) => {
        if (!result.confirm) return
        this.setData({ cancelling: true })
        try {
          await cancelBooking(this.data.bookingNo, this.data.booking.version)
          wx.showToast({ title: '预约已取消', icon: 'success' })
          await this.loadBooking()
        } catch (error) {
          wx.showModal({
            title: '取消未完成',
            content: (error as Error).message || '请刷新后重试。',
            showCancel: false
          })
        } finally {
          this.setData({ cancelling: false })
        }
      }
    })
  },

  viewWorks() {
    wx.switchTab({ url: '/pages/works/index' })
  }
})
