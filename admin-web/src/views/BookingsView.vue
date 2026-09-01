<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { get, post } from '@/api/client'
import type { BookingDetail, BookingSummary, Slot } from '@/types'
import {
  actionRequiresMessage,
  actionsForStatus,
  type AdminBookingAction,
} from '@/utils/booking-actions'
import { bookingEventText, optionGroupText, selectionText } from '@/utils/display'

interface BookingListResult {
  items: BookingSummary[]
  page: number
  page_size: number
  total: number
}

interface AvailabilityResult {
  month: string
  slots: Slot[]
}

const route = useRoute()
const rows = ref<BookingSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const detailLoading = ref(false)
const detail = ref<BookingDetail | null>(null)
const drawer = ref(false)
const phoneRevealed = ref(false)
const actionDialog = ref(false)
const actionLoading = ref(false)
const slotsLoading = ref(false)
const slots = ref<Slot[]>([])
const filters = reactive({
  status: '',
  bookingNo: '',
  phoneLast4: '',
  dateRange: [] as string[],
})
const action = reactive({
  action: 'request_info' as AdminBookingAction,
  slotId: undefined as number | undefined,
  publicMessage: '',
  internalNote: '',
  reopenSlot: false,
})

const actionOptions = computed(() => actionsForStatus(detail.value?.status || ''))
const selectedAction = computed(() =>
  actionOptions.value.find((item) => item.value === action.action),
)
const openSlots = computed(() => slots.value.filter((slot) => slot.status === 'open'))
const messageRequired = computed(() => actionRequiresMessage(action.action))
const actionReady = computed(() => {
  if (!selectedAction.value) return false
  if (action.action === 'confirm' && !action.slotId) return false
  return !messageRequired.value || Boolean(action.publicMessage.trim())
})
const selectionEntries = computed(() => {
  if (!detail.value) return []
  const preferredOrder = ['shoot_type', 'style', 'equipment_feel', 'props', 'budget', 'location']
  const keys = [
    ...preferredOrder.filter((key) => detail.value?.selections[key]?.length),
    ...Object.keys(detail.value.selections).filter((key) => !preferredOrder.includes(key)),
  ]
  return keys.map((key) => ({
    key,
    label: optionGroupText(key),
    value: selectionText(detail.value?.selections || {}, key, '未选择'),
  }))
})
const internalNotes = computed(() =>
  detail.value?.internal_events.filter((item) => item.internal_note.trim()) || [],
)

const periodLabels: Record<string, string> = {
  morning: '上午',
  afternoon: '下午',
  sunset: '傍晚',
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date(`${value}T00:00:00+08:00`))
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function slotLabel(slot: Slot): string {
  return `${formatDateTime(slot.start_at)} – ${formatTime(slot.end_at)}${slot.public_note ? ` · ${slot.public_note}` : ''}`
}

function locationText(): string {
  if (!detail.value) return '—'
  if (detail.value.location.type === 'custom') return detail.value.location.text || '客户自定义地点'
  return selectionText(detail.value.selections, 'location', '待沟通')
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const query = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    if (filters.status) query.set('status', filters.status)
    if (filters.bookingNo.trim()) query.set('booking_no', filters.bookingNo.trim())
    if (filters.phoneLast4) query.set('phone_last4', filters.phoneLast4)
    const [dateFrom, dateTo] = filters.dateRange
    if (dateFrom && dateTo) {
      query.set('date_from', dateFrom)
      query.set('date_to', dateTo)
    }
    const result = await get<BookingListResult>(`/bookings?${query}`)
    rows.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function search(): Promise<void> {
  page.value = 1
  await load()
}

async function resetFilters(): Promise<void> {
  filters.status = ''
  filters.bookingNo = ''
  filters.phoneLast4 = ''
  filters.dateRange = []
  page.value = 1
  await load()
}

async function openDetail(row: BookingSummary): Promise<void> {
  drawer.value = true
  phoneRevealed.value = false
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await get<BookingDetail>(`/bookings/${row.booking_no}`)
  } catch (error) {
    drawer.value = false
    throw error
  } finally {
    detailLoading.value = false
  }
}

async function refreshDetail(): Promise<void> {
  if (!detail.value) return
  detail.value = await get<BookingDetail>(`/bookings/${detail.value.booking_no}`)
  phoneRevealed.value = false
}

async function loadSlots(): Promise<void> {
  if (!detail.value) return
  slotsLoading.value = true
  slots.value = []
  action.slotId = undefined
  try {
    const month = detail.value.requested_date.slice(0, 7)
    const result = await get<AvailabilityResult>(`/availability?month=${month}`)
    slots.value = result.slots
  } finally {
    slotsLoading.value = false
  }
}

async function handleActionChange(value: AdminBookingAction): Promise<void> {
  action.slotId = undefined
  if (value === 'confirm') await loadSlots()
}

async function openActionDialog(): Promise<void> {
  const firstAction = actionOptions.value[0]
  if (!firstAction) return
  action.action = firstAction.value
  action.slotId = undefined
  action.publicMessage = ''
  action.internalNote = ''
  action.reopenSlot = false
  slots.value = []
  actionDialog.value = true
  if (action.action === 'confirm') await loadSlots()
}

async function runAction(): Promise<void> {
  if (!detail.value || !selectedAction.value || !actionReady.value) return
  const publicMessage = action.publicMessage.trim()
  try {
    await ElMessageBox.confirm(
      `预约将变更为“${selectedAction.value.targetStatus}”。客户可见说明：${publicMessage || '无'}`,
      '确认处理预约',
      { type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '返回检查' },
    )
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    throw error
  }

  actionLoading.value = true
  try {
    await post(`/bookings/${detail.value.booking_no}/actions`, {
      action: action.action,
      version: detail.value.version,
      slot_id: action.action === 'confirm' ? action.slotId : undefined,
      public_message: publicMessage,
      internal_note: action.internalNote.trim(),
      reopen_slot: action.action === 'cancel' ? action.reopenSlot : false,
    })
    ElMessage.success('预约状态已更新')
    actionDialog.value = false
    await Promise.all([refreshDetail(), load()])
  } finally {
    actionLoading.value = false
  }
}

async function changePage(nextPage: number): Promise<void> {
  page.value = nextPage
  await load()
}

async function changePageSize(nextPageSize: number): Promise<void> {
  pageSize.value = nextPageSize
  page.value = 1
  await load()
}

onMounted(async () => {
  if (typeof route.query.status === 'string') filters.status = route.query.status
  if (typeof route.query.booking_no === 'string') filters.bookingNo = route.query.booking_no
  await load()
})
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>预约管理</h1>
        <p>查看客户意向，并通过受控动作推进预约状态。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-form inline class="filter-bar">
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 160px">
          <el-option label="待确认" value="submitted" />
          <el-option label="待补充" value="needs_info" />
          <el-option label="待确认改期" value="reschedule_proposed" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="已完成" value="completed" />
          <el-option label="已婉拒" value="declined" />
          <el-option label="客户已取消" value="cancelled_by_user" />
          <el-option label="管理员已取消" value="cancelled_by_admin" />
        </el-select>
      </el-form-item>
      <el-form-item label="意向日期">
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          range-separator="至"
        />
      </el-form-item>
      <el-form-item label="预约编号">
        <el-input v-model="filters.bookingNo" clearable placeholder="精确编号" />
      </el-form-item>
      <el-form-item label="手机号尾号">
        <el-input v-model="filters.phoneLast4" maxlength="4" clearable placeholder="4 位数字" />
      </el-form-item>
      <el-button type="primary" :loading="loading" @click="search">查询</el-button>
      <el-button :disabled="loading" @click="resetFilters">重置</el-button>
    </el-form>

    <div class="content-block">
      <el-table v-loading="loading" :data="rows">
        <el-table-column prop="booking_no" label="预约编号" min-width="170" />
        <el-table-column prop="status_text" label="状态" min-width="120" />
        <el-table-column prop="shoot_type" label="拍摄类型" min-width="120" />
        <el-table-column prop="requested_date" label="意向日期" min-width="120" />
        <el-table-column prop="contact_name" label="联系人" min-width="100" />
        <el-table-column prop="phone_masked" label="手机号" min-width="110" />
        <el-table-column label="提交时间" min-width="175">
          <template #default="scope">{{ formatDateTime(scope.row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="175">
          <template #default="scope">{{ formatDateTime(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="84">
          <template #default="scope">
            <el-button link type="primary" @click="openDetail(scope.row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="没有符合条件的预约" />
      <el-pagination
        v-if="total > 0"
        class="table-pagination"
        background
        layout="total, sizes, prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>

    <el-drawer v-model="drawer" title="预约详情" size="min(820px, 100%)" destroy-on-close>
      <div v-loading="detailLoading" class="booking-detail">
        <template v-if="detail">
          <div class="detail-grid">
            <div><small>预约编号</small><strong>{{ detail.booking_no }}</strong></div>
            <div><small>当前状态</small><strong>{{ detail.status_text }}</strong></div>
            <div><small>联系人</small><strong>{{ detail.contact.name }}</strong></div>
            <div>
              <small>手机号</small>
              <strong>{{ phoneRevealed ? detail.contact.phone : detail.contact.phone_masked }}</strong>
              <el-button
                v-if="detail.contact.phone !== '已清理'"
                link
                type="primary"
                class="sensitive-toggle"
                @click="phoneRevealed = !phoneRevealed"
              >
                {{ phoneRevealed ? '隐藏完整号码' : '显示完整号码' }}
              </el-button>
            </div>
            <div><small>意向日期</small><strong>{{ formatDate(detail.requested_date) }}</strong></div>
            <div><small>意向时段</small><strong>{{ periodLabels[detail.requested_period_code] || detail.requested_period_code }}</strong></div>
            <div><small>参与人数</small><strong>{{ detail.participant_count }} 人</strong></div>
            <div><small>地点</small><strong>{{ locationText() }}</strong></div>
          </div>

          <el-alert
            v-if="detail.confirmed_slot"
            type="success"
            :closable="false"
            :title="`已确认档期：${formatDateTime(detail.confirmed_slot.start_at)} – ${formatTime(detail.confirmed_slot.end_at)}`"
            :description="detail.confirmed_slot.public_note"
            show-icon
          />

          <h3>拍摄需求</h3>
          <el-descriptions v-if="selectionEntries.length" border :column="1" class="selection-list">
            <el-descriptions-item
              v-for="item in selectionEntries"
              :key="item.key"
              :label="item.label"
            >
              {{ item.value }}
            </el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="没有拍摄需求记录" :image-size="72" />

          <h3>客户备注</h3>
          <p class="detail-note">{{ detail.remark || '无' }}</p>

          <h3>公开时间线</h3>
          <el-timeline v-if="detail.timeline.length">
            <el-timeline-item
              v-for="item in detail.timeline"
              :key="`${item.event_type}-${item.created_at}`"
              :timestamp="formatDateTime(item.created_at)"
            >
              <strong>{{ bookingEventText(item.event_type) }}</strong>
              <p v-if="item.message" class="timeline-message">{{ item.message }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无公开时间线" :image-size="72" />

          <h3>内部操作记录</h3>
          <el-timeline v-if="internalNotes.length">
            <el-timeline-item
              v-for="item in internalNotes"
              :key="`${item.event_type}-${item.created_at}`"
              :timestamp="formatDateTime(item.created_at)"
            >
              <strong>{{ bookingEventText(item.event_type) }}</strong>
              <p class="timeline-message">{{ item.internal_note }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无内部备注" :image-size="72" />

          <el-button
            v-if="actionOptions.length"
            type="primary"
            class="drawer-action"
            @click="openActionDialog"
          >
            处理预约
          </el-button>
          <el-alert
            v-else
            class="drawer-action"
            type="info"
            :closable="false"
            title="当前状态没有可由管理员执行的下一步操作。"
          />
        </template>
      </div>
    </el-drawer>

    <el-dialog v-model="actionDialog" title="处理预约" width="min(560px, 92vw)" align-center destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="操作" required>
          <el-select v-model="action.action" style="width: 100%" @change="handleActionChange">
            <el-option
              v-for="item in actionOptions"
              :key="item.value"
              :label="`${item.label} → ${item.targetStatus}`"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="action.action === 'confirm'" label="开放档期" required>
          <el-select
            v-model="action.slotId"
            :loading="slotsLoading"
            filterable
            placeholder="选择预约意向月份内的开放档期"
            style="width: 100%"
          >
            <el-option
              v-for="slot in openSlots"
              :key="slot.id"
              :label="slotLabel(slot)"
              :value="slot.id"
            />
          </el-select>
          <p v-if="!slotsLoading && !openSlots.length" class="form-hint">
            该月份没有开放档期，请先到“档期管理”配置。
          </p>
        </el-form-item>
        <el-form-item :label="messageRequired ? '客户可见说明（必填）' : '客户可见说明'" :required="messageRequired">
          <el-input
            v-model="action.publicMessage"
            type="textarea"
            :rows="4"
            maxlength="300"
            show-word-limit
            placeholder="将出现在客户预约时间线中，请勿填写内部信息。"
          />
        </el-form-item>
        <el-form-item label="内部备注">
          <el-input
            v-model="action.internalNote"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="仅管理员可见，不会发送给客户。"
          />
        </el-form-item>
        <el-form-item v-if="action.action === 'cancel'">
          <el-checkbox v-model="action.reopenSlot">取消后重新开放原档期</el-checkbox>
        </el-form-item>
        <el-alert
          v-if="selectedAction"
          type="warning"
          :closable="false"
          :title="`执行后状态将变更为“${selectedAction.targetStatus}”`"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button :disabled="actionLoading" @click="actionDialog = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" :disabled="!actionReady" @click="runAction">
          确认执行
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.booking-detail {
  min-height: 240px;
}

.booking-detail h3 {
  margin-top: 28px;
  margin-bottom: 14px;
  font-size: 17px;
}

.selection-list {
  --el-descriptions-table-border: 1px solid #e5e7eb;
}

.sensitive-toggle {
  justify-content: flex-start;
  width: fit-content;
  margin-top: 4px;
}

.detail-note,
.timeline-message {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.detail-note {
  padding: 14px;
  border-radius: 10px;
  background: #f8f4ee;
  color: #4d4944;
}

.timeline-message {
  margin-top: 8px;
  margin-bottom: 0;
  color: #6f6962;
}

.form-hint {
  width: 100%;
  margin: 8px 0 0;
  color: #b55d49;
  font-size: 13px;
}
</style>
