<template>
  <v-btn
    class="onboarding-dev-launcher"
    size="small"
    variant="elevated"
    prepend-icon="mdi-creation"
    @click="emit('launch')"
  >
    DEV · Onboarding
  </v-btn>
</template>

<script setup>
const emit = defineEmits(['launch']);
</script>

<style scoped>
.onboarding-dev-launcher {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 20;
  border: 1px solid rgba(var(--v-theme-primary), 0.34);
  background: rgb(var(--v-theme-surface-2)) !important;
  color: rgb(var(--v-theme-primary));
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18) !important;
  letter-spacing: 0.02em;
}
@media (max-width: 720px) {
  .onboarding-dev-launcher { right: 12px; bottom: 12px; }
}
</style>
