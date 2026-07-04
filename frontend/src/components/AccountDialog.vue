<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="900"
    scrollable
    card-class="pm-account-card"
    body-class="pm-account-body"
    title="Konto"
    header-subtitle="Profil, Sicherheit und Zugänge verwalten."
    description=""
    variant="info"
    :show-footer="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="pm-settings-layout">
      <nav class="pm-settings-nav" role="tablist" aria-label="Kontoeinstellungen">
        <div class="pm-settings-nav__group">
          <button
            v-for="category in visibleCategories"
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
            <div class="pm-account-id">
              <button
                type="button"
                class="pm-account-avatar"
                aria-label="Profilbild ändern"
                @click="avatarOpen = true"
              >
                <UserAvatar :user="auth.user" current :size="96" />
                <span class="pm-account-avatar__badge">
                  <v-icon size="16">mdi-camera-outline</v-icon>
                </span>
              </button>
              <div class="pm-account-id__name">
                {{ auth.user?.display_name || auth.username }}
              </div>
              <div v-if="auth.user?.email" class="pm-account-id__email">
                {{ auth.user.email }}
              </div>
              <v-chip
                size="small"
                :color="auth.isAdmin ? 'primary' : undefined"
                variant="tonal"
                class="pm-account-id__role"
              >
                {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
              </v-chip>
            </div>

            <ProfileEditView
              v-if="modelValue"
              ref="profileRef"
            />
            <div class="pm-account-profile-actions">
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
            </div>

            <dl class="pm-account-facts">
              <div class="pm-account-facts__item">
                <dt class="pm-account-facts__label">Mitglied seit</dt>
                <dd class="pm-account-facts__value">
                  {{ formatDateTime(auth.user?.created_at) || '–' }}
                </dd>
              </div>
              <div class="pm-account-facts__item">
                <dt class="pm-account-facts__label">Letzte Anmeldung</dt>
                <dd class="pm-account-facts__value">
                  {{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}
                </dd>
              </div>
            </dl>
          </div>
        </section>

        <section v-show="view === 'security'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-lock-outline"
              title="Passwort ändern"
              subtitle="Das aktuelle Passwort bestätigen und ein neues vergeben."
            />
            <PasswordChangeView v-if="modelValue" />
            <v-divider class="pm-account-divider" />
            <SessionSecurityView v-if="modelValue" />
          </div>
        </section>

        <section v-if="auth.isAdmin" v-show="view === 'users'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <SettingsInfoCard
              icon="mdi-account-group-outline"
              title="Benutzer"
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
  </BaseDialog>

  <!-- Profilbild-Editor als eigenes Fenster (kein eingeklapptes Inline-Panel). -->
  <BaseDialog
    :model-value="avatarOpen"
    max-width="640"
    scrollable
    title="Profilbild"
    header-subtitle="Bild hochladen, zuschneiden oder entfernen."
    variant="info"
    :show-secondary="false"
    @update:model-value="avatarOpen = $event"
  >
    <AvatarEditorView
      v-if="avatarOpen"
      @done="avatarOpen = false"
    />
    <template #footer>
      <div class="pm-account-footer-row">
        <span></span>
        <v-btn variant="tonal" color="primary" class="pm-dialog__btn" @click="avatarOpen = false">
          Fertig
        </v-btn>
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
const avatarOpen = ref(false);
const profileRef = ref(null);
const usersRef = ref(null);

const accountCategories = [
  { value: 'profile', label: 'Profil', icon: 'mdi-card-account-details-outline' },
  { value: 'security', label: 'Sicherheit', icon: 'mdi-shield-lock-outline' },
  { value: 'users', label: 'Benutzer', icon: 'mdi-account-group-outline', adminOnly: true },
];
const visibleCategories = computed(() =>
  accountCategories.filter((category) => !category.adminOnly || auth.isAdmin)
);

// Beim Öffnen die Einstiegsansicht aus dem UI-Store übernehmen
// (Konto-Menü: „Konto“ → profile, „Benutzerverwaltung“ → users).
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      view.value = ui.accountTab === 'users' && auth.isAdmin ? 'users' : 'profile';
      avatarOpen.value = false;
    }
  },
  { immediate: true }
);
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

/* Oberen Panel-Abstand an die Navigation (20px) angleichen, damit der Inhalt
   – insb. das Profilbild – auf gleicher Höhe wie die Nav-Einträge beginnt. */
.pm-dialog.pm-account-card .pm-settings-panel {
  padding-top: 20px;
}

.pm-account-content > .settings-info-card {
  margin-bottom: 18px;
}

/* Trennlinie zwischen Passwort- und Abmelde-Abschnitt auf der Sicherheits-Seite. */
.pm-account-divider {
  margin: 28px auto;
  width: 100%;
  max-width: 520px;
}

/* Profil: zentrierter Identitäts-Stack (Avatar + Name + E-Mail + Rolle). */
.pm-account-id {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin-bottom: 24px;
}
.pm-account-id__name {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  margin-top: 6px;
}
.pm-account-id__email {
  font-size: 0.88rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}
.pm-account-id__role {
  margin-top: 4px;
}

.pm-account-profile-actions {
  display: flex;
  justify-content: flex-end;
  width: 100%;
  max-width: 420px;
  margin: 12px auto 0;
}

/* Avatar als Editier-Trigger mit Kamera-Badge. */
.pm-account-avatar {
  position: relative;
  display: inline-flex;
  border: none;
  background: transparent;
  padding: 0;
  border-radius: 50%;
  cursor: pointer;
}
.pm-account-avatar::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid transparent;
  transition: border-color 0.15s ease;
}
.pm-account-avatar:hover::after,
.pm-account-avatar:focus-visible::after {
  border-color: rgba(var(--v-theme-primary), 0.55);
}
.pm-account-avatar__badge {
  position: absolute;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  border: 3px solid rgb(var(--v-theme-surface));
}

/* Ruhige, randlose Konto-Fakten als zwei Zeilen mit feiner Trennlinie. */
.pm-account-facts {
  max-width: 420px;
  width: 100%;
  margin: 24px auto 0;
  padding-top: 16px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pm-account-facts__item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}
.pm-account-facts__label {
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.pm-account-facts__value {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.85);
  text-align: right;
}

.pm-account-footer-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

</style>
