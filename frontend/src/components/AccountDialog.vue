<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="900"
    scrollable
    card-class="pm-account-card"
    body-class="pm-account-body"
    footer-class="pm-account-footer"
    title="Konto"
    header-subtitle="Profil, Sicherheit und Zugänge verwalten."
    description=""
    variant="info"
    primary-text="Fertig"
    :show-secondary="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="pm-settings-layout">
      <nav class="pm-settings-nav" role="tablist" aria-label="Kontoeinstellungen">
        <div
          v-for="group in visibleCategoryGroups"
          :key="`account-group-${group.key}`"
          class="pm-settings-nav__group"
        >
          <div class="pm-settings-nav__group-label">{{ group.label }}</div>
          <button
            v-for="category in group.items"
            :key="`account-category-${category.value}`"
            type="button"
            class="pm-settings-nav__item"
            :class="{ 'pm-settings-nav__item--active': view === category.value }"
            role="tab"
            :aria-selected="view === category.value"
            @click="view = category.value"
          >
            <v-icon size="18" class="pm-settings-nav__icon">{{ category.icon }}</v-icon>
            <span>{{ category.label }}</span>
          </button>
        </div>
      </nav>

      <div class="pm-settings-panel">
        <section v-show="view === 'profile'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              title="Profil"
              subtitle="Anzeigename, E-Mail-Adresse und Kontoinformationen."
            >
              <template #badge>
                <UserAvatar :user="auth.user" current :size="42" />
              </template>
              <template #actions>
                <v-chip
                  size="small"
                  :color="auth.isAdmin ? 'primary' : undefined"
                  variant="tonal"
                >
                  {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
                </v-chip>
              </template>
            </SettingsInfoCard>
            <ProfileEditView
              v-if="modelValue"
              ref="profileRef"
            />
            <div class="pm-account-meta">
              <div class="pm-account-meta__item">
                <span class="pm-account-meta__label">Mitglied seit</span>
                <span class="pm-account-meta__value">
                  {{ formatDateTime(auth.user?.created_at) || '–' }}
                </span>
              </div>
              <div class="pm-account-meta__item">
                <span class="pm-account-meta__label">Letzte Anmeldung</span>
                <span class="pm-account-meta__value">
                  {{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <section v-show="view === 'avatar'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-image-outline"
              title="Profilbild"
              subtitle="Bild hochladen, zuschneiden oder entfernen."
            />
            <AvatarEditorView
              v-if="modelValue"
              ref="avatarRef"
              @done="view = 'profile'"
            />
          </div>
        </section>

        <section v-show="view === 'password'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-lock-outline"
              title="Passwort ändern"
              subtitle="Das aktuelle Passwort bestätigen und ein neues vergeben."
            />
            <PasswordChangeView
              v-if="modelValue"
              ref="passwordRef"
            />
          </div>
        </section>

        <section v-show="view === 'session'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-shield-lock-outline"
              title="Sitzung &amp; Sicherheit"
              subtitle="Automatische Abmeldung bei Inaktivität für dieses Gerät."
            />
            <SessionSecurityView v-if="modelValue" />
          </div>
        </section>

        <section v-if="auth.isAdmin" v-show="view === 'users'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-account-group-outline"
              title="Benutzerverwaltung"
              subtitle="Rollen, Status und Zugänge verwalten."
            >
              <template #actions>
                <v-btn
                  color="primary"
                  variant="outlined"
                  size="small"
                  prepend-icon="mdi-account-plus"
                  @click="usersRef?.openCreate()"
                >
                  Benutzer anlegen
                </v-btn>
              </template>
            </SettingsInfoCard>
            <UsersAdminView
              v-if="modelValue"
              ref="usersRef"
            />
          </div>
        </section>
      </div>
    </div>

    <template #footer>
      <div class="pm-account-footer-row">
        <template v-if="view === 'profile'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Schließen</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            class="pm-dialog__btn"
            :loading="profileRef?.saving"
            :disabled="!profileRef?.canSubmit"
            @click="profileRef?.submit()"
          >
            Speichern
          </v-btn>
        </template>

        <template v-else-if="view === 'avatar'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Abbrechen</v-btn>
          <div class="pm-account-footer-right">
            <v-btn
              v-if="avatarRef?.hasImage"
              variant="outlined"
              class="pm-dialog__btn"
              @click="avatarRef?.pickFile()"
            >
              Neue Datei
            </v-btn>
            <v-btn
              variant="tonal"
              color="primary"
              class="pm-dialog__btn"
              :loading="avatarRef?.applying"
              :disabled="!avatarRef?.canApply"
              @click="avatarRef?.apply()"
            >
              Zuschnitt übernehmen
            </v-btn>
          </div>
        </template>

        <template v-else-if="view === 'password'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Abbrechen</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            class="pm-dialog__btn"
            :loading="passwordRef?.saving"
            :disabled="!passwordRef?.canSubmit"
            @click="passwordRef?.submit()"
          >
            Passwort aktualisieren
          </v-btn>
        </template>

        <template v-else-if="view === 'session'">
          <span></span>
          <v-btn variant="tonal" color="primary" class="pm-dialog__btn" @click="close">Fertig</v-btn>
        </template>

        <template v-else-if="view === 'users' && auth.isAdmin">
          <span class="pm-account-footer-hint">{{ usersRef?.summary }}</span>
          <v-btn variant="tonal" color="primary" class="pm-dialog__btn" @click="close">Fertig</v-btn>
        </template>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import BaseDialog from './BaseDialog.vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import UserAvatar from './UserAvatar.vue';
import AvatarEditorView from './account/AvatarEditorView.vue';
import PasswordChangeView from './account/PasswordChangeView.vue';
import ProfileEditView from './account/ProfileEditView.vue';
import SessionSecurityView from './account/SessionSecurityView.vue';
import UsersAdminView from './account/UsersAdminView.vue';
import { useAuthStore } from '../stores/auth.js';
import { useUiStore } from '../stores/ui.js';
import { formatDateTime } from '../utils/dates.js';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const auth = useAuthStore();
const ui = useUiStore();

const view = ref('profile');
const profileRef = ref(null);
const avatarRef = ref(null);
const passwordRef = ref(null);
const usersRef = ref(null);

const accountCategories = [
  { value: 'profile', label: 'Profil', icon: 'mdi-card-account-details-outline', group: 'account' },
  { value: 'avatar', label: 'Profilbild', icon: 'mdi-image-outline', group: 'account' },
  { value: 'password', label: 'Passwort', icon: 'mdi-lock-outline', group: 'security' },
  { value: 'session', label: 'Sitzung & Sicherheit', icon: 'mdi-shield-lock-outline', group: 'security' },
  { value: 'users', label: 'Benutzerverwaltung', icon: 'mdi-account-group-outline', group: 'administration', adminOnly: true },
];
const accountCategoryGroups = [
  { key: 'account', label: 'Konto' },
  { key: 'security', label: 'Sicherheit' },
  { key: 'administration', label: 'Verwaltung' },
];
const visibleCategories = computed(() =>
  accountCategories.filter((category) => !category.adminOnly || auth.isAdmin)
);
const visibleCategoryGroups = computed(() =>
  accountCategoryGroups
    .map((group) => ({
      ...group,
      items: visibleCategories.value.filter((category) => category.group === group.key),
    }))
    .filter((group) => group.items.length > 0)
);

// Beim Öffnen die Einstiegsansicht aus dem UI-Store übernehmen
// (Konto-Menü: „Konto“ → profile, „Benutzerverwaltung“ → users).
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      view.value = ui.accountTab === 'users' && auth.isAdmin ? 'users' : 'profile';
    }
  },
  { immediate: true }
);
function close() {
  emit('update:modelValue', false);
}
</script>

<!-- Global (nicht gescopt): v-dialog teleportiert seinen Inhalt aus der
     Komponente heraus, daher würden gescopte Styles den Dialog nicht erreichen. -->
<style>
/* Wie bei den globalen Einstellungen bleibt die Dialoghöhe beim Wechsel
   zwischen den Bereichen stabil; nur der Hauptbereich scrollt. */
.pm-dialog.pm-account-card .pm-dialog__content-wrap {
  height: min(62vh, 600px);
  overflow: hidden;
}

.pm-dialog.pm-account-card .pm-dialog__content {
  height: 100%;
  padding: 0;
  overflow: hidden;
  box-sizing: border-box;
}

.pm-account-content > .settings-info-card {
  margin-bottom: 18px;
}

.pm-account-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  max-width: 520px;
  width: 100%;
  margin: 22px auto 0;
}

.pm-account-meta__item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.025);
}

.pm-account-meta__label {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.48);
}

.pm-account-meta__value {
  font-size: 0.86rem;
  font-weight: 500;
}

.pm-account-footer-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.pm-account-footer-right {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.pm-account-footer-hint {
  font-size: 0.85rem;
  font-style: italic;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

@media (max-width: 640px) {
  .pm-account-meta {
    grid-template-columns: 1fr;
  }
}
</style>
