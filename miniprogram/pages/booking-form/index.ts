import { ApiError, createIdempotencyKey } from '../../services/api'
import { createBooking, fetchBookingDetail, updateBooking } from '../../services/bookings'
import { fetchAvailability } from '../../services/public'
import type { BookingDetail, BookingOptionGroup, PolicyVersions } from '../../services/types'
import { getBookingOptions, getBootstrap } from '../../store/app'
import { currentAndFutureMonths, formatDate, periodName } from '../../utils/format'

const DRAFT_STORAGE_KEY = 'yuepai_booking_draft_v1'
const SUPPORTED_GROUPS = ['shoot_type', 'style', 'equipment_feel', 'props', 'budget', 'location']

const EMPTY_DRAFT = {
  shootType: '',
  style: '',
  shootMethod: '',
  props: [] as string[],
  budget: '',
  participantCount: 1,
  date: '',
  period: '',
  location: '',
  customLocation: '',
  name: '',
  phone: '',
  remark: '',
  termsAccepted: false
}

function groupItems(groups: BookingOptionGroup[], code: string): any[] {
  return groups.find((group) => group.code === code)?.items || []
}

function itemName(items: any[], code: string, fallback: string): string {
  return items.find((item) => item.code === code)?.name || fallback
}

function persistedDraft(draft: any, versions: PolicyVersions) {
  return {
    policyVersions: versions,
    shootType: draft.shootType,
    style: draft.style,
    shootMethod: draft.shootMethod,
    props: draft.props,
    budget: draft.budget,
    participantCount: Number(draft.participantCount) || 1,
    date: draft.date,
    period: draft.period,
    location: draft.location
  }
}

Page({
  data: {
    step: 1,
    steps: [
      { number: 1, label: '需求' },
      { number: 2, label: '档期' },
      { number: 3, label: '联系' }
    ],
    loading: true,
    submitting: false,
    errorMessage: '',
    isEditing: false,
    bookingNo: '',
    bookingVersion: 0,
    currentPhoneMasked: '',
    idempotencyKey: '',
    optionGroups: [] as BookingOptionGroup[],
    shootTypes: [] as any[],
    styles: [] as any[],
    shootMethods: [] as any[],
    props: [] as any[],
    budgets: [] as any[],
    locations: [] as any[],
    months: currentAndFutureMonths(12),
    activeMonthIndex: 0,
    monthTitle: '',
    canPreviousMonth: false,
    canNextMonth: true,
    availableDates: [] as any[],
    periods: [] as any[],
    policyVersions: { privacy: '', service_terms: '' },
    summary: {
      shootType: '未选择',
      style: '未选择',
      shootMethod: '未选择',
      schedule: '待选择',
      location: '待选择',
      budget: '待选择'
    },
    draft: { ...EMPTY_DRAFT }
  },

  onLoad(options: Record<string, string>) {
    this.initialize(options)
  },

  async initialize(options: Record<string, string>) {
    this.setData({ loading: true, errorMessage: '' })
    try {
      const detailPromise = options.bookingNo
        ? fetchBookingDetail(options.bookingNo)
        : Promise.resolve(null)
      const [groups, bootstrap, detail] = await Promise.all([
        getBookingOptions(),
        getBootstrap(),
        detailPromise
      ])
      const unsupportedRequired = groups.find(
        (group) => group.is_required && !SUPPORTED_GROUPS.includes(group.code)
      )
      if (unsupportedRequired) {
        throw new Error(`预约配置包含暂不支持的必选项“${unsupportedRequired.name}”，请联系摄影师。`)
      }

      let draft = { ...EMPTY_DRAFT }
      if (detail) {
        draft = this.draftFromDetail(detail)
      } else {
        const saved = wx.getStorageSync(DRAFT_STORAGE_KEY) as any
        if (
          saved?.policyVersions?.privacy === bootstrap.policy_versions.privacy &&
          saved?.policyVersions?.service_terms === bootstrap.policy_versions.service_terms
        ) {
          draft = { ...draft, ...saved, termsAccepted: false }
        } else if (saved) {
          wx.removeStorageSync(DRAFT_STORAGE_KEY)
        }
      }
      if (options.type && groupItems(groups, 'shoot_type').some((item) => item.code === options.type)) {
        draft.shootType = options.type
      }

      const months = currentAndFutureMonths(bootstrap.booking_horizon_months || 12)
      const targetMonth = draft.date ? draft.date.slice(0, 7) : months[0]
      const activeMonthIndex = Math.max(0, months.indexOf(targetMonth))
      const availability = await fetchAvailability(months[activeMonthIndex])
      const props = groupItems(groups, 'props').map((item) => ({
        ...item,
        selected: draft.props.includes(item.code)
      }))
      const availableDates = this.mapDates(availability.dates)
      const selectedDate = availableDates.find((item) => item.date === draft.date)
      const periods = selectedDate?.periods || []
      if (draft.period && !periods.some((item: any) => item.code === draft.period)) {
        draft.period = ''
      }

      this.setData({
        loading: false,
        isEditing: Boolean(detail),
        bookingNo: detail?.booking_no || '',
        bookingVersion: detail?.version || 0,
        currentPhoneMasked: detail?.contact.phone_masked || '',
        optionGroups: groups,
        shootTypes: groupItems(groups, 'shoot_type').map((item) => ({
          ...item,
          mark: item.metadata?.mark || '摄影',
          note: item.description || ''
        })),
        styles: groupItems(groups, 'style'),
        shootMethods: groupItems(groups, 'equipment_feel'),
        props,
        budgets: groupItems(groups, 'budget'),
        locations: groupItems(groups, 'location'),
        months,
        policyVersions: bootstrap.policy_versions,
        activeMonthIndex,
        monthTitle: this.monthTitle(months[activeMonthIndex]),
        canPreviousMonth: activeMonthIndex > 0,
        canNextMonth: activeMonthIndex < months.length - 1,
        availableDates,
        periods,
        draft
      })
      this.refreshSummary(draft)
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '预约表单加载失败，请稍后重试。'
      })
    }
  },

  draftFromDetail(detail: BookingDetail) {
    const selected = (code: string) => (detail.selections[code] || []).map((item) => item.code)
    return {
      ...EMPTY_DRAFT,
      shootType: selected('shoot_type')[0] || '',
      style: selected('style')[0] || '',
      shootMethod: selected('equipment_feel')[0] || '',
      props: selected('props'),
      budget: detail.budget_code || selected('budget')[0] || '',
      participantCount: detail.participant_count,
      date: detail.requested_date,
      period: detail.requested_period_code,
      location: detail.location.code || (detail.location.type === 'custom' ? 'custom' : ''),
      customLocation: detail.location.text || '',
      name: detail.contact.name,
      phone: '',
      remark: detail.remark || '',
      termsAccepted: true
    }
  },

  mapDates(dates: any[]) {
    return dates
      .map((item) => ({
        ...item,
        label: String(Number(item.date.slice(8, 10))),
        week: `周${'日一二三四五六'[new Date(`${item.date}T00:00:00+08:00`).getDay()]}`,
        periods: item.periods.filter((period: any) => period.available)
      }))
      .filter((item) => item.periods.length > 0)
  },

  monthTitle(month: string): string {
    const [year, monthNumber] = month.split('-')
    return `${year}年${Number(monthNumber)}月`
  },

  async changeMonth(event: any) {
    const direction = Number(event.currentTarget.dataset.direction)
    const nextIndex = this.data.activeMonthIndex + direction
    if (nextIndex < 0 || nextIndex >= this.data.months.length) return
    this.setData({ loading: true, errorMessage: '' })
    try {
      const result = await fetchAvailability(this.data.months[nextIndex])
      const availableDates = this.mapDates(result.dates)
      this.setData({
        loading: false,
        activeMonthIndex: nextIndex,
        monthTitle: this.monthTitle(this.data.months[nextIndex]),
        canPreviousMonth: nextIndex > 0,
        canNextMonth: nextIndex < this.data.months.length - 1,
        availableDates,
        periods: [],
        'draft.date': '',
        'draft.period': '',
        'summary.schedule': '待选择'
      })
      this.saveDraft()
    } catch (error) {
      this.setData({
        loading: false,
        errorMessage: (error as Error).message || '档期加载失败，请稍后重试。'
      })
    }
  },

  selectSingle(event: any) {
    const field = String(event.currentTarget.dataset.field)
    const code = String(event.currentTarget.dataset.code)
    const updates: Record<string, any> = { [`draft.${field}`]: code }
    if (field === 'date') {
      const selectedDate = this.data.availableDates.find((item: any) => item.date === code)
      updates.periods = selectedDate?.periods || []
      if (!(selectedDate?.periods || []).some((item: any) => item.code === this.data.draft.period)) {
        updates['draft.period'] = ''
      }
    }
    if (field === 'location' && code !== 'custom') updates['draft.customLocation'] = ''
    this.setData(updates)
    this.refreshSummary({ ...this.data.draft, [field]: code })
    this.saveDraft()
  },

  toggleProp(event: any) {
    const code = String(event.currentTarget.dataset.code)
    const selected = [...this.data.draft.props]
    const index = selected.indexOf(code)
    if (index >= 0) selected.splice(index, 1)
    else {
      const group = this.data.optionGroups.find((item: BookingOptionGroup) => item.code === 'props')
      if (group && selected.length >= group.max_select) {
        wx.showToast({ title: `最多选择 ${group.max_select} 项`, icon: 'none' })
        return
      }
      selected.push(code)
    }
    this.setData({
      'draft.props': selected,
      props: this.data.props.map((item: any) => ({ ...item, selected: selected.includes(item.code) }))
    })
    this.saveDraft()
  },

  onInput(event: any) {
    const field = String(event.currentTarget.dataset.field)
    this.setData({ [`draft.${field}`]: event.detail.value })
    if (!['name', 'phone', 'remark', 'customLocation'].includes(field)) this.saveDraft()
  },

  refreshSummary(draft = this.data.draft) {
    const date = this.data.availableDates.find((item: any) => item.date === draft.date)
    this.setData({
      summary: {
        shootType: itemName(this.data.shootTypes, draft.shootType, '未选择'),
        style: itemName(this.data.styles, draft.style, '未选择'),
        shootMethod: itemName(this.data.shootMethods, draft.shootMethod, '未选择'),
        schedule: draft.date
          ? `${formatDate(draft.date)}${draft.period ? ` · ${periodName(draft.period)}` : ''}`
          : '待选择',
        location: itemName(this.data.locations, draft.location, '待选择'),
        budget: itemName(this.data.budgets, draft.budget, '待选择')
      },
      periods: date?.periods || this.data.periods
    })
  },

  saveDraft() {
    if (this.data.isEditing || !this.data.policyVersions.privacy) return
    wx.setStorageSync(
      DRAFT_STORAGE_KEY,
      persistedDraft(this.data.draft, this.data.policyVersions)
    )
  },

  toggleTerms() {
    this.setData({ 'draft.termsAccepted': !this.data.draft.termsAccepted })
  },

  openPolicies() {
    wx.navigateTo({ url: '/pages/policies/index' })
  },

  previousStep() {
    if (this.data.step > 1) this.setData({ step: this.data.step - 1 })
  },

  nextStep() {
    const draft = this.data.draft
    if (this.data.step === 1) {
      if (!draft.shootType || !draft.style || !draft.shootMethod) {
        wx.showToast({ title: '请补全拍摄类型、风格和成片质感', icon: 'none' })
        return
      }
      const participantCount = Number(draft.participantCount)
      if (!Number.isInteger(participantCount) || participantCount < 1 || participantCount > 10) {
        wx.showToast({ title: '拍摄人数应为 1–10 人', icon: 'none' })
        return
      }
    }
    if (this.data.step === 2) {
      if (!draft.date || !draft.period || !draft.location || !draft.budget) {
        wx.showToast({ title: '请补全日期、时段、地点和预算', icon: 'none' })
        return
      }
      if (draft.location === 'custom' && !draft.customLocation.trim()) {
        wx.showToast({ title: '请填写意向地点', icon: 'none' })
        return
      }
    }
    this.setData({ step: this.data.step + 1 })
    wx.pageScrollTo({ scrollTop: 0, duration: 240 })
  },

  selections() {
    const draft = this.data.draft
    return {
      shoot_type: [draft.shootType],
      style: [draft.style],
      equipment_feel: [draft.shootMethod],
      props: draft.props,
      budget: [draft.budget],
      location: [draft.location]
    }
  },

  async submitBooking() {
    if (this.data.submitting) return
    const draft = this.data.draft
    if (!this.data.isEditing && !draft.name.trim()) {
      wx.showToast({ title: '请输入联系人', icon: 'none' })
      return
    }
    if (!this.data.isEditing && !/^1\d{10}$/.test(draft.phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (this.data.isEditing && draft.phone && !/^1\d{10}$/.test(draft.phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!draft.termsAccepted) {
      wx.showToast({ title: '请先阅读并同意相关说明', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    try {
      const location = draft.location === 'custom'
        ? { type: 'custom' as const, text: draft.customLocation.trim() }
        : { type: 'preset' as const, code: draft.location }
      let booking: BookingDetail
      if (this.data.isEditing) {
        const payload: any = {
          version: this.data.bookingVersion,
          requested_date: draft.date,
          requested_period_code: draft.period,
          participant_count: Number(draft.participantCount),
          budget_code: draft.budget,
          location,
          selections: this.selections(),
          remark: draft.remark
        }
        if (draft.phone) payload.contact = { name: draft.name.trim(), phone: draft.phone }
        booking = await updateBooking(this.data.bookingNo, payload)
      } else {
        const idempotencyKey = this.data.idempotencyKey || createIdempotencyKey()
        if (!this.data.idempotencyKey) this.setData({ idempotencyKey })
        booking = await createBooking({
          requested_date: draft.date,
          requested_period_code: draft.period,
          participant_count: Number(draft.participantCount),
          budget_code: draft.budget,
          location,
          selections: this.selections(),
          contact: { name: draft.name.trim(), phone: draft.phone },
          remark: draft.remark,
          privacy_policy_version: this.data.policyVersions.privacy,
          service_terms_version: this.data.policyVersions.service_terms
        }, idempotencyKey)
      }
      wx.removeStorageSync(DRAFT_STORAGE_KEY)
      wx.showToast({ title: this.data.isEditing ? '预约已更新' : '预约意向已提交', icon: 'success' })
      setTimeout(() => {
        wx.redirectTo({
          url: `/pages/booking-detail/index?bookingNo=${encodeURIComponent(booking.booking_no)}${this.data.isEditing ? '' : '&new=1'}`
        })
      }, 500)
    } catch (error) {
      const apiError = error as ApiError
      if (apiError.code === 'POLICY_VERSION_OUTDATED') {
        const bootstrap = await getBootstrap(true)
        this.setData({
          policyVersions: bootstrap.policy_versions,
          'draft.termsAccepted': false,
          idempotencyKey: ''
        })
        wx.showModal({
          title: '相关说明已更新',
          content: '请重新阅读拍摄须知与隐私说明后再提交。',
          showCancel: false
        })
      } else {
        wx.showModal({
          title: '提交未完成',
          content: `${apiError.message || '请稍后重试。'}${apiError.requestId ? `\n请求编号：${apiError.requestId}` : ''}`,
          showCancel: false
        })
      }
    } finally {
      this.setData({ submitting: false })
    }
  },

  retryLoad() {
    const pages = getCurrentPages()
    const current = pages[pages.length - 1] as any
    this.initialize(current?.options || {})
  }
})
