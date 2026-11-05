<template>
  <el-dialog :model-value="modelValue" title="AI 报告设置" width="640px" append-to-body @update:model-value="$emit('update:modelValue', $event)">
    <el-alert type="info" show-icon :closable="false" class="notice" title="选择 AI 模型管理中已启用的 LLM。此设置对算法任务报告生效。" />
    <el-form v-loading="loading" :model="form" label-width="120px">
      <el-form-item label="默认 LLM" required>
        <el-select v-model="form.modelId" placeholder="选择已启用的 LLM" style="width: 100%">
          <el-option v-for="model in models" :key="model.modelId" :value="model.modelId"
            :label="`${model.modelName || model.modelCode} · ${model.provider}`" />
        </el-select>
      </el-form-item>
      <el-form-item label="自动生成报告"><el-switch v-model="form.autoEnabled" /></el-form-item>
      <p class="hint">开启后，新运行的任务成功保存结果时自动生成报告；旧任务可手动生成。</p>
      <el-form-item label="补充分析要求">
        <el-input v-model="form.instructions" type="textarea" :rows="5" maxlength="4000" show-word-limit
          placeholder="例如：重点分析高风险线路，给出巡检优先级；可补充算法字段的单位和风险阈值。" />
      </el-form-item>
    </el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-empty v-if="!loading && !models.length && !error" description="暂无可用 LLM，请先在 AI 模型管理中添加并启用模型" />
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading || !form.modelId" @click="save">保存设置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getReportConfig, listReportModels, saveReportConfig } from '@/api/algorithmReport'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const form = ref({ modelId: null, autoEnabled: false, instructions: '' })
const models = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
watch(() => props.modelValue, async visible => {
  if (!visible) return
  loading.value = true
  error.value = ''
  try {
    const [config, options] = await Promise.all([getReportConfig(), listReportModels()])
    form.value = { modelId: config.data.modelId, autoEnabled: config.data.autoEnabled, instructions: config.data.instructions }
    models.value = options.data || []
  } catch (err) {
    error.value = `加载报告设置失败：${err.message || '请稍后重试'}`
  } finally {
    loading.value = false
  }
}, { immediate: true })
async function save() {
  saving.value = true
  error.value = ''
  try {
    await saveReportConfig(form.value)
    ElMessage.success('AI 报告设置已保存')
    emit('update:modelValue', false)
  } catch (err) {
    error.value = err.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.notice { margin-bottom: 20px; }
.hint { color: var(--el-text-color-secondary); font-size: 13px; margin: -5px 0 20px 120px; }
</style>
