<template>
  <v-app-bar class="app-topbar" flat height="64">
    <div class="appbar-layout">
      <div class="appbar-left app-title">
        <button type="button" class="app-title__brand app-title__brand-button" @click="goHome">
          PaperMind
        </button>
      </div>

      <div class="appbar-center">
        <slot name="center" />
      </div>

      <div class="appbar-right appbar-actions">
        <slot name="actions" />

        <v-btn
          class="topbar-btn topbar-btn--icon"
          variant="text"
          aria-label="Einstellungen"
          @click="ui.openSettings()"
        >
          <v-icon size="20">mdi-cog-outline</v-icon>
        </v-btn>

        <v-menu location="bottom end" offset="8">
          <template #activator="{ props: accountMenuProps }">
            <v-btn
              class="topbar-btn topbar-btn--icon"
              variant="text"
              aria-label="Konto"
              v-bind="accountMenuProps"
            >
              <v-icon size="20">mdi-account-circle-outline</v-icon>
            </v-btn>
          </template>
          <v-list class="account-menu" min-width="300">
            <div class="account-card">
              <UserAvatar :user="auth.user" current :size="44" />
              <div class="account-card__info">
                <div class="account-card__name">
                  {{ auth.user?.display_name || auth.username }}
                </div>
                <div v-if="auth.user?.email" class="account-card__email">
                  {{ auth.user.email }}
                </div>
                <v-chip
                  size="x-small"
                  :color="auth.isAdmin ? 'primary' : undefined"
                  variant="tonal"
                  class="account-card__role"
                >
                  {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
                </v-chip>
              </div>
            </div>

            <div class="account-meta">
              <div class="account-meta__row">
                <v-icon size="14">mdi-clock-outline</v-icon>
                <span>Letzte Anmeldung: {{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}</span>
              </div>
              <div class="account-meta__row">
                <v-icon size="14">mdi-calendar-outline</v-icon>
                <span>Mitglied seit {{ formatDateTime(auth.user?.created_at) || '–' }}</span>
              </div>
            </div>

            <v-divider />

            <v-list-item
              prepend-icon="mdi-account-outline"
              title="Konto"
              @click="ui.openAccount('profile')"
            />
            <v-list-item
              v-if="auth.isAdmin"
              prepend-icon="mdi-account-group-outline"
              title="Benutzerverwaltung"
              @click="ui.openAccount('users')"
            />

            <v-divider />

            <v-list-item
              prepend-icon="mdi-logout"
              title="Abmelden"
              class="account-logout"
              @click="onLogout"
            />
          </v-list>
        </v-menu>
      </div>
    </div>
  </v-app-bar>
</template>

<script setup>
import { useRouter } from 'vue-router';

import UserAvatar from './UserAvatar.vue';
import { useAuthStore } from '../stores/auth.js';
import { useUiStore } from '../stores/ui.js';
import { formatDateTime } from '../utils/dates';

const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

function goHome() {
  router.push('/');
}

async function onLogout() {
  await auth.logout();
  router.push('/login');
}
</script>

<style>
/* Chrome-/Layout-Regeln der App-Top-Bar. Slot-Inhalte (Suche, Import, KI)
   werden von der globalen CSS der jeweiligen View gestylt. Globale (nicht
   gescopte) Regeln, damit die Bar überall identisch aussieht. */
.app-topbar {
  color: rgba(248, 250, 255, 0.96) !important;
  background: var(--pm-appbar-bg) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

.app-topbar .v-toolbar__content {
  padding: 0;
}

.appbar-layout {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 16px;
}

.appbar-center {
  justify-self: center;
  width: min(480px, 100%);
  padding: 0 16px;
  min-width: 0;
  box-sizing: border-box;
}

.appbar-left {
  flex-shrink: 0;
}

.appbar-right {
  flex-shrink: 0;
}

.app-title {
  min-width: 0;
}

.app-title__brand {
  color: rgba(248, 250, 255, 0.98);
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.015em;
}

.app-title__brand-button {
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.appbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.topbar-btn {
  height: 38px;
  margin: 0 !important;
  border-radius: 999px;
  text-transform: none;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: rgba(248, 250, 255, 0.95) !important;
}

.topbar-btn--icon:hover {
  background: rgba(255, 255, 255, 0.14);
}

.topbar-btn--icon {
  min-width: 38px;
  width: 38px;
  padding: 0;
}

.topbar-btn .v-icon {
  color: rgba(250, 252, 255, 0.94);
}

.papermind-app.v-theme--dark .topbar-btn--icon:hover {
  background: color-mix(in srgb, var(--pm-appbar-bg) 70%, white 30%);
}

/* ── Konto-Menü (v-menu wird wegteleportiert → globale, nicht gescopte CSS) ── */
.account-menu {
  border-radius: 14px;
  padding: 0;
  overflow: hidden;
}

.account-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 12px;
}

.account-card__info {
  min-width: 0;
}

.account-card__name {
  font-size: 0.98rem;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-card__email {
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-card__role {
  margin-top: 6px;
}

.account-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 16px 12px;
}

.account-meta__row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.account-logout {
  color: rgb(var(--v-theme-error)) !important;
}

.account-logout .v-icon {
  color: rgb(var(--v-theme-error)) !important;
}
</style>
