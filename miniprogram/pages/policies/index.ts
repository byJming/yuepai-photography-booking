import { getBootstrap } from '../../store/app'

const FALLBACK_CONTENT = {
  service_scope: '当前提供单摄影师个人写真、情侣记录、毕业季和城市跟拍等摄影服务。城市跟拍以摄影为核心，不提供社交、陪伴、撮合或其他服务。',
  schedule_and_pricing: '小程序提交的是预约意向，不代表档期已经锁定。摄影师会在沟通后确认最终时间、地点和费用，本版本不提供在线支付。',
  safety_and_reschedule: '首次合作优先选择公共场所，未成年人需要监护人参与。迟到、改期和取消应尽早沟通，已确认预约不能由客户直接在小程序中取消。',
  privacy_and_display: '联系人、手机号、意向日期、地点、选择项和备注只用于预约沟通及履约。敏感字段在数据库中加密保存，不向其他客户公开。作品公开展示需要另行取得授权，预约服务不等于展示授权。',
  cancellation_rules: '未确认预约可以在详情页取消；已确认预约请联系摄影师处理。争议或法定义务涉及的数据可能在必要期限内限制处理，不会无限期保留。'
}

Page({
  data: {
    loading: true,
    versionText: '版本加载中',
    content: FALLBACK_CONTENT
  },

  onLoad() {
    this.loadPolicies()
  },

  async loadPolicies() {
    try {
      const bootstrap = await getBootstrap()
      this.setData({
        loading: false,
        versionText: `拍摄须知 ${bootstrap.policy_versions.service_terms} · 隐私说明 ${bootstrap.policy_versions.privacy}`,
        content: { ...FALLBACK_CONTENT, ...(bootstrap.policy_content || {}) }
      })
      wx.setNavigationBarTitle({ title: '拍摄须知与隐私说明' })
    } catch (_error) {
      this.setData({ loading: false, versionText: '当前为内置说明版本' })
    }
  }
})
