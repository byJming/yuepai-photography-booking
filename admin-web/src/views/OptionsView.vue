<script setup lang="ts">
import { ArrowDown, ArrowUp, EditPen, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { get, patch, post } from '@/api/client'
import type { OptionGroup, OptionItem } from '@/types'

const GROUP_DESCRIPTIONS: Record<string, string> = {
  shoot_type: '客户首先选择的拍摄主题，例如个人写真、情侣记录。',
  style: '客户偏好的画面风格与氛围。',
  equipment_feel: '客户对相机或手机拍摄质感的偏好。',
  props: '客户准备携带的物品，可设置为多选。',
  budget: '客户可接受的预算范围。',
  location: '可选拍摄区域，也可保留“一起商量”。',
}

const groups = ref<OptionGroup[]>([])
const loading = ref(false)
const saving = ref(false)
const groupDialog = ref(false)
const itemDialog = ref(false)
const editingGroupId = ref<number | null>(null)
const editingItemId = ref<number | null>(null)
const groupForm = reactive({
  name: '',
  selectionMode: 'single' as 'single' | 'multiple',
  required: false,
  min: 0,
  max: 1,
})
const itemForm = reactive({
  groupId: 0,
  name: '',
  description: '',
  mark: '',
  status: 'active' as 'active' | 'disabled',
  sortOrder: 0,
})

const currentGroup = computed(() => groups.value.find((group) => group.id === itemForm.groupId))

async function load(): Promise<void> {
  loading.value = true
  try {
    groups.value = (await get<{ groups: OptionGroup[] }>('/booking-option-groups')).groups
  } finally {
    loading.value = false
  }
}

function editGroup(group: OptionGroup): void {
  editingGroupId.value = group.id
  Object.assign(groupForm, {
    name: group.name,
    selectionMode: group.selection_mode,
    required: group.is_required,
    min: group.min_select,
    max: group.max_select,
  })
  groupDialog.value = true
}

async function saveGroup(): Promise<void> {
  if (!editingGroupId.value || !groupForm.name.trim()) {
    ElMessage.warning('请填写配置名称')
    return
  }
  saving.value = true
  try {
    const single = groupForm.selectionMode === 'single'
    await patch(`/booking-option-groups/${editingGroupId.value}`, {
      name: groupForm.name.trim(),
      selection_mode: groupForm.selectionMode,
      is_required: groupForm.required,
      min_select: groupForm.required ? Math.max(1, groupForm.min) : 0,
      max_select: single ? 1 : groupForm.max,
    })
    ElMessage.success('选择规则已保存')
    groupDialog.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function toggleGroup(group: OptionGroup): Promise<void> {
  const next = group.status === 'active' ? 'disabled' : 'active'
  await patch(`/booking-option-groups/${group.id}`, { status: next })
  ElMessage.success(next === 'active' ? '该组已启用' : '该组已停用')
  await load()
}

function openItem(group: OptionGroup, item?: OptionItem): void {
  editingItemId.value = item?.id || null
  Object.assign(itemForm, {
    groupId: group.id,
    name: item?.name || '',
    description: item?.description || '',
    mark: String(item?.metadata?.mark || ''),
    status: item?.status || 'active',
    sortOrder: item?.sort_order ?? (group.items.length + 1) * 10,
  })
  itemDialog.value = true
}

async function saveItem(): Promise<void> {
  if (!itemForm.name.trim()) {
    ElMessage.warning('请填写选项名称')
    return
  }
  saving.value = true
  try {
    const metadata = currentGroup.value?.code === 'shoot_type' && itemForm.mark.trim()
      ? { mark: itemForm.mark.trim() }
      : {}
    const payload = {
      name: itemForm.name.trim(),
      description: itemForm.description.trim() || null,
      metadata,
      status: itemForm.status,
      sort_order: itemForm.sortOrder,
    }
    if (editingItemId.value) {
      await patch(`/booking-option-items/${editingItemId.value}`, payload)
      ElMessage.success('选项已保存')
    } else {
      await post('/booking-option-items', { group_id: itemForm.groupId, ...payload })
      ElMessage.success('选项已创建')
    }
    itemDialog.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function toggleItem(item: OptionItem): Promise<void> {
  const next = item.status === 'active' ? 'disabled' : 'active'
  await patch(`/booking-option-items/${item.id}`, { status: next })
  await load()
}

async function moveOption(group: OptionGroup, index: number, direction: -1 | 1): Promise<void> {
  const target = index + direction
  if (target < 0 || target >= group.items.length) return
  const reordered = [...group.items]
  const currentItem = reordered[index]
  const targetItem = reordered[target]
  if (!currentItem || !targetItem) return
  reordered[index] = targetItem
  reordered[target] = currentItem
  saving.value = true
  try {
    await Promise.all(
      reordered.map((item, position) =>
        patch(`/booking-option-items/${item.id}`, { sort_order: (position + 1) * 10 }),
      ),
    )
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-heading">
      <div>
        <h1>预约内容配置</h1>
        <p>维护客户在预约表单中看到的名称和说明，内部字段由系统自动管理。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <div v-loading="loading" class="option-groups">
      <section v-for="group in groups" :key="group.id" class="content-block option-group">
        <div class="option-group__header">
          <div>
            <div class="option-group__title">
              <h2>{{ group.name }}</h2>
              <el-tag size="small" :type="group.status === 'active' ? 'success' : 'info'">
                {{ group.status === 'active' ? '使用中' : '已停用' }}
              </el-tag>
              <el-tag size="small" effect="plain">
                {{ group.selection_mode === 'single' ? '单选' : `最多选 ${group.max_select} 项` }}
              </el-tag>
              <el-tag size="small" effect="plain">{{ group.is_required ? '必填' : '选填' }}</el-tag>
            </div>
            <p>{{ GROUP_DESCRIPTIONS[group.code] || '预约表单中的可选内容。' }}</p>
          </div>
          <div class="option-group__actions">
            <el-button @click="toggleGroup(group)">
              {{ group.status === 'active' ? '停用整组' : '启用整组' }}
            </el-button>
            <el-button :icon="EditPen" @click="editGroup(group)">选择规则</el-button>
            <el-button type="primary" :icon="Plus" @click="openItem(group)">新增选项</el-button>
          </div>
        </div>

        <el-table :data="group.items" row-key="id">
          <el-table-column prop="name" label="客户看到的名称" min-width="170" />
          <el-table-column prop="description" label="补充说明" min-width="260">
            <template #default="scope">{{ scope.row.description || '—' }}</template>
          </el-table-column>
          <el-table-column label="显示" width="100">
            <template #default="scope">
              <el-switch
                :model-value="scope.row.status === 'active'"
                :aria-label="`${scope.row.name}显示状态`"
                @change="toggleItem(scope.row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="顺序" width="110">
            <template #default="scope">
              <el-button-group>
                <el-tooltip content="上移" placement="top">
                  <el-button :icon="ArrowUp" :disabled="scope.$index === 0 || saving" aria-label="上移" @click="moveOption(group, scope.$index, -1)" />
                </el-tooltip>
                <el-tooltip content="下移" placement="top">
                  <el-button :icon="ArrowDown" :disabled="scope.$index === group.items.length - 1 || saving" aria-label="下移" @click="moveOption(group, scope.$index, 1)" />
                </el-tooltip>
              </el-button-group>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="scope">
              <el-button link type="primary" :icon="EditPen" @click="openItem(group, scope.row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!group.items.length" description="尚未添加选项" />
      </section>
      <el-empty v-if="!groups.length && !loading" description="尚未配置预约内容" />
    </div>

    <el-dialog v-model="groupDialog" title="选择规则" width="min(520px, 92vw)" align-center>
      <el-form label-position="top">
        <el-form-item label="栏目名称"><el-input v-model="groupForm.name" maxlength="40" /></el-form-item>
        <el-form-item label="客户如何选择">
          <el-radio-group v-model="groupForm.selectionMode">
            <el-radio-button value="single">只能选一项</el-radio-button>
            <el-radio-button value="multiple">可以选多项</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="是否必须填写"><el-switch v-model="groupForm.required" /></el-form-item>
        <el-form-item v-if="groupForm.selectionMode === 'multiple'" label="最多可选">
          <el-input-number v-model="groupForm.max" :min="1" :max="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveGroup">保存规则</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="itemDialog" :title="editingItemId ? '编辑选项' : '新增选项'" width="min(560px, 92vw)" align-center>
      <el-form label-position="top">
        <el-form-item label="客户看到的名称" required>
          <el-input v-model="itemForm.name" maxlength="60" placeholder="例如：日常自然" />
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="itemForm.description" type="textarea" :rows="3" maxlength="300" show-word-limit placeholder="帮助客户理解这个选项" />
        </el-form-item>
        <el-form-item v-if="currentGroup?.code === 'shoot_type'" label="卡片短标签">
          <el-input v-model="itemForm.mark" maxlength="8" placeholder="例如：人像" />
        </el-form-item>
        <el-form-item label="立即显示给客户">
          <el-switch v-model="itemForm.status" active-value="active" inactive-value="disabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveItem">保存选项</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.option-groups {
  display: grid;
  gap: 16px;
}

.option-group {
  margin-bottom: 0;
}

.option-group__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.option-group__header p {
  margin: 8px 0 0;
  color: #64748b;
}

.option-group__title,
.option-group__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.option-group__title h2 {
  margin: 0 4px 0 0;
}

@media (max-width: 760px) {
  .option-group__header {
    flex-direction: column;
  }

  .option-group__actions {
    width: 100%;
  }
}
</style>
