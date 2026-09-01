const CATEGORY_NAMES: Record<string, string> = {
  portrait: '人像',
  couple: '情侣',
  graduation: '毕业季',
  city: '城市跟拍'
}

const PERIOD_NAMES: Record<string, string> = {
  morning: '上午',
  afternoon: '下午',
  sunset: '傍晚'
}

export function categoryName(code: string): string {
  return CATEGORY_NAMES[code] || '其他'
}

export function periodName(code: string): string {
  return PERIOD_NAMES[code] || '待确认'
}

export function formatShotOn(value?: string): string {
  if (!value) return '近期'
  const [year, month] = value.split('-')
  return `${year}.${month}`
}

export function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00+08:00`)
  return `${date.getMonth() + 1}月${date.getDate()}日 ${'日一二三四五六'[date.getDay()]}`
}

export function formatDateTime(value: string): string {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatTime(value: string): string {
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}
export function currentAndFutureMonths(count = 4): string[] {
  const now = new Date()
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() + index, 1)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  })
}
