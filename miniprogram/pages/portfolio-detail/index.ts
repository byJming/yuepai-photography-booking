import { fetchPortfolioDetail } from '../../services/public'
import { formatShotOn } from '../../utils/format'

Page({
  data: {
    series: null as any,
    loading: true,
    errorMessage: ''
  },

  onLoad(options: Record<string, string>) {
    if (!options.slug) {
      this.setData({ loading: false, errorMessage: '作品参数无效。' })
      return
    }
    this.loadSeries(options.slug)
  },

  async loadSeries(slug: string) {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const series = await fetchPortfolioDetail(slug)
      this.setData({
        loading: false,
        series: {
          ...series,
          tags: series.style_tags || [],
          date: formatShotOn(series.shot_on),
          intro: series.description || '这组作品的拍摄故事正在整理中。'
        }
      })
      wx.setNavigationBarTitle({ title: series.title })
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '作品加载失败，请稍后重试。'
      })
    }
  },

  retryLoad() {
    const pages = getCurrentPages()
    const current = pages[pages.length - 1] as any
    const slug = current?.options?.slug
    if (slug) this.loadSeries(slug)
  },

  startBooking() {
    const type = this.data.series?.category_code || ''
    wx.navigateTo({
      url: type ? `/pages/booking-form/index?type=${encodeURIComponent(type)}` : '/pages/booking-form/index'
    })
  }
})
