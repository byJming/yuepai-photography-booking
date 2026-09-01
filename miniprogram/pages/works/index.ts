import { fetchPortfolios } from '../../services/public'
import type { PortfolioSummary } from '../../services/types'
import { getBootstrap } from '../../store/app'
import { categoryName, formatShotOn } from '../../utils/format'

const FALLBACK_BRAND = {
  name: '摄影预约',
  eyebrow: '自然人像 · 城市记录',
  monthlyTitle: '记录平常而珍贵的瞬间',
  monthlySubtitle: '品牌内容将在服务端配置完成后展示。'
}

const CATEGORY_CODES = ['portrait', 'couple', 'graduation', 'city']

function mapSeries(item: PortfolioSummary) {
  return {
    id: item.id,
    slug: item.slug,
    category: item.category_code,
    title: item.title,
    subtitle: item.subtitle || '',
    cover: item.cover.thumbnail_url || item.cover.url,
    date: formatShotOn(item.shot_on),
    location: item.location || '',
    tags: item.style_tags || []
  }
}

Page({
  data: {
    brand: FALLBACK_BRAND,
    availabilityStatus: { available: false, text: '档期查询中' },
    categories: [
      { code: 'all', name: '全部' },
      ...CATEGORY_CODES.map((code) => ({ code, name: categoryName(code) }))
    ],
    activeCategory: 'all',
    featuredSeries: null as any,
    visibleSeries: [] as any[],
    nextCursor: null as string | null,
    loading: true,
    loadingMore: false,
    errorMessage: ''
  },

  onLoad() {
    this.loadPage(true)
  },

  onShow() {
    const tabBar = this.getTabBar()
    if (tabBar) tabBar.setData({ selected: 0 })
  },

  onPullDownRefresh() {
    this.loadPage(true).finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.nextCursor && !this.data.loadingMore) this.loadMore()
  },

  async loadPage(force = false) {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const category = this.data.activeCategory === 'all' ? '' : this.data.activeCategory
      const [bootstrap, portfolios] = await Promise.all([
        getBootstrap(force),
        fetchPortfolios(category)
      ])
      const items = portfolios.items.map(mapSeries)
      const featuredSeries = this.data.activeCategory === 'all' ? items[0] || null : this.data.featuredSeries
      const visibleSeries = this.data.activeCategory === 'all' ? items.slice(1) : items
      this.setData({
        brand: {
          name: bootstrap.brand.name || FALLBACK_BRAND.name,
          eyebrow: bootstrap.brand.eyebrow || FALLBACK_BRAND.eyebrow,
          monthlyTitle: bootstrap.brand.monthly_title || FALLBACK_BRAND.monthlyTitle,
          monthlySubtitle: bootstrap.brand.monthly_subtitle || FALLBACK_BRAND.monthlySubtitle
        },
        availabilityStatus: bootstrap.availability_status,
        featuredSeries,
        visibleSeries,
        nextCursor: portfolios.next_cursor || null,
        loading: false
      })
      wx.setNavigationBarTitle({ title: bootstrap.brand.name || FALLBACK_BRAND.name })
    } catch (error) {
      this.setData({
        loading: false,
        availabilityStatus: { available: false, text: '档期暂不可查' },
        errorMessage: (error as Error).message || '作品加载失败，请稍后重试。'
      })
    }
  },

  async loadMore() {
    this.setData({ loadingMore: true })
    try {
      const category = this.data.activeCategory === 'all' ? '' : this.data.activeCategory
      const result = await fetchPortfolios(category, this.data.nextCursor || undefined)
      this.setData({
        visibleSeries: [...this.data.visibleSeries, ...result.items.map(mapSeries)],
        nextCursor: result.next_cursor || null
      })
    } catch (error) {
      wx.showToast({ title: (error as Error).message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loadingMore: false })
    }
  },

  selectCategory(event: WechatMiniprogram.TouchEvent) {
    const code = String(event.currentTarget.dataset.code)
    if (code === this.data.activeCategory) return
    this.setData({ activeCategory: code, visibleSeries: [], nextCursor: null })
    this.loadPage()
  },

  retryLoad() {
    this.loadPage(true)
  },

  openSeries(event: WechatMiniprogram.TouchEvent) {
    const slug = String(event.currentTarget.dataset.slug)
    if (slug) wx.navigateTo({ url: `/pages/portfolio-detail/index?slug=${encodeURIComponent(slug)}` })
  },

  startBooking() {
    wx.navigateTo({ url: '/pages/booking-form/index' })
  }
})
