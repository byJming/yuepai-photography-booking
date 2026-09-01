type SelectionMap = Record<string, Array<{ code: string; name: string }>>

const BOOKING_EVENT_LABELS: Record<string, string> = {
  submitted: '客户提交预约',
  customer_updated: '客户更新预约',
  customer_cancelled: '客户取消预约',
  info_requested: '摄影师请求补充信息',
  reschedule_proposed: '摄影师建议改期',
  confirmed: '摄影师确认预约',
  declined: '摄影师婉拒预约',
  completed: '拍摄已完成',
  admin_cancelled: '摄影师取消预约',
  request_info: '摄影师请求补充信息',
  propose_reschedule: '摄影师建议改期',
  confirm: '摄影师确认预约',
  decline: '摄影师婉拒预约',
  complete: '拍摄已完成',
  admin_cancel: '摄影师取消预约',
}

const OPTION_GROUP_LABELS: Record<string, string> = {
  shoot_type: '拍摄类型',
  style: '拍摄风格',
  equipment_feel: '成片质感',
  props: '自带道具',
  budget: '预算范围',
  location: '拍摄地点',
}

const PORTFOLIO_CATEGORY_LABELS: Record<string, string> = {
  portrait: '个人写真',
  couple: '情侣记录',
  graduation: '毕业季',
  city: '城市跟拍',
}

export function bookingEventText(eventType: string): string {
  return BOOKING_EVENT_LABELS[eventType] || '预约状态更新'
}

export function optionGroupText(groupCode: string): string {
  return OPTION_GROUP_LABELS[groupCode] || '其他选择'
}

export function selectionText(
  selections: SelectionMap,
  groupCode: string,
  emptyText = '未填写',
): string {
  return selections[groupCode]?.map((item) => item.name).filter(Boolean).join('、') || emptyText
}

export function portfolioCategoryText(categoryCode: string): string {
  return PORTFOLIO_CATEGORY_LABELS[categoryCode] || '其他'
}
