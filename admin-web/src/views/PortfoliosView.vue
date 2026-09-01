<script setup lang="ts">
import { ArrowDown, ArrowUp, Delete, EditPen, Plus, Star, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { api, del, get, patch, post, put } from '@/api/client'
import type { Portfolio, PortfolioDetail, PortfolioMedia } from '@/types'
import { portfolioCategoryText } from '@/utils/display'
import { moveItem } from '@/utils/collections'

const items = ref<Portfolio[]>([])
const dialog = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const editingId = ref<number | null>(null)
const media = ref<PortfolioMedia[]>([])
const coverMediaId = ref<number | null>(null)
const form = reactive({
  slug: '',
  title: '',
  subtitle: '',
  description: '',
  categoryCode: 'portrait',
  locationText: '',
  shotOn: '',
  styleTags: '',
  sortOrder: 0,
})
const dialogTitle = computed(() => editingId.value ? `编辑作品：${form.title}` : '新建作品系列')

function resetForm(): void {
  editingId.value = null
  media.value = []
  coverMediaId.value = null
  Object.assign(form, {
    slug: '',
    title: '',
    subtitle: '',
    description: '',
    categoryCode: 'portrait',
    locationText: '',
    shotOn: '',
    styleTags: '',
    sortOrder: 0,
  })
}

function generatedSlug(): string {
  return `series-${Date.now().toString(36)}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = (await get<{ items: Portfolio[] }>('/portfolio-series')).items
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  resetForm()
  dialog.value = true
}

async function openEdit(row: Portfolio): Promise<void> {
  dialog.value = true
  detailLoading.value = true
  try {
    const detail = await get<PortfolioDetail>(`/portfolio-series/${row.id}`)
    editingId.value = detail.id
    media.value = detail.media
    coverMediaId.value = detail.cover_media_id || detail.media[0]?.id || null
    Object.assign(form, {
      slug: detail.slug,
      title: detail.title,
      subtitle: detail.subtitle || '',
      description: detail.description || '',
      categoryCode: detail.category_code,
      locationText: detail.location_text || '',
      shotOn: detail.shot_on || '',
      styleTags: detail.style_tags.join('，'),
      sortOrder: detail.sort_order,
    })
  } finally {
    detailLoading.value = false
  }
}

function payload() {
  if (!form.slug) form.slug = generatedSlug()
  return {
    slug: form.slug,
    title: form.title.trim(),
    subtitle: form.subtitle.trim() || null,
    description: form.description.trim() || null,
    category_code: form.categoryCode,
    style_tags: form.styleTags.split(/[,，]/).map((value) => value.trim()).filter(Boolean),
    location_text: form.locationText.trim() || null,
    shot_on: form.shotOn || null,
    cover_media_id: coverMediaId.value,
    sort_order: form.sortOrder,
  }
}

async function createDraft(silent = false): Promise<boolean> {
  if (!form.title.trim()) {
    ElMessage.warning('请先填写作品标题')
    return false
  }
  const created = await post<Portfolio>('/portfolio-series', payload())
  editingId.value = created.id
  if (!silent) ElMessage.success('草稿已创建')
  await load()
  return true
}

async function syncMedia(): Promise<void> {
  if (!editingId.value) return
  await put(`/portfolio-series/${editingId.value}/media-order`, {
    items: media.value.map((item) => ({ media_id: item.id, caption: item.caption?.trim() || null })),
  })
  await patch(`/portfolio-series/${editingId.value}`, { cover_media_id: coverMediaId.value })
}

async function save(): Promise<boolean> {
  if (!form.title.trim()) {
    ElMessage.warning('请填写作品标题')
    return false
  }
  saving.value = true
  try {
    if (!editingId.value) return await createDraft()
    await syncMedia()
    await patch(`/portfolio-series/${editingId.value}`, payload())
    ElMessage.success('作品已保存')
    await load()
    return true
  } finally {
    saving.value = false
  }
}

async function uploadFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  if (files.length > 10) {
    ElMessage.warning('单次最多上传 10 张图片')
    return
  }
  const invalidFile = files.find(
    (file) => !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024,
  )
  if (invalidFile) {
    ElMessage.warning('仅支持 JPG、PNG、WebP，且单张图片不能超过 15 MB')
    return
  }
  if (!editingId.value && !(await createDraft(true))) return
  uploading.value = true
  try {
    for (const file of files) {
      const data = new FormData()
      data.append('file', file)
      data.append('kind', 'portfolio_image')
      const uploaded = await api<Omit<PortfolioMedia, 'caption' | 'status'>>('/media', {
        method: 'POST',
        body: data,
      })
      media.value.push({ ...uploaded, caption: '', status: 'ready' })
      if (!coverMediaId.value) coverMediaId.value = uploaded.id
      await syncMedia()
    }
    ElMessage.success(`已上传 ${files.length} 张图片`)
  } finally {
    uploading.value = false
  }
}

function setCover(item: PortfolioMedia): void {
  coverMediaId.value = item.id
}

function move(index: number, direction: -1 | 1): void {
  media.value = moveItem(media.value, index, index + direction)
}

async function removeMedia(item: PortfolioMedia): Promise<void> {
  await ElMessageBox.confirm('从当前作品移除并删除这张图片？', '删除图片', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  const previous = [...media.value]
  media.value = media.value.filter((mediaItem) => mediaItem.id !== item.id)
  if (coverMediaId.value === item.id) coverMediaId.value = media.value[0]?.id || null
  try {
    await syncMedia()
    await del(`/media/${item.id}`)
    ElMessage.success('图片已删除')
  } catch (error) {
    media.value = previous
    throw error
  }
}

async function publishCurrent(): Promise<void> {
  if (!(await save()) || !editingId.value) return
  if (!media.value.length) {
    ElMessage.warning('发布前至少上传一张图片')
    return
  }
  await ElMessageBox.confirm('确认公开发布这个作品系列？', '发布作品', {
    confirmButtonText: '发布',
    cancelButtonText: '取消',
  })
  await post(`/portfolio-series/${editingId.value}/publish`)
  ElMessage.success('作品已发布')
  dialog.value = false
  await load()
}

async function publish(row: Portfolio): Promise<void> {
  await ElMessageBox.confirm('确认发布这个作品系列？请确保图片已取得展示授权。', '发布作品')
  await post(`/portfolio-series/${row.id}/publish`)
  ElMessage.success('已发布')
  await load()
}

async function archive(row: Portfolio): Promise<void> {
  await ElMessageBox.confirm('归档后将不再公开展示，是否继续？', '归档作品', { type: 'warning' })
  await post(`/portfolio-series/${row.id}/archive`)
  ElMessage.success('已归档')
  await load()
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>作品管理</h1>
        <p>填写作品信息、上传图片并选择封面，保存后即可发布。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建作品</el-button>
    </div>

    <div class="content-block">
      <el-table v-loading="loading" :data="items">
        <el-table-column prop="title" label="作品标题" min-width="180" />
        <el-table-column label="分类" width="120">
          <template #default="scope">{{ portfolioCategoryText(scope.row.category_code) }}</template>
        </el-table-column>
        <el-table-column label="拍摄日期" width="130">
          <template #default="scope">{{ scope.row.shot_on || '未填写' }}</template>
        </el-table-column>
        <el-table-column label="图片" width="90">
          <template #default="scope">{{ scope.row.cover_media_id ? '已设置' : '未上传' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'published' ? 'success' : scope.row.status === 'archived' ? 'info' : 'warning'">
              {{ scope.row.status === 'published' ? '已发布' : scope.row.status === 'archived' ? '已归档' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
            <el-button v-if="scope.row.status !== 'published'" link type="success" @click="publish(scope.row)">发布</el-button>
            <el-button v-if="scope.row.status !== 'archived'" link type="danger" @click="archive(scope.row)">归档</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !items.length" description="尚未创建作品" />
    </div>

    <el-dialog
      v-model="dialog"
      :title="dialogTitle"
      width="min(920px, 94vw)"
      align-center
      destroy-on-close
      :close-on-click-modal="false"
      class="portfolio-dialog"
      @closed="resetForm"
    >
      <div v-loading="detailLoading" class="portfolio-dialog__content">
        <el-form label-position="top">
          <div class="form-row">
            <el-form-item label="作品标题" required><el-input v-model="form.title" maxlength="80" placeholder="例如：湖边的夏日下午" /></el-form-item>
            <el-form-item label="作品分类">
              <el-select v-model="form.categoryCode" style="width: 100%">
                <el-option label="个人写真" value="portrait" />
                <el-option label="情侣记录" value="couple" />
                <el-option label="毕业季" value="graduation" />
                <el-option label="城市跟拍" value="city" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="副标题"><el-input v-model="form.subtitle" maxlength="120" placeholder="列表中显示的一句补充说明" /></el-form-item>
          <el-form-item label="作品介绍"><el-input v-model="form.description" type="textarea" :rows="4" maxlength="5000" show-word-limit placeholder="介绍拍摄故事、氛围或创作想法" /></el-form-item>
          <div class="form-row">
            <el-form-item label="拍摄地点"><el-input v-model="form.locationText" maxlength="100" placeholder="只填写适合公开的区域" /></el-form-item>
            <el-form-item label="拍摄日期"><el-date-picker v-model="form.shotOn" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          </div>
          <el-form-item label="风格标签"><el-input v-model="form.styleTags" placeholder="例如：自然，胶片感，夏日（用逗号分隔）" /></el-form-item>
        </el-form>

        <section class="media-editor">
          <div class="block-heading media-heading">
            <div>
              <h2>作品图片</h2>
              <p>第一张图片自动作为封面，也可以手动更换和调整顺序。</p>
            </div>
            <label class="upload-label">
              <input type="file" accept="image/jpeg,image/png,image/webp" multiple @change="uploadFiles" />
              <el-button type="primary" :icon="Upload" :loading="uploading" tag="span">上传图片</el-button>
            </label>
          </div>
          <div class="media-list">
            <article v-for="(item, index) in media" :key="item.id" class="media-card">
              <div class="media-card__preview">
                <img :src="item.thumbnail_url" :alt="`作品图片 ${index + 1}`" />
                <el-tag v-if="coverMediaId === item.id" class="cover-tag" type="success">封面</el-tag>
              </div>
              <div class="media-card__body">
                <el-input v-model="item.caption" maxlength="200" placeholder="图片说明（选填）" />
                <div class="media-actions">
                  <el-tooltip content="上移" placement="top"><el-button :icon="ArrowUp" :disabled="index === 0" aria-label="上移" @click="move(index, -1)" /></el-tooltip>
                  <el-tooltip content="下移" placement="top"><el-button :icon="ArrowDown" :disabled="index === media.length - 1" aria-label="下移" @click="move(index, 1)" /></el-tooltip>
                  <el-tooltip content="设为封面" placement="top"><el-button :icon="Star" :type="coverMediaId === item.id ? 'success' : 'default'" aria-label="设为封面" @click="setCover(item)" /></el-tooltip>
                  <el-tooltip content="删除图片" placement="top"><el-button :icon="Delete" type="danger" plain aria-label="删除图片" @click="removeMedia(item)" /></el-tooltip>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-if="!media.length" :description="editingId ? '尚未上传图片，至少上传一张才能发布' : '填写标题后可直接上传，系统会自动建立草稿'" />
        </section>
      </div>

      <template #footer>
        <el-button @click="dialog = false">关闭</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ editingId ? '保存修改' : '创建草稿' }}</el-button>
        <el-button v-if="editingId" type="success" :disabled="!media.length" @click="publishCurrent">保存并发布</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.portfolio-dialog__content {
  min-height: 240px;
}

.media-heading {
  align-items: center;
}

.media-card__preview {
  position: relative;
}

.cover-tag {
  position: absolute;
  top: 10px;
  left: 10px;
}

:deep(.portfolio-dialog) {
  max-height: calc(100vh - 40px);
  margin: 20px auto;
  display: flex;
  flex-direction: column;
}

:deep(.portfolio-dialog .el-dialog__body) {
  min-height: 0;
  overflow-y: auto;
}

@media (max-width: 560px) {
  :deep(.portfolio-dialog) {
    max-height: calc(100vh - 20px);
    margin: 10px auto;
  }
}
</style>
