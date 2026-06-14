<template>
  <div class="sess">
    <div class="sess__field">
      <div class="sess__label">Automatische Abmeldung</div>
      <div class="sess__description">
        Meldet dich nach einer Zeit ohne Aktivität automatisch ab. Gilt nur für dieses Gerät bzw.
        diesen Browser – andere angemeldete Geräte bleiben unberührt.
      </div>
      <v-select
        :model-value="auth.autoLogoutMinutes"
        :items="autoLogoutOptions"
        item-title="label"
        item-value="value"
        density="comfortable"
        variant="outlined"
        hide-details
        label="Abmelden"
        class="sess__select"
        @update:model-value="onAutoLogoutChange"
      />
    </div>
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
  max-width: 520px;
  margin-inline: auto;
}
.sess__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sess__label {
  font-size: 0.96rem;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}
.sess__description {
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.sess__select {
  margin-top: 4px;
}
</style>
