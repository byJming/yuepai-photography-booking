import { getBootstrap } from './store/app'

App({
  globalData: {
    brandName: '摄影预约'
  },

  async onLaunch() {
    try {
      const bootstrap = await getBootstrap()
      this.globalData.brandName = bootstrap.brand.name || '摄影预约'
    } catch (_error) {
      this.globalData.brandName = '摄影预约'
    }
  }
})
