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
      <template v-if="name === 'link-plus'">
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
    validator: (value) => ['link-plus', 'download', 'file-plus', 'fullscreen', 'fullscreen-exit'].includes(value),
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
