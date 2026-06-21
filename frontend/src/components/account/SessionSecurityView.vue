<template>
  <div class="sess">
    <v-select
      :model-value="auth.autoLogoutMinutes"
      :items="autoLogoutOptions"
      item-title="label"
      item-value="value"
      label="Automatische Abmeldung"
      variant="outlined"
      density="comfortable"
      hide-details="auto"
      @update:model-value="onAutoLogoutChange"
    />
  </div>
</template>

<script setup>
import { useAuthStore } from '../../stores/auth.js';

const auth = useAuthStore();

const autoLogoutOptions = [
  { label: 'Nie', value: 0 },
  { label: 'Nach 5 Minuten', value: 5 },
  { label: 'Nach 15 Minuten', value: 15 },
  { label: 'Nach 30 Minuten', value: 30 },
  { label: 'Nach 1 Stunde', value: 60 },
  { label: 'Nach 4 Stunden', value: 240 },
];

function onAutoLogoutChange(value) {
  auth.setAutoLogoutMinutes(Number(value) || 0);
}
</script>

<style scoped>
.sess {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  max-width: 520px;
  margin-inline: auto;
}
</style>
