<template>
  <div
    class="details-drawer__header"
    :class="open ? 'details-drawer__header--expanded' : 'details-drawer__header--collapsed'"
    @click="emit('toggle')"
  >
    <div class="details-drawer__inner">
      <div class="details-command-bar">
        <div class="details-command-bar__left">
          <div class="details-drawer__title-row">
            <div class="details-drawer__title-wrap">
              <div v-if="$slots.eyebrow" class="details-drawer__eyebrow">
                <div class="details-drawer__eyebrow-inner"><slot name="eyebrow" /></div>
              </div>
              <component
                :is="titleTag"
                v-if="title !== null"
                ref="titleRef"
                class="details-drawer__subtitle"
                :style="titleStyle"
                :tabindex="titleTag === 'h1' ? -1 : undefined"
              >{{ title }}</component>
              <div v-if="title !== null && (documentType || pageCountLabel || $slots.meta)" class="details-drawer__meta-line">
                <template v-if="documentType">
                  <span class="details-drawer__meta-part details-drawer__meta-part--type" :title="documentType">
                    <v-icon size="13" aria-hidden="true">mdi-file-document-outline</v-icon>
                    <span>{{ documentType }}</span>
                  </span>
                  <span v-if="pageCountLabel || $slots.meta" class="details-drawer__meta-dot" aria-hidden="true" />
                </template>
                <template v-if="pageCountLabel">
                  <span class="details-drawer__meta-part">{{ pageCountLabel }}</span>
                  <span v-if="$slots.meta" class="details-drawer__meta-dot" aria-hidden="true" />
                </template>
                <slot name="meta" />
              </div>
            </div>
          </div>
        </div>

        <div class="details-command-bar__right" @click.stop>
          <slot name="actions" />
          <v-btn
            icon="mdi-chevron-up"
            size="small"
            density="comfortable"
            variant="text"
            class="details-action-btn details-action-btn--quiet details-chevron-btn"
            :class="{ 'details-chevron-btn--expanded': open }"
            :aria-label="open ? 'Dokumentdetails schließen' : 'Dokumentdetails öffnen'"
            :aria-expanded="open"
            :aria-controls="bodyId"
            @click="emit('toggle')"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  open: Boolean,
  bodyId: { type: String, required: true },
  title: { type: String, default: null },
  titleTag: { type: String, default: 'div' },
  documentType: { type: String, default: '' },
  pageCountLabel: { type: String, default: '' },
});
const emit = defineEmits(['toggle']);
const titleRef = ref(null);

const titleStyle = computed(() => {
  const titleLength = Array.from(props.title || '').length;
  let size = '1.18rem';
  if (titleLength > 78) {
    size = '0.98rem';
  } else if (titleLength > 62) {
    size = '1.02rem';
  } else if (titleLength > 46) {
    size = '1.06rem';
  } else if (titleLength > 32) {
    size = '1.12rem';
  }
  return { '--details-header-title-size': size };
});

defineExpose({ focusTitle: () => titleRef.value?.focus({ preventScroll: true }) });
</script>

<style scoped>
h1.details-drawer__subtitle { margin: 0; }
h1.details-drawer__subtitle:focus { outline: none; }
</style>
