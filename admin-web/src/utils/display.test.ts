import { describe, expect, it } from 'vitest'

import {
  bookingEventText,
  optionGroupText,
  portfolioCategoryText,
  selectionText,
} from './display'

describe('bookingEventText', () => {
  it('maps persisted event types to concise Chinese labels', () => {
    expect(bookingEventText('customer_cancelled')).toBe('客户取消预约')
    expect(bookingEventText('customer_updated')).toBe('客户更新预约')
    expect(bookingEventText('unknown_event')).toBe('预约状态更新')
  })
})

describe('optionGroupText', () => {
  it('never exposes internal field names in the primary UI', () => {
    expect(optionGroupText('shoot_type')).toBe('拍摄类型')
    expect(optionGroupText('equipment_feel')).toBe('成片质感')
    expect(optionGroupText('unknown_group')).toBe('其他选择')
  })
})

describe('selectionText', () => {
  it('uses saved Chinese option names instead of internal codes', () => {
    expect(
      selectionText(
        { budget: [{ code: 'budget_300_500', name: '300–500 元' }] },
        'budget',
      ),
    ).toBe('300–500 元')
    expect(selectionText({}, 'budget')).toBe('未填写')
  })
})

describe('portfolioCategoryText', () => {
  it('maps public category codes to Chinese names', () => {
    expect(portfolioCategoryText('portrait')).toBe('个人写真')
    expect(portfolioCategoryText('other')).toBe('其他')
  })
})
