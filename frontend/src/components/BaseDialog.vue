<template>
  <v-dialog
    :model-value="modelValue"
    :max-width="maxWidth"
    :width="width"
    :persistent="persistent"
    :scrollable="scrollable"
    transition="pm-dialog"
    @update:model-value="onModelUpdate"
  >
    <v-card :class="['pm-dialog', `pm-dialog--${variant}`, cardClass]">
      <header :class="['pm-dialog__header', headerClass]">
        <div class="pm-dialog__title-wrap">
          <slot name="icon">
            <v-icon v-if="icon" size="20" class="pm-dialog__title-icon">{{ icon }}</v-icon>
          </slot>
          <div class="pm-dialog__title-block">
            <h2 class="pm-dialog__title">{{ title }}</h2>
            <p v-if="headerSubtitle" class="pm-dialog__subtitle">{{ headerSubtitle }}</p>
          </div>
        </div>
        <div class="pm-dialog__header-actions">
          <slot name="header-actions" />
          <v-btn
            icon="mdi-close"
            size="small"
            variant="text"
            class="pm-dialog__close-btn"
            :disabled="loading || persistent"
            aria-label="Dialog schließen"
            @click="onCloseClick"
          />
        </div>
      </header>

      <div class="pm-dialog__content-wrap">
        <section ref="contentRef" :class="['pm-dialog__content', bodyClass]">
          <p v-if="description" :class="['pm-dialog__description', { 'pm-dialog__description--destructive': variant === 'destructive' }]">
            {{ description }}
          </p>
          <slot />

          <div v-if="dangerRequireConfirmText" class="pm-dialog__danger-confirm">
            <label class="pm-dialog__danger-confirm-label" :for="dangerInputId">
              Tippe {{ dangerRequireConfirmText }}, um zu bestätigen.
            </label>
            <v-text-field
              :id="dangerInputId"
              ref="dangerInputRef"
              v-model="dangerInput"
              density="comfortable"
              variant="outlined"
              hide-details
            />
          </div>
        </section>
      </div>

      <footer :class="['pm-dialog__footer', footerClass]">
        <slot name="footer">
          <v-btn
            v-if="showSecondary"
            variant="text"
            class="pm-dialog__btn"
            :disabled="loading"
            @click="onSecondaryClick"
          >
            {{ secondaryText }}
          </v-btn>
          <v-btn
            ref="primaryButtonRef"
            :variant="primaryButtonVariant"
            :color="primaryButtonColor"
            class="pm-dialog__btn"
            :loading="loading"
            :disabled="isPrimaryDisabled"
            @click="onPrimaryClick"
          >
            {{ resolvedPrimaryText }}
          </v-btn>
        </slot>
      </footer>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

let openDialogCount = 0;

function syncGlobalModalState() {
  if (typeof document === 'undefined') {
    return;
  }
  document.body.classList.toggle('pm-modal-open', openDialogCount > 0);
}

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, required: true },
  headerSubtitle: { type: String, default: '' },
  description: { type: String, default: '' },
  variant: {
    type: String,
    default: 'confirm',
    validator: (value) => ['info', 'confirm', 'destructive'].includes(value)
  },
  primaryText: { type: String, default: '' },
  secondaryText: { type: String, default: 'Abbrechen' },
  showSecondary: { type: Boolean, default: true },
  icon: { type: String, default: '' },
  maxWidth: { type: [String, Number], default: 720 },
  width: { type: [String, Number], default: undefined },
  persistent: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  primaryDisabled: { type: Boolean, default: false },
  dangerRequireConfirmText: { type: String, default: '' },
  scrollable: { type: Boolean, default: false },
  cardClass: { type: [String, Array, Object], default: '' },
  headerClass: { type: [String, Array, Object], default: '' },
  bodyClass: { type: [String, Array, Object], default: '' },
  footerClass: { type: [String, Array, Object], default: '' }
});

const emit = defineEmits(['update:modelValue', 'primary', 'secondary', 'close']);

const contentRef = ref(null);
const dangerInputRef = ref(null);
const primaryButtonRef = ref(null);
const dangerInput = ref('');
const isCountedAsOpen = ref(false);
const dangerInputId = `pm-dialog-danger-input-${Math.random().toString(36).slice(2, 10)}`;

const resolvedPrimaryText = computed(() => {
  if (props.primaryText) {
    return props.primaryText;
  }
  if (props.variant === 'info') {
    return 'OK';
  }
  if (props.variant === 'destructive') {
    return 'Löschen';
  }
  return 'Bestätigen';
});

const primaryButtonVariant = computed(() => {
  if (props.variant === 'info') {
    return 'tonal';
  }
  if (props.variant === 'destructive') {
    return 'tonal';
  }
  return 'tonal';
});

const primaryButtonColor = computed(() => {
  if (props.variant === 'destructive') {
    return 'error';
  }
  return 'primary';
});

const hasDangerRequirement = computed(() => props.dangerRequireConfirmText.trim().length > 0);
const isDangerConfirmationValid = computed(() => {
  if (!hasDangerRequirement.value) {
    return true;
  }
  return dangerInput.value.trim() === props.dangerRequireConfirmText.trim();
});

const isPrimaryDisabled = computed(() => {
  return props.loading || props.primaryDisabled || !isDangerConfirmationValid.value;
});

function closeDialog() {
  emit('update:modelValue', false);
  emit('close');
}

function registerOpen() {
  if (isCountedAsOpen.value) {
    return;
  }
  openDialogCount += 1;
  isCountedAsOpen.value = true;
  syncGlobalModalState();
}

function registerClose() {
  if (!isCountedAsOpen.value) {
    return;
  }
  openDialogCount = Math.max(0, openDialogCount - 1);
  isCountedAsOpen.value = false;
  syncGlobalModalState();
}

function onModelUpdate(value) {
  emit('update:modelValue', value);
  if (!value) {
    emit('close');
  }
}

function onCloseClick() {
  if (props.loading || props.persistent) {
    return;
  }
  closeDialog();
}

function onSecondaryClick() {
  if (props.loading) {
    return;
  }
  emit('secondary');
  closeDialog();
}

function onPrimaryClick() {
  if (isPrimaryDisabled.value) {
    return;
  }
  emit('primary');
}

function focusElement(target) {
  if (!target) {
    return false;
  }
  if (typeof target.focus === 'function') {
    target.focus();
    return true;
  }
  if (target.$el && typeof target.$el.focus === 'function') {
    target.$el.focus();
    return true;
  }
  return false;
}

async function focusPreferredTarget() {
  await nextTick();

  if (hasDangerRequirement.value && focusElement(dangerInputRef.value)) {
    return;
  }

  const firstInput = contentRef.value?.querySelector('input, textarea, [contenteditable="true"], [role="combobox"]');
  if (focusElement(firstInput)) {
    return;
  }

  focusElement(primaryButtonRef.value);
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      registerClose();
      return;
    }
    registerOpen();
    dangerInput.value = '';
    void focusPreferredTarget();
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  registerClose();
});
</script>

<style scoped>
.pm-dialog {
  border-radius: 20px;
  background: rgb(var(--v-theme-surface));
  border: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  outline: none;
  box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.12));
}

.pm-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}

.pm-dialog__title-wrap {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.pm-dialog__title-icon {
  opacity: 0.9;
  margin-top: 2px;
}

.pm-dialog__title-block {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.pm-dialog__title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 650;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pm-dialog__subtitle {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.35;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.pm-dialog__header-actions {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pm-dialog__close-btn {
  flex: 0 0 auto;
}

.pm-dialog__content-wrap {
  max-height: min(68vh, 760px);
  overflow: auto;
}

.pm-dialog__content {
  padding: 20px 24px;
}

.pm-dialog__description {
  margin: 0 0 12px;
  font-size: 0.92rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.pm-dialog__description--destructive {
  color: rgba(var(--v-theme-error), 0.86);
  opacity: 0.92;
}

.pm-dialog__danger-confirm {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.pm-dialog__danger-confirm-label {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.pm-dialog__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
}

.pm-dialog__btn {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
}

@media (max-width: 900px) {
  .pm-dialog__header,
  .pm-dialog__content,
  .pm-dialog__footer {
    padding-left: 18px;
    padding-right: 18px;
  }
}
</style>
