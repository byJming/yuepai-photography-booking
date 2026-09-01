import { getBookingOptions } from '../../store/app'

Page({
  data: {
    shootTypes: [] as any[],
    loading: true,
    errorMessage: '',
    process: [
      { number: '1', title: '填写意向' },
      { number: '2', title: '沟通确认' },
      { number: '3', title: '见面拍摄' }
    ]
  },

  onLoad() {
    this.loadContent()
  },

  onShow() {
    const tabBar = this.getTabBar()
    if (tabBar) tabBar.setData({ selected: 1 })
  },

  async loadContent(force = false) {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const groups = await getBookingOptions(force)
      const shootTypeGroup = groups.find((group) => group.code === 'shoot_type')
      this.setData({
        loading: false,
        shootTypes: (shootTypeGroup?.items || []).map((item) => ({
          code: item.code,
          name: item.name,
          note: item.description || '',
          mark: item.metadata?.mark || '摄影'
        }))
      })
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '预约信息加载失败，请稍后重试。'
      })
    }
  },

  retryLoad() {
    this.loadContent(true)
  },

  startBooking() {
    wx.navigateTo({ url: '/pages/booking-form/index' })
  },

  chooseType(event: WechatMiniprogram.TouchEvent) {
    const type = String(event.currentTarget.dataset.type)
    wx.navigateTo({ url: `/pages/booking-form/index?type=${encodeURIComponent(type)}` })
  },

  openPolicies() {
    wx.navigateTo({ url: '/pages/policies/index' })
  }
})
