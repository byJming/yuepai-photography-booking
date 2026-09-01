<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { get, patch } from '@/api/client'

const loading = ref(true)
const savingKey = ref('')
const brand = reactive({
  name: '摄影预约',
  eyebrow: '自然人像 · 城市记录',
  monthly_title: '记录平常而珍贵的瞬间',
  monthly_subtitle: '品牌内容可在管理后台修改。',
  availability_text: '近期可约',
  service_area: '请与摄影师确认',
  about_text: '专注自然、真实的个人摄影记录。',
})
const policies = reactive({ privacy: '2026-07-26', service_terms: '2026-07-26' })
const policyContent = reactive({
  service_scope: '',
  schedule_and_pricing: '',
  safety_and_reschedule: '',
  privacy_and_display: '',
  cancellation_rules: '',
})
const rules = reactive({
  open_months: 12,
  confirmed_customer_cancel: false,
  data_retention_completed_months: 12,
  data_retention_cancelled_months: 6,
})
const featureFlags = reactive({ subscription_message: false, reference_upload: false })

async function load() {
  loading.value = true
  try {
    const data = await get<Record<string, any>>('/settings')
    Object.assign(brand, data.brand || {})
    Object.assign(policies, data.policy_versions || {})
    Object.assign(policyContent, data.policy_content || {})
    Object.assign(rules, data.booking_rules || {})
    Object.assign(featureFlags, data.feature_flags || {})
  } finally {
    loading.value = false
  }
}

async function save(key: string, value: Record<string, unknown>) {
  savingKey.value = key
  try {
    await patch(`/settings/${key}`, { value })
    ElMessage.success('设置已保存')
  } finally {
    savingKey.value = ''
  }
}

onMounted(load)
</script>

<template>
  <section class="page" v-loading="loading">
    <div class="page-heading">
      <div>
        <h1>品牌、政策与规则</h1>
        <p>公开内容保存后实时生效；政策正文实质变化时必须同步提升版本号。</p>
      </div>
    </div>

    <div class="settings-grid">
      <section class="content-block">
        <h2>品牌内容</h2>
        <el-form label-position="top">
          <el-form-item label="品牌名称"><el-input v-model="brand.name" maxlength="40" show-word-limit /></el-form-item>
          <el-form-item label="品牌短句"><el-input v-model="brand.eyebrow" maxlength="80" /></el-form-item>
          <el-form-item label="本月主题"><el-input v-model="brand.monthly_title" maxlength="80" /></el-form-item>
          <el-form-item label="主题说明"><el-input v-model="brand.monthly_subtitle" type="textarea" :rows="3" maxlength="200" show-word-limit /></el-form-item>
          <el-form-item label="服务区域"><el-input v-model="brand.service_area" maxlength="100" /></el-form-item>
          <el-form-item label="摄影师介绍"><el-input v-model="brand.about_text" type="textarea" :rows="4" maxlength="2000" show-word-limit /></el-form-item>
          <el-button type="primary" :loading="savingKey === 'brand'" @click="save('brand', { ...brand })">保存品牌内容</el-button>
        </el-form>
      </section>

      <section class="content-block settings-wide">
        <h2>拍摄须知与隐私正文</h2>
        <p class="help-text">使用纯文本，不支持任意 HTML。小程序会通过 Bootstrap 实时读取这些内容。</p>
        <el-form label-position="top">
          <el-form-item label="服务范围"><el-input v-model="policyContent.service_scope" type="textarea" :rows="4" maxlength="5000" show-word-limit /></el-form-item>
          <el-form-item label="档期与费用"><el-input v-model="policyContent.schedule_and_pricing" type="textarea" :rows="4" maxlength="5000" show-word-limit /></el-form-item>
          <el-form-item label="安全与改期"><el-input v-model="policyContent.safety_and_reschedule" type="textarea" :rows="4" maxlength="5000" show-word-limit /></el-form-item>
          <el-form-item label="隐私与作品展示"><el-input v-model="policyContent.privacy_and_display" type="textarea" :rows="5" maxlength="5000" show-word-limit /></el-form-item>
          <el-form-item label="取消与数据删除"><el-input v-model="policyContent.cancellation_rules" type="textarea" :rows="4" maxlength="5000" show-word-limit /></el-form-item>
          <el-button type="primary" :loading="savingKey === 'policy_content'" @click="save('policy_content', { ...policyContent })">保存政策正文</el-button>
        </el-form>
      </section>

      <section class="content-block">
        <h2>政策版本</h2>
        <p class="help-text">建议使用发布日期，例如 2026-07-26。版本变化后，客户旧草稿会要求重新确认。</p>
        <el-form label-position="top">
          <el-form-item label="隐私说明版本"><el-input v-model="policies.privacy" maxlength="32" /></el-form-item>
          <el-form-item label="拍摄须知版本"><el-input v-model="policies.service_terms" maxlength="32" /></el-form-item>
          <el-button type="primary" :loading="savingKey === 'policy_versions'" @click="save('policy_versions', { ...policies })">保存政策版本</el-button>
        </el-form>
      </section>

      <section class="content-block">
        <h2>预约与数据规则</h2>
        <el-form label-position="top">
          <el-form-item label="可预约月份范围">
            <el-input-number v-model="rules.open_months" :min="1" :max="12" />
            <small>从当前月起最多开放未来 12 个月。</small>
          </el-form-item>
          <el-form-item label="已确认预约允许客户直接取消">
            <el-switch v-model="rules.confirmed_customer_cancel" disabled />
            <small>当前版本固定由摄影师后台处理。</small>
          </el-form-item>
          <div class="form-row">
            <el-form-item label="已完成敏感数据保留（月）"><el-input-number v-model="rules.data_retention_completed_months" :min="1" :max="120" /></el-form-item>
            <el-form-item label="取消或婉拒保留（月）"><el-input-number v-model="rules.data_retention_cancelled_months" :min="1" :max="120" /></el-form-item>
          </div>
          <el-button type="primary" :loading="savingKey === 'booking_rules'" @click="save('booking_rules', { ...rules })">保存预约规则</el-button>
        </el-form>
      </section>

      <section class="content-block">
        <h2>候选功能开关</h2>
        <p class="help-text">以下能力尚未进入首版交付，保持关闭可避免小程序出现未配置入口。</p>
        <el-form label-position="top">
          <el-form-item label="订阅消息"><el-switch v-model="featureFlags.subscription_message" disabled /></el-form-item>
          <el-form-item label="客户参考图上传"><el-switch v-model="featureFlags.reference_upload" disabled /></el-form-item>
        </el-form>
      </section>
    </div>
  </section>
</template>
