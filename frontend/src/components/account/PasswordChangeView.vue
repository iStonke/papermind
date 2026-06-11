<template>
  <div class="pw">
    <v-text-field
      v-model="currentPassword"
      label="Aktuelles Passwort"
      type="password"
      variant="outlined"
      density="comfortable"
      autocomplete="current-password"
      hide-details="auto"
    />

    <div class="pw__field">
      <v-text-field
        v-model="newPassword"
        label="Neues Passwort"
        type="password"
        variant="outlined"
        density="comfortable"
        autocomplete="new-password"
        :hint="`mind. ${MIN_LENGTH} Zeichen`"
        persistent-hint
      />
      <div v-if="newPassword" class="pw__strength">
        <div class="pw__strength-track">
          <div
            class="pw__strength-bar"
            :style="{ width: `${(strength.score / 4) * 100}%`, background: strength.color }"
          />
        </div>
        <div class="pw__strength-label">
          Stärke: <strong :style="{ color: strength.color }">{{ strength.label }}</strong>
        </div>
      </div>
    </div>

    <v-text-field
      v-model="repeatPassword"
      label="Neues Passwort wiederholen"
      type="password"
      variant="outlined"
      density="comfortable"
      autocomplete="new-password"
      :error="!!repeatPassword && !passwordsMatch"
      :error-messages="!!repeatPassword && !passwordsMatch ? 'Passwörter stimmen nicht überein.' : []"
      hide-details="auto"
    />

    <p class="pw__hint">
      Nach dem Ändern bleibst du in dieser Sitzung angemeldet. Andere Geräte werden abgemeldet.
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

import { changePassword } from '../../api/auth.js';
import { notifyError, useNotifications } from '../../stores/notifications';

const MIN_LENGTH = 8;

const emit = defineEmits(['done']);

const { notify } = useNotifications();

const currentPassword = ref('');
const newPassword = ref('');
const repeatPassword = ref('');
const savingPassword = ref(false);

const passwordsMatch = computed(() => newPassword.value === repeatPassword.value);

const strength = computed(() => {
  const pw = newPassword.value;
  let score = 0;
  if (pw.length >= MIN_LENGTH) score += 1;
  if (pw.length >= 12) score += 1;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 1;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score += 1;
  if (score <= 1) return { score: Math.max(score, 1), label: 'schwach', color: '#d9534f' };
  if (score === 2) return { score, label: 'mittel', color: '#e0a800' };
  if (score === 3) return { score, label: 'gut', color: '#3a9d4e' };
  return { score: 4, label: 'stark', color: '#2e7d32' };
});

const canSubmit = computed(
  () =>
    !!currentPassword.value &&
    newPassword.value.length >= MIN_LENGTH &&
    passwordsMatch.value
);

async function submit() {
  if (!canSubmit.value) return;
  savingPassword.value = true;
  try {
    await changePassword(currentPassword.value, newPassword.value);
    currentPassword.value = '';
    newPassword.value = '';
    repeatPassword.value = '';
    notify({ type: 'success', message: 'Passwort geändert.', critical: true });
    emit('done');
  } catch (err) {
    notifyError(err, 'Passwortänderung fehlgeschlagen.');
  } finally {
    savingPassword.value = false;
  }
}

defineExpose({ canSubmit, saving: savingPassword, submit });
</script>

<style scoped>
.pw {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 520px;
  margin-inline: auto;
}
.pw__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pw__strength-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.12);
  overflow: hidden;
}
.pw__strength-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.2s ease, background 0.2s ease;
}
.pw__strength-label {
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-top: 6px;
}
.pw__hint {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
