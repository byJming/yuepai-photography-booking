export type AdminBookingAction =
  | 'request_info'
  | 'propose_reschedule'
  | 'confirm'
  | 'decline'
  | 'complete'
  | 'cancel'

export interface BookingActionOption {
  value: AdminBookingAction
  label: string
  targetStatus: string
}

const ACTIONS_BY_STATUS: Record<string, BookingActionOption[]> = {
  submitted: [
    { value: 'request_info', label: '要求补充信息', targetStatus: '待补充信息' },
    { value: 'propose_reschedule', label: '建议改期', targetStatus: '待客户确认改期' },
    { value: 'confirm', label: '确认预约', targetStatus: '已确认' },
    { value: 'decline', label: '婉拒预约', targetStatus: '已婉拒' },
  ],
  confirmed: [
    { value: 'complete', label: '标记完成', targetStatus: '已完成' },
    { value: 'cancel', label: '取消预约', targetStatus: '管理员已取消' },
  ],
}

const MESSAGE_REQUIRED_ACTIONS = new Set<AdminBookingAction>([
  'request_info',
  'propose_reschedule',
  'decline',
  'cancel',
])

export function actionsForStatus(status: string): BookingActionOption[] {
  return ACTIONS_BY_STATUS[status] ?? []
}

export function actionRequiresMessage(action: AdminBookingAction): boolean {
  return MESSAGE_REQUIRED_ACTIONS.has(action)
}
