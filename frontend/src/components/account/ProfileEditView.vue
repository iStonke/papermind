<template>
  <div class="pe">
    <v-text-field
      v-model="username"
      label="Benutzername"
      variant="outlined"
      color="primary"
      density="compact"
      rounded="lg"
      autocomplete="username"
      :error="!!username && !usernameValid"
      :error-messages="!!username && !usernameValid ? 'Benutzername darf nicht leer sein.' : []"
      hide-details="auto"
    />

    <v-text-field
      v-model="displayName"
      label="Anzeigename"
      variant="outlined"
      color="primary"
      density="compact"
      rounded="lg"
      hide-details="auto"
    />

    <v-text-field
      v-model="email"
      label="E-Mail-Adresse"
      type="email"
      variant="outlined"
      color="primary"
      density="compact"
      rounded="lg"
      autocomplete="email"
      :error="!!email && !emailValid"
      :error-messages="!!email && !emailValid ? 'Bitte eine gültige E-Mail-Adresse eingeben.' : []"
      hide-details="auto"
    />
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

const username = ref('');
const displayName = ref('');
const email = ref('');
const saving = ref(false);

function syncFromUser() {
  username.value = auth.user?.username || '';
  displayName.value = auth.user?.display_name || '';
  email.value = auth.user?.email || '';
}
watch(() => auth.user, syncFromUser, { immediate: true });

const usernameValid = computed(() => username.value.trim().length > 0);
const emailValid = computed(() => !email.value || EMAIL_RE.test(email.value.trim()));

const dirty = computed(
  () =>
    username.value.trim() !== (auth.user?.username || '') ||
    displayName.value !== (auth.user?.display_name || '') ||
    email.value !== (auth.user?.email || '')
);

const canSubmit = computed(() => dirty.value && usernameValid.value && emailValid.value);

async function submit() {
  if (!canSubmit.value) return;
  saving.value = true;
  try {
    const updated = await updateProfile({
      username: username.value.trim(),
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
  gap: 16px;
  max-width: 460px;
  margin-inline: 0;
}
</style>
