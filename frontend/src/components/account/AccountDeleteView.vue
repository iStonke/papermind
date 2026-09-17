<template>
  <div class="del">
    <div v-if="auth.isAdmin" class="del__note">
      <v-icon size="18">mdi-shield-account-outline</v-icon>
      <span>
        Administratoren können ihr eigenes Konto hier nicht löschen. Bitte eine andere
        Person mit Administratorrechten darum bitten.
      </span>
    </div>

    <template v-else>
      <p class="del__hint">
        Entfernt dein Konto und <strong>alle</strong> eigenen Dokumente, Tags, Notizen und
        Einstellungen dauerhaft. Das lässt sich nicht rückgängig machen.
      </p>
      <div class="del__actions">
        <v-btn
          variant="tonal"
          color="error"
          class="del__btn"
          prepend-icon="mdi-delete-outline"
          @click="openDelete"
        >
          Konto löschen
        </v-btn>
      </div>
    </template>

    <BaseDialog
      v-model="deleteOpen"
      max-width="460"
      variant="destructive"
      title="Konto endgültig löschen?"
      header-subtitle="Dieser Schritt kann nicht rückgängig gemacht werden."
      icon="mdi-delete-outline"
      primary-text="Konto löschen"
      secondary-text="Abbrechen"
      :loading="deleting"
      :primary-disabled="!deletePassword"
      @primary="confirmDelete"
      @update:model-value="onDialogToggle"
    >
      <p class="del__dialog-copy">
        Dein Konto und alle zugehörigen Daten werden unwiderruflich gelöscht. Zur Bestätigung
        dein aktuelles Passwort eingeben.
      </p>
      <v-text-field
        v-model="deletePassword"
        label="Passwort"
        type="password"
        variant="outlined"
        color="primary"
        density="compact"
        rounded="lg"
        autocomplete="current-password"
        :error="!!deleteError"
        :error-messages="deleteError ? [deleteError] : []"
        hide-details="auto"
        @update:model-value="deleteError = ''"
      />
    </BaseDialog>
  </div>
</template>

<script setup>
import { ref } from 'vue';

import BaseDialog from '../BaseDialog.vue';
import { deleteAccount } from '../../api/auth.js';
import { useAuthStore } from '../../stores/auth.js';

const auth = useAuthStore();

const deleteOpen = ref(false);
const deleting = ref(false);
const deletePassword = ref('');
const deleteError = ref('');

function openDelete() {
  deletePassword.value = '';
  deleteError.value = '';
  deleteOpen.value = true;
}

function onDialogToggle(value) {
  deleteOpen.value = value;
  if (!value) {
    deletePassword.value = '';
    deleteError.value = '';
  }
}

async function confirmDelete() {
  if (!deletePassword.value) return;
  deleting.value = true;
  deleteError.value = '';
  try {
    await deleteAccount(deletePassword.value);
    auth.clearSession();
    window.location.assign('/login');
  } catch (err) {
    deleteError.value = err?.message || 'Konto konnte nicht gelöscht werden.';
  } finally {
    deleting.value = false;
  }
}
</script>

<style scoped>
.del {
  max-width: 460px;
  margin-inline: 0;
}
.del__hint {
  margin: 0 0 14px;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.del__actions {
  display: flex;
}
.del__btn {
  text-transform: none;
  letter-spacing: normal;
  font-weight: 600;
  border-radius: 10px;
}
.del__note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.7);
  background: rgba(var(--v-theme-on-surface), 0.045);
  border-radius: 10px;
  padding: 12px 14px;
}
.del__note .v-icon {
  color: rgb(var(--v-theme-primary));
  flex: 0 0 auto;
  margin-top: 1px;
}
.del__dialog-copy {
  margin: 0 0 16px;
  font-size: 0.9rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.78);
}
</style>
