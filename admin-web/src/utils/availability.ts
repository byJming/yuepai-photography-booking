export type SlotTemplateCode = 'morning' | 'afternoon' | 'sunset' | 'custom'
export type EditableSlotStatus = 'open' | 'blocked'
export type DatePreset = 'all' | 'weekdays' | 'weekends'

export interface SlotInput {
  start_at: string
  end_at: string
  status: EditableSlotStatus
  public_note: string | null
  internal_note: string | null
}

const SLOT_TEMPLATE_TIMES: Record<Exclude<SlotTemplateCode, 'custom'>, { start: string; end: string }> = {
  morning: { start: '09:00', end: '11:30' },
  afternoon: { start: '14:30', end: '17:00' },
  sunset: { start: '17:30', end: '19:30' },
}

function monthIndex(month: string): number {
  const [year, monthNumber] = monthParts(month)
  return year * 12 + monthNumber - 1
}

function monthParts(month: string): [number, number] {
  const [year = '1970', monthNumber = '1'] = month.split('-')
  return [Number(year), Number(monthNumber)]
}

export function isMonthWithinHorizon(
  candidate: string,
  currentMonth: string,
  horizonMonths: number,
): boolean {
  const offset = monthIndex(candidate) - monthIndex(currentMonth)
  return offset >= 0 && offset < horizonMonths
}

export function datesForPreset(
  month: string,
  today: string,
  preset: DatePreset,
): string[] {
  if (month < today.slice(0, 7)) return []
  const [year, monthNumber] = monthParts(month)
  const lastDay = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate()
  const firstDay = month === today.slice(0, 7) ? Number(today.slice(8, 10)) : 1
  const dates: string[] = []
  for (let day = firstDay; day <= lastDay; day += 1) {
    const weekday = new Date(Date.UTC(year, monthNumber - 1, day)).getUTCDay()
    const isWeekend = weekday === 0 || weekday === 6
    if (preset === 'weekdays' && isWeekend) continue
    if (preset === 'weekends' && !isWeekend) continue
    dates.push(`${month}-${String(day).padStart(2, '0')}`)
  }
  return dates
}

export function slotTemplateTimes(code: Exclude<SlotTemplateCode, 'custom'>): {
  start: string
  end: string
} {
  return { ...SLOT_TEMPLATE_TIMES[code] }
}

export function validateSlotDraft(
  month: string,
  dates: string[],
  start: string,
  end: string,
): string {
  if (!dates.length) return '请至少选择一个日期。'
  if (!start || !end) return '请选择完整的开始和结束时间。'
  if (end <= start) return '结束时间必须晚于开始时间。'
  if (dates.some((date) => date.slice(0, 7) !== month)) return '所选日期必须属于当前月份。'
  if (dates.length > 200) return '单次最多保存 200 个档期。'
  return ''
}

export function buildSlotInputs(
  dates: string[],
  start: string,
  end: string,
  status: EditableSlotStatus,
  publicNote: string,
  internalNote: string,
): SlotInput[] {
  const normalizedPublicNote = publicNote.trim() || null
  const normalizedInternalNote = internalNote.trim() || null
  return dates.map((date) => ({
    start_at: `${date}T${start}:00+08:00`,
    end_at: `${date}T${end}:00+08:00`,
    status,
    public_note: normalizedPublicNote,
    internal_note: normalizedInternalNote,
  }))
}
