<template>
  <template v-for="(segment, index) in segments" :key="index">
    <code v-if="segment.code">{{ segment.text }}</code>
    <strong v-else-if="segment.bold">{{ segment.text }}</strong>
    <em v-else-if="segment.italic">{{ segment.text }}</em>
    <span v-else>{{ segment.text }}</span>
  </template>
</template>

<script setup>
defineProps({
  segments: { type: Array, default: () => [] },
});
</script>

<style scoped>
code {
  padding: 1px 4px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--pm-ai, #b45309) 10%, transparent);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.88em;
}
</style>
