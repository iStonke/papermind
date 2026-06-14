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
    <div class="pm-account-layout">
      <aside class="pm-account-side">
        <AccountSidebar @navigate="onNavigate" />
      </aside>

      <div class="pm-account-pane">
        <!-- Minimale Navigationsleiste nur für Unterseiten -->
        <div v-if="view !== 'profile'" class="pm-account-nav">
          <v-btn
            icon="mdi-arrow-left"
            size="x-small"
            variant="text"
            density="comfortable"
            class="pm-account-nav__back"
            aria-label="Zurück zum Konto"
            @click="goProfile"
          />
          <div class="pm-account-nav__titles">
            <div class="pm-account-nav__title">{{ paneTitle }}</div>
            <div class="pm-account-nav__sub">{{ paneSubtitle }}</div>
          </div>
          <div class="pm-account-nav__actions">
            <v-btn
              v-if="view === 'users'"
              color="primary"
              variant="outlined"
              size="small"
              prepend-icon="mdi-account-plus"
              @click="panelRef?.openCreate()"
            >
              Benutzer anlegen
            </v-btn>
          </div>
        </div>

        <ProfileView v-if="modelValue && view === 'profile'" ref="panelRef" @navigate="onNavigate" />
        <ProfileEditView v-else-if="modelValue && view === 'profile-edit'" ref="panelRef" @done="goProfile" />
        <AvatarEditorView v-else-if="modelValue && view === 'avatar'" ref="panelRef" @done="goProfile" />
        <PasswordChangeView v-else-if="modelValue && view === 'password'" ref="panelRef" @done="goProfile" />
        <SessionSecurityView v-else-if="modelValue && view === 'session'" ref="panelRef" />
        <UsersAdminView v-else-if="modelValue && view === 'users' && auth.isAdmin" ref="panelRef" />
      </div>
    </div>

    <!-- Pro Ansicht eigener Footer -->
    <template #footer>
      <div class="pm-account-footer-row">
        <!-- Profil -->
        <template v-if="view === 'profile'">
          <span></span>
          <v-btn variant="tonal" color="primary" class="pm-dialog__btn" @click="close">Fertig</v-btn>
        </template>

        <!-- Profildaten (Anzeigename & E-Mail) -->
        <template v-else-if="view === 'profile-edit'">
          <v-btn variant="text" class="pm-dialog__btn" @click="goProfile">Abbrechen</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            class="pm-dialog__btn"
            :loading="panelRef?.saving"
            :disabled="!panelRef?.canSubmit"
            @click="panelRef?.submit()"
          >
            Speichern
          </v-btn>
        </template>

        <!-- Profilbild -->
        <template v-else-if="view === 'avatar'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Abbrechen</v-btn>
          <div class="pm-account-footer-right">
            <v-btn
              v-if="panelRef?.hasImage"
              variant="outlined"
              class="pm-dialog__btn"
              @click="panelRef?.pickFile()"
            >
              Neue Datei
            </v-btn>
            <v-btn
              variant="tonal"
              color="primary"
              class="pm-dialog__btn"
              :loading="panelRef?.applying"
              :disabled="!panelRef?.canApply"
              @click="panelRef?.apply()"
            >
              Zuschnitt übernehmen
            </v-btn>
          </div>
        </template>

        <!-- Passwort -->
        <template v-else-if="view === 'password'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Abbrechen</v-btn>
          <v-btn
            variant="tonal"
            color="primary"
            class="pm-dialog__btn"
            :loading="panelRef?.saving"
            :disabled="!panelRef?.canSubmit"
            @click="panelRef?.submit()"
          >
            Passwort aktualisieren
          </v-btn>
        </template>

        <!-- Sitzung & Sicherheit (speichert sofort) -->
        <template v-else-if="view === 'session'">
          <span></span>
          <v-btn variant="tonal" color="primary" class="pm-dialog__btn" @click="close">Fertig</v-btn>
        </template>

        <!-- Benutzerverwaltung -->
        <template v-else-if="view === 'users'">
          <v-btn variant="text" class="pm-dialog__btn" @click="close">Abbrechen</v-btn>
          <span class="pm-account-footer-hint">{{ panelRef?.summary }}</span>
        </template>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

import BaseDialog from './BaseDialog.vue';
import AccountSidebar from './account/AccountSidebar.vue';
import AvatarEditorView from './account/AvatarEditorView.vue';
import PasswordChangeView from './account/PasswordChangeView.vue';
import ProfileEditView from './account/ProfileEditView.vue';
import ProfileView from './account/ProfileView.vue';
import SessionSecurityView from './account/SessionSecurityView.vue';
import UsersAdminView from './account/UsersAdminView.vue';
import { useAuthStore } from '../stores/auth.js';
import { useUiStore } from '../stores/ui.js';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const auth = useAuthStore();
const ui = useUiStore();

const view = ref('profile');
const panelRef = ref(null);

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

const TITLES = {
  profile: { title: 'Konto', sub: '' },
  'profile-edit': { title: 'Anzeigename & E-Mail', sub: 'Profildaten bearbeiten · E-Mail wird sofort geprüft.' },
  avatar: { title: 'Profilbild', sub: 'Hochladen, zuschneiden oder entfernen.' },
  password: { title: 'Passwort ändern', sub: 'Aus Sicherheitsgründen aktuelles Passwort bestätigen.' },
  session: { title: 'Sitzung & Sicherheit', sub: 'Automatische Abmeldung bei Inaktivität · gilt für dieses Gerät.' },
  users: { title: 'Benutzerverwaltung', sub: 'Rollen, Status und Zugänge verwalten.' },
};
const paneTitle = computed(() => TITLES[view.value].title);
const paneSubtitle = computed(() => TITLES[view.value].sub);

function onNavigate(target) {
  if (target === 'users' && !auth.isAdmin) return;
  view.value = target;
}
function goProfile() {
  view.value = 'profile';
}
function close() {
  emit('update:modelValue', false);
}
</script>

<!-- Global (nicht gescopt): v-dialog teleportiert seinen Inhalt aus der
     Komponente heraus, daher würden gescopte Styles den Dialog nicht erreichen. -->
<style>
/* Höhe passt sich dem Inhalt an (keine feste Höhe → keine Leerfläche),
   mit Obergrenze; darüber hinaus wird gescrollt. */
.pm-dialog.pm-account-card .pm-dialog__content-wrap {
  max-height: min(70vh + 25px, 625px);
  overflow-y: auto;
}

/* Stabile Mindesthöhe: ~15px mehr als die natürliche Höhe der Seitenleiste
   (≈ 426px), damit das Fenster etwas mehr Luft bekommt. */
.pm-dialog.pm-account-card .pm-account-layout {
  min-height: 441px;
}

.pm-dialog.pm-account-card .pm-dialog__content {
  padding: 0;
}

.pm-account-layout {
  display: flex;
  align-items: stretch;
  min-height: 100%;
}

.pm-account-side {
  flex: 0 0 248px;
  padding: 28px 24px;
}

/* Durchgehender vertikaler Trennstrich (wie im Einstellungen-Dialog). */
.pm-account-pane {
  flex: 1 1 auto;
  min-width: 0;
  padding: 28px 24px;
  border-left: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

/* Minimale, schlanke Navigationsleiste der Unterseiten – bündig unter dem
   Header, über die volle Breite des Hauptbereichs, mit leichter Färbung. */
.pm-account-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  /* full-bleed: zieht die Leiste an die Ränder des (gepolsterten) Bereichs */
  margin: -28px -24px 22px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}
.pm-account-nav__back {
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.75);
}
.pm-account-nav__titles {
  flex: 1 1 auto;
  min-width: 0;
  text-align: left;
}
.pm-account-nav__actions {
  flex: 0 0 auto;
}
.pm-account-nav__title {
  font-size: 0.95rem;
  font-weight: 650;
  line-height: 1.25;
}
.pm-account-nav__sub {
  margin-top: 3px;
  font-size: 0.78rem;
  line-height: 1.25;
  color: rgba(var(--v-theme-on-surface), 0.6);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 680px) {
  .pm-account-layout {
    flex-direction: column;
  }
  .pm-account-side {
    flex: 0 0 auto;
  }
  .pm-account-pane {
    border-left: none;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  }
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
</style>
