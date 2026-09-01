<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError, post, setCsrfToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface TotpSetupResult {
  secret: string
  otpauth_uri: string
  issuer: string
  account_name: string
}

interface TotpEnableResult {
  totp_enabled: boolean
  csrf_token: string
}

const router = useRouter()
const auth = useAuthStore()
const passwordLoading = ref(false)
const setupLoading = ref(false)
const enableLoading = ref(false)
const setupData = ref<TotpSetupResult | null>(null)
const qrDataUrl = ref('')
const enableCode = ref('')
const totpEnabled = computed(() => auth.admin?.totp_enabled === true)
const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
  totpCode: '',
})

function validatePassword(): string {
  if (form.oldPassword.length < 8) return '请输入当前密码。'
  if (form.newPassword.length < 12) return '新密码至少需要 12 个字符。'
  if (form.newPassword === form.oldPassword) return '新密码不能与当前密码相同。'
  if (form.newPassword !== form.confirmPassword) return '两次输入的新密码不一致。'
  if (totpEnabled.value && !/^\d{6}$/.test(form.totpCode)) return '请输入 6 位动态验证码。'
  return ''
}

async function generateTotpSetup(): Promise<void> {
  setupLoading.value = true
  try {
    const result = await post<TotpSetupResult>('/auth/totp/setup')
    const dataUrl = await QRCode.toDataURL(result.otpauth_uri, {
      errorCorrectionLevel: 'M',
      margin: 2,
      width: 240,
      color: { dark: '#3e3935', light: '#fffdf9' },
    })
    setupData.value = result
    qrDataUrl.value = dataUrl
    enableCode.value = ''
    ElMessage.success('绑定二维码已生成，请使用验证器扫码。')
  } catch (error) {
    setupData.value = null
    qrDataUrl.value = ''
    ElMessage.error(error instanceof ApiError ? error.message : '二维码生成失败，请稍后重试。')
  } finally {
    setupLoading.value = false
  }
}

async function enableTotp(): Promise<void> {
  if (!/^\d{6}$/.test(enableCode.value)) {
    ElMessage.warning('请输入验证器当前显示的 6 位动态验证码。')
    return
  }
  enableLoading.value = true
  try {
    const result = await post<TotpEnableResult>('/auth/totp/enable', { totp_code: enableCode.value })
    auth.setTotpEnabled(result.totp_enabled, result.csrf_token)
    setupData.value = null
    qrDataUrl.value = ''
    enableCode.value = ''
    ElMessage.success('动态验证码已启用，后续登录和修改密码都需要验证。')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '动态验证码启用失败，请稍后重试。')
  } finally {
    enableLoading.value = false
  }
}

async function submitPassword(): Promise<void> {
  const validationMessage = validatePassword()
  if (validationMessage) {
    ElMessage.warning(validationMessage)
    return
  }
  try {
    await ElMessageBox.confirm(
      '修改密码后，当前会话和其他已登录会话都会立即失效，需要重新登录。',
      '确认修改管理员密码',
      { type: 'warning', confirmButtonText: '修改并退出', cancelButtonText: '取消' },
    )
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    throw error
  }

  passwordLoading.value = true
  try {
    const body: { old_password: string; new_password: string; totp_code?: string } = {
      old_password: form.oldPassword,
      new_password: form.newPassword,
    }
    if (totpEnabled.value) body.totp_code = form.totpCode
    await post('/auth/change-password', body)
    setCsrfToken('')
    auth.clear()
    ElMessage.success('密码已修改，请使用新密码重新登录。')
    await router.replace({ path: '/login', query: { password_changed: '1' } })
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '密码修改失败，请稍后重试。')
  } finally {
    passwordLoading.value = false
  }
}
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>账户安全</h1>
        <p>管理管理员密码，并按需启用验证器动态验证码。</p>
      </div>
    </div>

    <div class="security-grid">
      <section class="content-block">
        <div class="security-card-heading">
          <div>
            <h2>动态验证码</h2>
            <p class="help-text">当前管理员：{{ auth.admin?.username }}</p>
          </div>
          <el-tag :type="totpEnabled ? 'success' : 'info'">
            {{ totpEnabled ? '已启用' : '未启用' }}
          </el-tag>
        </div>

        <el-alert
          v-if="totpEnabled"
          type="success"
          :closable="false"
          show-icon
          title="动态验证码已启用"
          description="后续登录和修改密码时，需要填写验证器当前显示的六位代码。"
        />

        <template v-else>
          <p class="help-text">默认不启用。启用后可降低管理员密码泄露带来的账号风险。</p>
          <el-button v-if="!setupData" type="primary" :loading="setupLoading" @click="generateTotpSetup">
            生成绑定二维码
          </el-button>

          <div v-else class="totp-setup">
            <div class="qr-code-wrap">
              <img :src="qrDataUrl" alt="动态验证码绑定二维码" />
            </div>
            <div class="totp-setup-content">
              <ol>
                <li>在 Microsoft Authenticator、Google Authenticator 等验证器中选择添加账号。</li>
                <li>扫描左侧二维码；无法扫码时，可手动输入下方密钥。</li>
                <li>填写验证器当前显示的六位代码并确认启用。</li>
              </ol>
              <dl class="totp-details">
                <div><dt>发行方</dt><dd>{{ setupData.issuer }}</dd></div>
                <div><dt>账号</dt><dd>{{ setupData.account_name }}</dd></div>
                <div class="manual-secret"><dt>手动密钥</dt><dd><code>{{ setupData.secret }}</code></dd></div>
              </dl>
              <el-form label-position="top" @submit.prevent="enableTotp">
                <el-form-item label="验证器六位代码" required>
                  <el-input
                    v-model="enableCode"
                    inputmode="numeric"
                    maxlength="6"
                    autocomplete="one-time-code"
                    placeholder="请输入 6 位数字"
                  />
                </el-form-item>
                <div class="totp-actions">
                  <el-button native-type="submit" type="primary" :loading="enableLoading">验证并启用</el-button>
                  <el-button :loading="setupLoading" @click="generateTotpSetup">重新生成二维码</el-button>
                </div>
              </el-form>
              <p class="security-hint">重新生成后，上一次二维码和手动密钥会立即失效。</p>
            </div>
          </div>
        </template>
      </section>

      <section class="content-block">
        <h2>修改密码</h2>
        <p class="help-text">
          {{ totpEnabled ? '需要同时验证当前动态验证码。' : '当前未启用动态验证码，仅验证原密码。' }}
        </p>
        <el-form label-position="top" @submit.prevent="submitPassword">
          <el-form-item label="当前密码" required>
            <el-input v-model="form.oldPassword" type="password" autocomplete="current-password" show-password />
          </el-form-item>
          <el-form-item label="新密码" required>
            <el-input v-model="form.newPassword" type="password" autocomplete="new-password" show-password />
            <p class="security-hint">至少 12 个字符，建议使用密码管理器生成并保存。</p>
          </el-form-item>
          <el-form-item label="确认新密码" required>
            <el-input v-model="form.confirmPassword" type="password" autocomplete="new-password" show-password />
          </el-form-item>
          <el-form-item v-if="totpEnabled" label="六位动态验证码" required>
            <el-input v-model="form.totpCode" inputmode="numeric" maxlength="6" autocomplete="one-time-code" />
          </el-form-item>
          <el-button native-type="submit" type="primary" :loading="passwordLoading" class="full-button">
            修改密码并退出所有会话
          </el-button>
        </el-form>
      </section>

      <aside class="content-block security-notes security-wide">
        <h2>安全说明</h2>
        <ul>
          <li>二维码和手动密钥只用于绑定验证器，不要截图、转发或保存到聊天记录。</li>
          <li>动态验证码一旦启用，后台不提供自助关闭入口，避免已入侵会话降低安全级别。</li>
          <li>密码修改成功后，服务端会撤销该管理员的全部 Session。</li>
          <li>若验证器设备丢失，需要在服务器侧执行受控恢复流程。</li>
        </ul>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.security-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, .85fr);
  gap: 20px;
  align-items: start;
}

.security-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.security-card-heading h2,
.security-card-heading p {
  margin-bottom: 0;
}

.totp-setup {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  gap: 24px;
  margin-top: 22px;
}

.qr-code-wrap {
  display: grid;
  place-items: center;
  align-self: start;
  min-height: 264px;
  padding: 12px;
  background: #fff;
  border: 1px solid #e7dfd5;
  border-radius: 14px;
}

.qr-code-wrap img {
  display: block;
  width: 240px;
  max-width: 100%;
  height: auto;
}

.totp-setup-content ol {
  display: grid;
  gap: 8px;
  padding-left: 20px;
  margin: 0 0 18px;
  color: #5f5a54;
  line-height: 1.6;
}

.totp-details {
  display: grid;
  gap: 10px;
  padding: 14px;
  margin: 0 0 18px;
  background: #f8f4ee;
  border-radius: 12px;
}

.totp-details div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
}

.totp-details dt {
  color: #77716a;
}

.totp-details dd {
  min-width: 0;
  margin: 0;
}

.manual-secret code {
  overflow-wrap: anywhere;
  color: #3e3935;
  font-size: 14px;
  letter-spacing: .08em;
}

.totp-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.security-hint {
  margin: 8px 0 0;
  color: #77716a;
  font-size: 13px;
}

.security-wide {
  grid-column: 1 / -1;
}

.security-notes ul {
  display: grid;
  gap: 14px;
  padding-left: 20px;
  margin: 0;
  color: #5f5a54;
  line-height: 1.7;
}

@media (max-width: 1080px) {
  .security-grid,
  .totp-setup {
    grid-template-columns: 1fr;
  }

  .qr-code-wrap {
    width: min(264px, 100%);
  }
}

@media (max-width: 560px) {
  .security-card-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .totp-actions .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>