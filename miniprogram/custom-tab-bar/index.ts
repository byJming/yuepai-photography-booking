Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/works/index', text: '作品', icon: 'works' },
      { pagePath: '/pages/booking/index', text: '预约', icon: 'calendar' },
      { pagePath: '/pages/profile/index', text: '我的', icon: 'profile' }
    ]
  },
  methods: {
    switchTab(event: WechatMiniprogram.TouchEvent) {
      const index = Number(event.currentTarget.dataset.index)
      const url = String(event.currentTarget.dataset.path)
      this.setData({ selected: index })
      wx.switchTab({ url })
    }
  }
})
