import { describe, expect, it } from 'vitest'

import { actionsForStatus, actionRequiresMessage } from './booking-actions'

describe('actionsForStatus', () => {
  it('only exposes valid actions for a submitted booking', () => {
    expect(actionsForStatus('submitted').map((item) => item.value)).toEqual([
      'request_info',
      'propose_reschedule',
      'confirm',
      'decline',
    ])
  })

  it('only exposes completion and cancellation for a confirmed booking', () => {
    expect(actionsForStatus('confirmed').map((item) => item.value)).toEqual([
      'complete',
      'cancel',
    ])
  })

  it('returns no actions for waiting and terminal statuses', () => {
    expect(actionsForStatus('needs_info')).toEqual([])
    expect(actionsForStatus('reschedule_proposed')).toEqual([])
    expect(actionsForStatus('completed')).toEqual([])
  })
})

describe('actionRequiresMessage', () => {
  it('requires an explanation when the customer must make or understand a change', () => {
    expect(actionRequiresMessage('request_info')).toBe(true)
    expect(actionRequiresMessage('propose_reschedule')).toBe(true)
    expect(actionRequiresMessage('decline')).toBe(true)
    expect(actionRequiresMessage('cancel')).toBe(true)
  })

  it('does not require an explanation for confirmation or completion', () => {
    expect(actionRequiresMessage('confirm')).toBe(false)
    expect(actionRequiresMessage('complete')).toBe(false)
  })
})
