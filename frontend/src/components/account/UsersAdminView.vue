<template>
  <div class="users">
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
      closable
      @click:close="error = ''"
    >
      {{ error }}
    </v-alert>

    <div class="users__list">
      <v-progress-linear v-if="loading" indeterminate class="users__loading" />

      <div
        v-for="u in users"
        :key="u.id"
        class="users__row"
        :class="{ 'users__row--inactive': !u.is_active }"
      >
        <UserAvatar :user="u" :size="38" class="users__avatar" />
        <div class="users__ident">
          <div class="users__name-main">
            {{ u.display_name || u.username }}
            <span v-if="u.id === auth.user?.id" class="users__you">(du)</span>
          </div>
          <div class="users__name-sub">{{ u.email || u.username }}</div>
          <div class="users__name-meta">
            {{ u.last_login_at ? `zuletzt aktiv ${formatDateTime(u.last_login_at)}` : 'noch nie angemeldet' }}
          </div>
        </div>

        <span class="users__role" :class="{ 'users__role--admin': u.is_admin }">
          <v-icon size="12">{{ u.is_admin ? 'mdi-shield-account-outline' : 'mdi-account-outline' }}</v-icon>
          {{ u.is_admin ? 'Administrator' : 'Benutzer' }}
        </span>

        <span class="users__status">
          <span
            class="users__dot"
            :style="{ background: u.is_active ? 'rgb(var(--v-theme-success))' : 'rgba(var(--v-theme-on-surface), 0.35)' }"
          />
          <span class="users__status-label">{{ u.is_active ? 'Aktiv' : 'Deaktiviert' }}</span>
        </span>

        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-btn
              icon="mdi-dots-vertical"
              variant="text"
              size="small"
              class="users__menu-btn"
              aria-label="Aktionen"
              v-bind="props"
            />
          </template>
          <v-list density="compact">
            <v-list-item
              :title="u.is_admin ? 'Adminrechte entziehen' : 'Zum Admin machen'"
              @click="patch(u, { is_admin: !u.is_admin })"
            />
            <v-list-item
              :title="u.is_active ? 'Deaktivieren' : 'Aktivieren'"
              @click="patch(u, { is_active: !u.is_active })"
            />
            <v-list-item title="Passwort zurücksetzen…" @click="openReset(u)" />
            <template v-if="u.id !== auth.user?.id">
              <v-divider />
              <v-list-item title="Löschen" class="text-error" @click="openDelete(u)" />
            </template>
          </v-list>
        </v-menu>
      </div>

      <div v-if="!loading && users.length === 0" class="users__empty">Noch keine Benutzer.</div>
    </div>

    <BaseDialog
      v-model="createOpen"
      max-width="520"
      title="Benutzer anlegen"
      header-subtitle="Zugangsdaten und Rolle für das neue Konto festlegen."
      primary-text="Anlegen"
      secondary-text="Zurück"
      icon="mdi-account-plus"
      :loading="creating"
      :primary-disabled="!newUser.username || newUser.password.length < 8"
      @primary="onCreate"
    >
      <div class="users-dialog-fields">
        <v-text-field v-model="newUser.username" label="Benutzername" variant="outlined" density="comfortable" hide-details="auto" />
        <v-text-field v-model="newUser.display_name" label="Anzeigename (optional)" variant="outlined" density="comfortable" hide-details="auto" />
        <v-text-field v-model="newUser.email" label="E-Mail (optional)" type="email" variant="outlined" density="comfortable" hide-details="auto" />
        <v-text-field v-model="newUser.password" label="Passwort (min. 8)" type="password" variant="outlined" density="comfortable" hide-details="auto" />
        <v-checkbox v-model="newUser.is_admin" label="Administrator" density="compact" hide-details />
      </div>
    </BaseDialog>

    <BaseDialog
      v-model="resetOpen"
      max-width="460"
      title="Passwort zurücksetzen"
      :header-subtitle="resetTarget?.username || ''"
      primary-text="Zurücksetzen"
      secondary-text="Zurück"
      icon="mdi-lock-reset"
      :loading="resetting"
      :primary-disabled="resetPassword.length < 8"
      @primary="confirmReset"
    >
      <v-text-field
        v-model="resetPassword"
        label="Neues Passwort"
        type="password"
        variant="outlined"
        density="comfortable"
        autofocus
        hide-details="auto"
      />
    </BaseDialog>

    <DestructiveDialog
      v-model="deleteOpen"
      max-width="460"
      title="Benutzer löschen?"
      header-subtitle="Das Konto wird endgültig entfernt."
      primary-text="Benutzer löschen"
      secondary-text="Zurück"
      :loading="deleting"
      @primary="confirmDelete"
    >
      <p class="users-dialog-copy">
        Benutzer <strong>{{ deleteTarget?.username }}</strong> wird gelöscht. Das lässt sich nicht rückgängig machen.
      </p>
    </DestructiveDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import BaseDialog from '../BaseDialog.vue';
import DestructiveDialog from '../DestructiveDialog.vue';
import UserAvatar from '../UserAvatar.vue';
import { createUser, deleteUser, listUsers, updateUser } from '../../api/users.js';
import { useAuthStore } from '../../stores/auth.js';
import { formatDateTime } from '../../utils/dates';

const auth = useAuthStore();

const users = ref([]);
const loading = ref(false);
const error = ref('');

const createOpen = ref(false);
const creating = ref(false);
const newUser = reactive({ username: '', display_name: '', email: '', password: '', is_admin: false });

const resetOpen = ref(false);
const resetTarget = ref(null);
const resetPassword = ref('');
const resetting = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref(null);
const deleting = ref(false);

async function refresh() {
  loading.value = true;
  error.value = '';
  try {
    const res = await listUsers();
    users.value = res.items || [];
  } catch (err) {
    error.value = err?.message || 'Konnte Benutzer nicht laden.';
  } finally {
    loading.value = false;
  }
}
onMounted(refresh);

// Zusammenfassung für den Dialog-Footer („N aktiv · M deaktiviert“).
const summary = computed(() => {
  const total = users.value.length;
  const active = users.value.filter((u) => u.is_active).length;
  const inactive = total - active;
  const parts = [`${active} aktiv`];
  if (inactive > 0) parts.push(`${inactive} deaktiviert`);
  return parts.join(' · ');
});

function openCreate() {
  createOpen.value = true;
}
defineExpose({ summary, openCreate });

async function onCreate() {
  if (!newUser.username || newUser.password.length < 8) return;
  creating.value = true;
  error.value = '';
  try {
    await createUser({ ...newUser });
    Object.assign(newUser, { username: '', display_name: '', email: '', password: '', is_admin: false });
    createOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = err?.message || 'Anlegen fehlgeschlagen.';
  } finally {
    creating.value = false;
  }
}

async function patch(user, payload) {
  error.value = '';
  try {
    await updateUser(user.id, payload);
    await refresh();
  } catch (err) {
    error.value = err?.message || 'Änderung fehlgeschlagen.';
  }
}

function openReset(user) {
  resetTarget.value = user;
  resetPassword.value = '';
  resetOpen.value = true;
}
async function confirmReset() {
  if (resetPassword.value.length < 8) return;
  resetting.value = true;
  try {
    await updateUser(resetTarget.value.id, { password: resetPassword.value });
    resetOpen.value = false;
  } catch (err) {
    error.value = err?.message || 'Passwort-Reset fehlgeschlagen.';
  } finally {
    resetting.value = false;
  }
}

function openDelete(user) {
  // Sich selbst zu löschen ist nicht erlaubt (zusätzlich serverseitig geschützt).
  if (user.id === auth.user?.id) return;
  deleteTarget.value = user;
  deleteOpen.value = true;
}
async function confirmDelete() {
  deleting.value = true;
  try {
    await deleteUser(deleteTarget.value.id);
    deleteOpen.value = false;
    await refresh();
  } catch (err) {
    error.value = err?.message || 'Löschen fehlgeschlagen.';
    deleteOpen.value = false;
  } finally {
    deleting.value = false;
  }
}
</script>

<style scoped>
.users {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* Responsive Zeilen-Liste statt starrer Tabelle (kein Horizontal-Scroll). */
.users__list {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 14px;
  overflow: hidden;
}
.users__loading {
  margin-bottom: -4px;
}
.users__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
}
.users__row + .users__row {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.users__row--inactive {
  opacity: 0.55;
}
.users__avatar {
  flex: 0 0 auto;
}
.users__ident {
  flex: 1 1 auto;
  min-width: 0;
}
.users__name-main {
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.users__you {
  font-weight: 400;
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
.users__name-sub {
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.users__name-meta {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.45);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Rollen-Pille im gleichen Stil wie Kopf/Menü (Türkis nur als Glyphe). */
.users__role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  padding: 2px 9px;
  font-size: 0.7rem;
  font-weight: 600;
  border-radius: 999px;
  color: rgba(var(--v-theme-on-surface), 0.75);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
}
.users__role .v-icon {
  color: rgba(var(--v-theme-on-surface), 0.5);
}
.users__role--admin {
  color: rgb(var(--v-theme-on-surface));
}
.users__role--admin .v-icon {
  color: rgb(var(--v-theme-primary));
}

.users__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: 0 0 auto;
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.users__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}
.users__menu-btn {
  flex: 0 0 auto;
}
.users__empty {
  text-align: center;
  padding: 28px 0;
  opacity: 0.6;
}

/* Auf schmalen Breiten Status-Text ausblenden (Punkt bleibt), damit nichts abschneidet. */
@media (max-width: 560px) {
  .users__status-label {
    display: none;
  }
}
.users-dialog-fields {
  display: grid;
  gap: 12px;
}
.users-dialog-copy {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.74);
  font-size: 0.98rem;
  line-height: 1.48;
}
</style>
