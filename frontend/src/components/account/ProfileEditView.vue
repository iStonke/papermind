<template>
  <div class="pe">
    <v-text-field
      v-model="displayName"
      label="Anzeigename"
      variant="outlined"
      density="comfortable"
      hide-details="auto"
    />

    <v-text-field
      v-model="email"
      label="E-Mail-Adresse"
      type="email"
      variant="outlined"
      density="comfortable"
      autocomplete="email"
      :error="!!email && !emailValid"
      :error-messages="!!email && !emailValid ? 'Bitte eine gültige E-Mail-Adresse eingeben.' : []"
      hide-details="auto"
    />

    <p class="pe__hint">
      Änderungen an Anzeigename und E-Mail-Adresse gelten sofort nach dem Speichern.
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import { updateProfile } from '../../api/auth.js';
import { useAuthStore } from '../../stores/auth.js';
import { notifyError, useNotifications } from '../../stores/notifications';

// Einfache, aber robuste Format-Prüfung (umgehend, während der Eingabe).
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emit = defineEmits(['done']);

const auth = useAuthStore();
const { notify } = useNotifications();

const displayName = ref('');
const email = ref('');
const saving = ref(false);

function syncFromUser() {
  displayName.value = auth.user?.display_name || '';
  email.value = auth.user?.email || '';
}
watch(() => auth.user, syncFromUser, { immediate: true });

const emailValid = computed(() => !email.value || EMAIL_RE.test(email.value.trim()));

const dirty = computed(
  () =>
    displayName.value !== (auth.user?.display_name || '') ||
    email.value !== (auth.user?.email || '')
);

const canSubmit = computed(() => dirty.value && emailValid.value);

async function submit() {
  if (!canSubmit.value) return;
  saving.value = true;
  try {
    const updated = await updateProfile({
      display_name: displayName.value.trim(),
      email: email.value.trim(),
    });
    auth.setUser(updated);
    notify({ type: 'success', message: 'Profil gespeichert.' });
    emit('done');
  } catch (err) {
    notifyError(err, 'Profil konnte nicht gespeichert werden.');
  } finally {
    saving.value = false;
  }
}

defineExpose({ canSubmit, saving, submit });
</script>

<style scoped>
.pe {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 420px;
  margin-inline: auto;
}
.pe__hint {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
