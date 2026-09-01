<script setup lang="ts">
import { ArrowLeft, ArrowRight, Delete, Edit } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { del, get, put } from '@/api/client'
import type { Slot } from '@/types'
import {
  buildSlotInputs,
  datesForPreset,
  isMonthWithinHorizon,
  slotTemplateTimes,
  type DatePreset,
  type EditableSlotStatus,
  type SlotTemplateCode,
  validateSlotDraft,
} from '@/utils/availability'

const HORIZON_MONTHS = 12

interface AvailabilityResult {
  month: string
  slots: Slot[]
  saved_count?: number
  skipped_confirmed_count?: number
}

const month = ref(currentShanghaiDate().slice(0, 7))
const slots = ref<Slot[]>([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref<number | null>(null)
const dialog = ref(false)
const dialogMode = ref<'batch' | 'edit'>('batch')
const form = reactive({
  dates: [] as string[],
  template: 'afternoon' as SlotTemplateCode,
  start: '14:30',
  end: '17:00',
  status: 'open' as EditableSlotStatus,
  publicNote: '',
  internalNote: '',
})

const monthLabel = computed(() => {
  return displayMonth(month.value)
})
const dialogTitle = computed(() => dialogMode.value === 'edit' ? '编辑档期' : '批量新增或更新档期')
const currentMonth = computed(() => currentShanghaiDate().slice(0, 7))
const canPreviousMonth = computed(() => month.value > currentMonth.value)
const canNextMonth = computed(() => month.value < addMonths(currentMonth.value, HORIZON_MONTHS - 1))

function currentShanghaiDate(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function addMonths(monthKey: string, count: number): string {
  const [yearValue, monthValue] = monthKey.split('-')
  const year = Number(yearValue || 1970)
  const monthNumber = Number(monthValue || 1)
  const date = new Date(Date.UTC(year, monthNumber - 1 + count, 1))
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`
}

function dateKey(value: Date): string {
  const year = value.getFullYear()
  const monthNumber = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${monthNumber}-${day}`
}

function disableMonth(value: Date): boolean {
  const candidate = dateKey(value).slice(0, 7)
  return !isMonthWithinHorizon(candidate, currentMonth.value, HORIZON_MONTHS)
}

function disableSlotDate(value: Date): boolean {
  const candidate = dateKey(value)
  return candidate.slice(0, 7) !== month.value || candidate < currentShanghaiDate()
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

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function statusText(status: string): string {
  return { open: '开放', blocked: '不可约', confirmed: '已确认' }[status] || status
}

function statusTag(status: string): 'success' | 'warning' | 'info' {
  if (status === 'open') return 'success'
  if (status === 'confirmed') return 'warning'
  return 'info'
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await get<AvailabilityResult>(`/availability?month=${month.value}`)
    slots.value = result.slots
  } finally {
    loading.value = false
  }
}

function applyTemplate(code: SlotTemplateCode): void {
  if (code === 'custom') return
  const times = slotTemplateTimes(code)
  form.start = times.start
  form.end = times.end
}

function resetForm(): void {
  form.dates = []
  form.template = 'afternoon'
  form.start = '14:30'
  form.end = '17:00'
  form.status = 'open'
  form.publicNote = ''
  form.internalNote = ''
}

function openBatchDialog(): void {
  dialogMode.value = 'batch'
  resetForm()
  dialog.value = true
}

function displayMonth(value: string): string {
  const [year, monthNumber] = value.split('-')
  return `${year}年${Number(monthNumber)}月`
}

function selectDatePreset(preset: DatePreset): void {
  form.dates = datesForPreset(month.value, currentShanghaiDate(), preset)
}

function openEditDialog(slot: Slot): void {
  if (slot.status === 'confirmed') return
  dialogMode.value = 'edit'
  form.dates = [slot.start_at.slice(0, 10)]
  form.template = 'custom'
  form.start = slot.start_at.slice(11, 16)
  form.end = slot.end_at.slice(11, 16)
  form.status = slot.status === 'blocked' ? 'blocked' : 'open'
  form.publicNote = slot.public_note || ''
  form.internalNote = slot.internal_note || ''
  dialog.value = true
}

async function save(): Promise<void> {
  const validationMessage = validateSlotDraft(month.value, form.dates, form.start, form.end)
  if (validationMessage) {
    ElMessage.warning(validationMessage)
    return
  }
  saving.value = true
  try {
    const result = await put<AvailabilityResult>('/availability/batch', {
      month: month.value,
      slots: buildSlotInputs(
        form.dates,
        form.start,
        form.end,
        form.status,
        form.publicNote,
        form.internalNote,
      ),
    })
    slots.value = result.slots
    const savedCount = result.saved_count ?? form.dates.length
    const skippedCount = result.skipped_confirmed_count ?? 0
    if (skippedCount) {
      ElMessage.warning(`已保存 ${savedCount} 个档期，跳过 ${skippedCount} 个已确认档期`)
    } else {
      ElMessage.success(dialogMode.value === 'edit' ? '档期已更新' : `已保存 ${savedCount} 个档期`)
    }
    dialog.value = false
  } finally {
    saving.value = false
  }
}

async function removeSlot(slot: Slot): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除 ${formatDateTime(slot.start_at)} 的档期？删除后客户将无法选择该时段。`,
      '删除档期',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    throw error
  }
  deletingId.value = slot.id
  try {
    await del(`/availability/${slot.id}?version=${slot.version}`)
    slots.value = slots.value.filter((item) => item.id !== slot.id)
    ElMessage.success('档期已删除')
  } finally {
    deletingId.value = null
  }
}

async function changeMonth(): Promise<void> {
  dialog.value = false
  await load()
}

async function shiftMonth(offset: -1 | 1): Promise<void> {
  const target = addMonths(month.value, offset)
  if (!isMonthWithinHorizon(target, currentMonth.value, HORIZON_MONTHS)) return
  month.value = target
  await changeMonth()
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>档期管理</h1>
        <p>按月维护未来 12 个月的可约时间，支持工作日、周末或整月批量配置。</p>
      </div>
      <el-button type="primary" @click="openBatchDialog">批量配置档期</el-button>
    </div>

    <div class="filter-bar availability-filter">
      <el-button-group>
        <el-button :icon="ArrowLeft" :disabled="!canPreviousMonth || loading" aria-label="上一个月" @click="shiftMonth(-1)" />
        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          format="YYYY 年 M 月"
          :clearable="false"
          :disabled-date="disableMonth"
          @change="changeMonth"
        />
        <el-button :icon="ArrowRight" :disabled="!canNextMonth || loading" aria-label="下一个月" @click="shiftMonth(1)" />
      </el-button-group>
      <strong>{{ monthLabel }}档期</strong>
      <span class="horizon-note">可配置至 {{ displayMonth(addMonths(currentMonth, HORIZON_MONTHS - 1)) }}</span>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert
      class="incremental-alert"
      type="info"
      :closable="false"
      title="批量保存只新增或更新本次选择的时段；已确认档期会自动跳过，不会删除其他档期。"
      show-icon
    />

    <div class="content-block">
      <el-table v-loading="loading" :data="slots">
        <el-table-column label="日期时间" min-width="250">
          <template #default="scope">
            {{ formatDateTime(scope.row.start_at) }} – {{ formatTime(scope.row.end_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="scope">
            <el-tag :type="statusTag(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="public_note" label="客户可见说明" min-width="180" show-overflow-tooltip />
        <el-table-column prop="internal_note" label="内部备注" min-width="180" show-overflow-tooltip />
        <el-table-column prop="booking_no" label="预约编号" min-width="170" />
        <el-table-column label="操作" fixed="right" width="124">
          <template #default="scope">
            <el-tag v-if="scope.row.status === 'confirmed'" type="warning">已锁定</el-tag>
            <template v-else>
              <el-tooltip content="编辑档期" placement="top">
                <el-button :icon="Edit" circle aria-label="编辑档期" @click="openEditDialog(scope.row)" />
              </el-tooltip>
              <el-tooltip content="删除档期" placement="top">
                <el-button
                  :icon="Delete"
                  type="danger"
                  plain
                  circle
                  aria-label="删除档期"
                  :loading="deletingId === scope.row.id"
                  @click="removeSlot(scope.row)"
                />
              </el-tooltip>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !slots.length" description="这个月还没有配置档期" />
    </div>

    <el-dialog v-model="dialog" :title="dialogTitle" width="min(680px, 94vw)" align-center destroy-on-close>
      <el-form label-position="top">
        <el-alert
          v-if="dialogMode === 'edit'"
          class="dialog-alert"
          type="warning"
          :closable="false"
          title="编辑模式只修改状态和说明；日期与时间不可变，避免生成重复档期。"
          show-icon
        />
        <el-form-item :label="dialogMode === 'edit' ? '日期' : '选择日期（可多选）'" required>
          <div v-if="dialogMode === 'batch'" class="date-presets">
            <span>快速选择</span>
            <el-button size="small" @click="selectDatePreset('all')">本月剩余日期</el-button>
            <el-button size="small" @click="selectDatePreset('weekdays')">仅工作日</el-button>
            <el-button size="small" @click="selectDatePreset('weekends')">仅周末</el-button>
            <el-button v-if="form.dates.length" size="small" text @click="form.dates = []">清空</el-button>
          </div>
          <el-date-picker
            v-model="form.dates"
            :type="dialogMode === 'edit' ? 'date' : 'dates'"
            value-format="YYYY-MM-DD"
            :disabled="dialogMode === 'edit'"
            :disabled-date="disableSlotDate"
            :placeholder="dialogMode === 'edit' ? '' : '选择一个或多个日期'"
            style="width: 100%"
          />
          <div v-if="dialogMode === 'batch'" class="selected-count">已选择 {{ form.dates.length }} 天</div>
        </el-form-item>
        <el-form-item label="时段模板" required>
          <el-radio-group
            v-model="form.template"
            :disabled="dialogMode === 'edit'"
            @change="applyTemplate"
          >
            <el-radio-button value="morning">上午 09:00–11:30</el-radio-button>
            <el-radio-button value="afternoon">下午 14:30–17:00</el-radio-button>
            <el-radio-button value="sunset">傍晚 17:30–19:30</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <div class="form-row">
          <el-form-item label="开始时间" required>
            <el-time-select
              v-model="form.start"
              start="08:00"
              step="00:30"
              end="20:00"
              :disabled="dialogMode === 'edit' || form.template !== 'custom'"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="结束时间" required>
            <el-time-select
              v-model="form.end"
              start="09:00"
              step="00:30"
              end="22:00"
              :disabled="dialogMode === 'edit' || form.template !== 'custom'"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <el-form-item label="状态" required>
          <el-radio-group v-model="form.status">
            <el-radio-button value="open">开放</el-radio-button>
            <el-radio-button value="blocked">不可约</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="客户可见说明">
          <el-input v-model="form.publicNote" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="内部备注">
          <el-input
            v-model="form.internalNote"
            type="textarea"
            :rows="3"
            maxlength="300"
            show-word-limit
            placeholder="仅管理员可见。"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ dialogMode === 'edit' ? '保存修改' : '批量保存' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.availability-filter {
  justify-content: flex-start;
  flex-wrap: wrap;
}

.incremental-alert,
.dialog-alert {
  margin-bottom: 20px;
}

.horizon-note,
.selected-count,
.date-presets > span {
  color: #64748b;
  font-size: 13px;
}

.date-presets {
  display: flex;
  width: 100%;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.selected-count {
  width: 100%;
  margin-top: 8px;
  text-align: right;
}
</style>
