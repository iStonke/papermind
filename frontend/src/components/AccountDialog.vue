<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="760"
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
            <div class="pm-account-head">
              <button
                type="button"
                class="pm-account-avatar"
                aria-label="Profilbild ändern"
                @click="avatarOpen = true"
              >
                <UserAvatar :user="auth.user" current :size="72" />
                <span class="pm-account-avatar__badge">
                  <v-icon size="15">mdi-camera-outline</v-icon>
                </span>
              </button>
              <div class="pm-account-head__main">
                <div class="pm-account-head__title">
                  <span class="pm-account-head__name">
                    {{ auth.user?.display_name || auth.username }}
                  </span>
                  <span class="pm-account-head__role">
                    <v-icon size="13">
                      {{ auth.isAdmin ? 'mdi-shield-account-outline' : 'mdi-account-outline' }}
                    </v-icon>
                    {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
                  </span>
                </div>
                <div v-if="auth.user?.email" class="pm-account-head__email">
                  {{ auth.user.email }}
                </div>
                <div class="pm-account-head__meta">
                  Mitglied seit {{ formatDateTime(auth.user?.created_at) || '–' }}
                  · zuletzt aktiv {{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}
                </div>
              </div>
            </div>

            <v-divider class="pm-account-head-sep" />

            <ProfileEditView
              v-if="modelValue"
              ref="profileRef"
            />

            <div class="pm-account-actionbar">
              <span class="pm-account-actionbar__hint">
                Änderungen gelten sofort nach dem Speichern.
              </span>
              <v-btn
                color="primary"
                variant="flat"
                class="pm-account-actionbar__btn"
                :loading="profileRef?.saving"
                :disabled="!profileRef?.canSubmit"
                @click="profileRef?.submit()"
              >
                Speichern
              </v-btn>
            </div>

            <v-divider class="pm-account-divider" />
            <div class="pm-account-subhead">Konto löschen</div>
            <AccountDeleteView v-if="modelValue" />
          </div>
        </section>

        <section v-show="view === 'password'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <div class="pm-account-sectionhead">
              <div class="pm-account-sectionhead__text">
                <div class="pm-account-sectionhead__title">Passwort ändern</div>
                <div class="pm-account-sectionhead__sub">
                  Aktuelles Passwort bestätigen und ein neues vergeben.
                </div>
              </div>
            </div>
            <v-divider class="pm-account-head-sep" />

            <PasswordChangeView v-if="modelValue" />
          </div>
        </section>

        <section v-show="view === 'session'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <div class="pm-account-sectionhead">
              <div class="pm-account-sectionhead__text">
                <div class="pm-account-sectionhead__title">Sitzungen &amp; Geräte</div>
                <div class="pm-account-sectionhead__sub">
                  Aktive Sitzungen und automatische Abmeldung verwalten.
                </div>
              </div>
            </div>
            <v-divider class="pm-account-head-sep" />

            <div class="pm-account-subhead">Aktive Sitzungen</div>
            <ActiveSessionsView v-if="modelValue" />

            <v-divider class="pm-account-divider" />
            <div class="pm-account-subhead">Automatische Abmeldung</div>
            <SessionSecurityView v-if="modelValue" />
          </div>
        </section>

        <section v-show="view === 'data'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <div class="pm-account-sectionhead">
              <div class="pm-account-sectionhead__text">
                <div class="pm-account-sectionhead__title">Datenschutz &amp; Daten</div>
                <div class="pm-account-sectionhead__sub">
                  Speicherplatz und persönlicher Datenexport.
                </div>
              </div>
            </div>
            <v-divider class="pm-account-head-sep" />
            <AccountDataView v-if="modelValue" />
          </div>
        </section>

        <section v-if="auth.isAdmin" v-show="view === 'users'" class="pm-settings-section">
          <div class="pm-settings-content pm-account-content">
            <div class="pm-account-sectionhead">
              <div class="pm-account-sectionhead__text">
                <div class="pm-account-sectionhead__title">Benutzer</div>
                <div class="pm-account-sectionhead__sub">
                  Rollen, Status und Zugänge verwalten.
                </div>
              </div>
              <div class="pm-account-sectionhead__actions">
                <v-btn
                  color="primary"
                  variant="flat"
                  size="small"
                  prepend-icon="mdi-account-plus"
                  class="pm-account-actionbar__btn"
                  @click="usersRef?.openCreate()"
                >
                  Benutzer anlegen
                </v-btn>
              </div>
            </div>
            <v-divider class="pm-account-head-sep" />
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
import UserAvatar from './UserAvatar.vue';
import AccountDataView from './account/AccountDataView.vue';
import AccountDeleteView from './account/AccountDeleteView.vue';
import ActiveSessionsView from './account/ActiveSessionsView.vue';
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
  { value: 'password', label: 'Passwort', icon: 'mdi-lock-outline' },
  { value: 'session', label: 'Sitzung', icon: 'mdi-shield-lock-outline' },
  { value: 'data', label: 'Daten', icon: 'mdi-database-outline' },
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
  height: min(60vh, 540px);
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

/* Flacher Section-Kopf (Sicherheit/Benutzer) – gleiche Sprache wie der Profil-Kopf. */
.pm-account-sectionhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}
.pm-account-sectionhead__text {
  min-width: 0;
}
.pm-account-sectionhead__title {
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.pm-account-sectionhead__sub {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-top: 4px;
  line-height: 1.4;
}
.pm-account-sectionhead__actions {
  flex: 0 0 auto;
}

/* Zwischenüberschrift (z. B. „Sitzung & Sicherheit"). */
.pm-account-subhead {
  font-size: 0.92rem;
  font-weight: 600;
  margin: 0 0 14px;
}

/* Trennlinie zwischen Passwort- und Sitzungs-Abschnitt. */
.pm-account-divider {
  margin: 24px 0;
  width: 100%;
  max-width: 460px;
  border-color: rgba(var(--v-theme-on-surface), 0.1) !important;
}

/* Identität als horizontaler Kopf (Avatar links, Name/Rolle/E-Mail/Meta rechts). */
.pm-account-head {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 520px;
}
.pm-account-head__main {
  min-width: 0;
}
.pm-account-head__title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.pm-account-head__name {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.pm-account-head__role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.5;
  border-radius: 999px;
  color: rgb(var(--v-theme-on-surface));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
}
.pm-account-head__role .v-icon {
  color: rgb(var(--v-theme-primary));
}
.pm-account-head__email {
  font-size: 0.9rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pm-account-head__meta {
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-top: 6px;
}
.pm-account-head-sep {
  width: 100%;
  margin: 18px 0;
  border-color: rgba(var(--v-theme-on-surface), 0.1) !important;
}

/* Feste Aktionsleiste: Hinweis links, klarer Speichern-Button rechts. */
.pm-account-actionbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}
.pm-account-actionbar__hint {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.pm-account-actionbar__btn {
  text-transform: none;
  letter-spacing: normal;
  font-weight: 600;
  border-radius: 10px;
}

/* Avatar als Editier-Trigger mit Kamera-Badge. */
.pm-account-avatar {
  position: relative;
  display: inline-flex;
  flex: none;
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
  right: -2px;
  bottom: -2px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  border: 3px solid rgb(var(--v-theme-surface));
}

.pm-account-footer-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

</style>
