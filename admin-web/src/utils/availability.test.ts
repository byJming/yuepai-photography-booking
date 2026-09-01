import { describe, expect, it } from 'vitest'

import {
  buildSlotInputs,
  datesForPreset,
  isMonthWithinHorizon,
  slotTemplateTimes,
  validateSlotDraft,
} from './availability'

describe('slotTemplateTimes', () => {
  it('returns stable Shanghai booking periods', () => {
    expect(slotTemplateTimes('morning')).toEqual({ start: '09:00', end: '11:30' })
    expect(slotTemplateTimes('afternoon')).toEqual({ start: '14:30', end: '17:00' })
    expect(slotTemplateTimes('sunset')).toEqual({ start: '17:30', end: '19:30' })
  })
})

describe('validateSlotDraft', () => {
  it('rejects empty, reversed, and cross-month input', () => {
    expect(validateSlotDraft('2026-08', [], '14:30', '17:00')).toBe('请至少选择一个日期。')
    expect(validateSlotDraft('2026-08', ['2026-08-10'], '17:00', '14:30')).toBe('结束时间必须晚于开始时间。')
    expect(validateSlotDraft('2026-08', ['2026-09-01'], '14:30', '17:00')).toBe('所选日期必须属于当前月份。')
  })
})

describe('buildSlotInputs', () => {
  it('keeps an explicit Shanghai timezone for every selected date', () => {
    expect(
      buildSlotInputs(
        ['2026-08-10', '2026-08-12'],
        '14:30',
        '17:00',
        'open',
        '公开说明',
        '内部备注',
      ),
    ).toEqual([
      {
        start_at: '2026-08-10T14:30:00+08:00',
        end_at: '2026-08-10T17:00:00+08:00',
        status: 'open',
        public_note: '公开说明',
        internal_note: '内部备注',
      },
      {
        start_at: '2026-08-12T14:30:00+08:00',
        end_at: '2026-08-12T17:00:00+08:00',
        status: 'open',
        public_note: '公开说明',
        internal_note: '内部备注',
      },
    ])
  })
})

describe('isMonthWithinHorizon', () => {
  it('allows the current month and the following eleven months', () => {
    expect(isMonthWithinHorizon('2026-07', '2026-07', 12)).toBe(true)
    expect(isMonthWithinHorizon('2027-06', '2026-07', 12)).toBe(true)
    expect(isMonthWithinHorizon('2027-07', '2026-07', 12)).toBe(false)
    expect(isMonthWithinHorizon('2026-06', '2026-07', 12)).toBe(false)
  })
})

describe('datesForPreset', () => {
  it('builds remaining weekdays and weekends for the selected month', () => {
    expect(datesForPreset('2026-08', '2026-08-28', 'weekdays')).toEqual([
      '2026-08-28',
      '2026-08-31',
    ])
    expect(datesForPreset('2026-08', '2026-08-28', 'weekends')).toEqual([
      '2026-08-29',
      '2026-08-30',
    ])
  })
})
