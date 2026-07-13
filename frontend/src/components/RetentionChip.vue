<template>
  <div
    class="retention-bar"
    :class="[`retention-bar--${state}`, { 'retention-bar--open': open }]"
    role="button"
    tabindex="0"
    aria-label="Aufbewahrung ein- oder ausklappen"
    @click="onClick"
    @keydown.enter.prevent="$emit('toggle')"
    @keydown.space.prevent="$emit('toggle')"
  >
    <span class="retention-bar__badge">
      <v-icon size="15">{{ badge.icon }}</v-icon>
    </span>
    <div class="retention-bar__text">
      <div class="retention-bar__title-row">
        <span class="retention-bar__title">{{ badge.title }}</span>
        <span v-if="state === 'ai'" class="retention-bar__ki">KI-Vorschlag</span>
      </div>
      <div v-if="badge.subtitle" class="retention-bar__subtitle">{{ badge.subtitle }}</div>
    </div>

    <button
      v-if="state === 'ai'"
      type="button"
      class="retention-bar__accept"
      :disabled="saving"
      @click.stop="$emit('accept')"
    >Übernehmen</button>
    <span v-else class="retention-bar__pencil" aria-hidden="true">
      <v-icon size="14">mdi-pencil-outline</v-icon>
    </span>

    <v-icon
      class="retention-bar__chev"
      :class="{ 'retention-bar__chev--open': open }"
      size="16"
    >mdi-chevron-down</v-icon>
  </div>
</template>

<script setup>
defineProps({
  state: { type: String, default: 'empty' },
  badge: { type: Object, default: () => ({ icon: 'mdi-shield-outline', title: '', subtitle: '' }) },
  open: { type: Boolean, default: false },
  saving: { type: Boolean, default: false }
});

const emit = defineEmits(['accept', 'toggle']);

function onClick(event) {
  const interactive = event?.target?.closest?.('button, a, input, textarea, select, [data-retention-action]');
  if (interactive && interactive !== event.currentTarget) {
    return;
  }
  emit('toggle');
}
</script>
