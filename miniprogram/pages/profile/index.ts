import { listBookings, requestDataDeletion } from '../../services/bookings'
import { formatDate, periodName } from '../../utils/format'

Page({
  data: {
    bookings: [] as any[],
    loading: true,
    deleting: false,
    errorMessage: ''
  },

  onShow() {
    const tabBar = this.getTabBar()
    if (tabBar) tabBar.setData({ selected: 2 })
    this.loadBookings()
  },

  async loadBookings() {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const result = await listBookings()
      this.setData({
        loading: false,
        bookings: result.items.map((item) => ({
          ...item,
          bookingNo: item.booking_no,
          statusText: item.status_text,
          title: item.shoot_type?.name || '摄影预约',
          dateText: `${formatDate(item.requested_date)} · ${periodName(item.requested_period_code)}`
        }))
      })
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '预约列表加载失败，请稍后重试。'
      })
    }
  },

  retryLoad() {
    this.loadBookings()
  },

  openBooking(event: any) {
    const bookingNo = String(event.currentTarget.dataset.bookingNo)
    wx.navigateTo({
      url: `/pages/booking-detail/index?bookingNo=${encodeURIComponent(bookingNo)}`
    })
  },

  openPolicies() {
    wx.navigateTo({ url: '/pages/policies/index' })
  },

  startBooking() {
    wx.navigateTo({ url: '/pages/booking-form/index' })
  },

  requestDeletion() {
    if (this.data.deleting) return
    wx.showModal({
      title: '申请删除个人数据？',
      content: '有未完成预约时申请可能无法立即完成。处理完成后预约中的敏感信息会被匿名化，登录状态也会失效。',
      confirmText: '提交申请',
      success: async (result: any) => {
        if (!result.confirm) return
        this.setData({ deleting: true })
        try {
          await requestDataDeletion()
          wx.showModal({
            title: '申请已提交',
            content: '摄影师会在后台核对未完成预约并处理你的申请。',
            showCancel: false
          })
        } catch (error) {
          wx.showModal({
            title: '申请未提交',
            content: (error as Error).message || '请稍后重试。',
            showCancel: false
          })
        } finally {
          this.setData({ deleting: false })
        }
      }
    })
  }
})
