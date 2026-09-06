<template>
  <svg
    class="pm-action-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    focusable="false"
  >
    <g
      stroke="currentColor"
      stroke-width="1.85"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <template v-if="name === 'columns'">
        <rect x="3.5" y="4" width="17" height="16" rx="2" />
        <path d="M12 4v16" />
      </template>

      <template v-else-if="name === 'plus'">
        <path d="M12 5v14M5 12h14" />
      </template>

      <template v-else-if="name === 'layers'">
        <path d="m12 3-9 5 9 5 9-5-9-5Z" />
        <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
      </template>

      <template v-else-if="name === 'sparkles'">
        <path d="m10 3 2.5 6.5L19 12l-6.5 2.5L10 21l-2.5-6.5L1 12l6.5-2.5L10 3Z" />
        <path d="M20 2v6M17 5h6" />
      </template>

      <template v-else-if="name === 'callout-info'">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="M12 10.5v6M12 7.5h.01" />
      </template>

      <template v-else-if="name === 'callout-important'">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="M12 7.5v6M12 16.5h.01" />
      </template>

      <template v-else-if="name === 'callout-question'">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="M9.75 9a2.35 2.35 0 1 1 3.25 2.17c-.67.29-1 .75-1 1.33v.5M12 16.5h.01" />
      </template>

      <template v-else-if="name === 'callout-decision'">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="m8 12.25 2.5 2.5L16.5 9" />
      </template>

      <template v-else-if="name === 'callout-prompt'">
        <rect x="3" y="3" width="18" height="18" rx="4" />
        <path d="m11.25 7.25 1.15 3.1 3.1 1.15-3.1 1.15-1.15 3.1-1.15-3.1L7 11.5l3.1-1.15 1.15-3.1Z" />
      </template>

      <template v-else-if="name === 'link-plus'">
        <path d="M8.75 16.25H7a4.25 4.25 0 0 1 0-8.5h1.75" />
        <path d="M15.25 7.75H17a4.25 4.25 0 0 1 0 8.5h-1.75" />
        <path d="M8.5 12h7" />
        <path d="M19 3v5" />
        <path d="M16.5 5.5h5" />
      </template>

      <template v-else-if="name === 'download'">
        <path d="M12 3.5v11" />
        <path d="m7.75 10.5 4.25 4 4.25-4" />
        <path d="M4 19.5h16" />
      </template>

      <template v-else-if="name === 'file-plus'">
        <path d="M14 3.5H6a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-11z" />
        <path d="M14 3.5v4h4" />
        <path d="M12 11v6" />
        <path d="M9 14h6" />
      </template>

      <template v-else-if="name === 'fullscreen'">
        <path d="M9 3.5H3.5V9" />
        <path d="M15 3.5h5.5V9" />
        <path d="M20.5 15v5.5H15" />
        <path d="M9 20.5H3.5V15" />
      </template>

      <template v-else-if="name === 'fullscreen-exit'">
        <path d="M3.5 9H9V3.5" />
        <path d="M15 3.5V9h5.5" />
        <path d="M20.5 15H15v5.5" />
        <path d="M9 20.5V15H3.5" />
      </template>
    </g>
  </svg>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true,
    validator: (value) => [
      'columns', 'plus', 'layers', 'sparkles',
      'callout-info', 'callout-important', 'callout-question', 'callout-decision', 'callout-prompt',
      'link-plus', 'download', 'file-plus', 'fullscreen', 'fullscreen-exit',
    ].includes(value),
  },
  size: { type: [Number, String], default: 20 },
});
</script>

<style scoped>
.pm-action-icon {
  display: block;
  flex: none;
  overflow: visible;
}
</style>
