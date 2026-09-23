<template>
  <v-menu location="top" offset="10">
    <template #activator="{ props: menuProps }">
      <button type="button" class="sidebar-account" v-bind="menuProps" aria-label="Konto">
        <UserAvatar :user="auth.user" current :size="30" />
        <div class="sidebar-account__info">
          <div class="sidebar-account__name">{{ auth.user?.display_name || auth.username }}</div>
        </div>
        <v-icon size="16" class="sidebar-account__chev">mdi-chevron-up</v-icon>
      </button>
    </template>

    <v-list class="account-menu" min-width="280">
      <div class="account-card">
        <div class="account-card__avatar">
          <UserAvatar :user="auth.user" current :size="46" />
          <span class="account-card__dot" aria-hidden="true" />
        </div>
        <div class="account-card__info">
          <div class="account-card__name">
            {{ auth.user?.display_name || auth.username }}
          </div>
          <div v-if="auth.user?.email" class="account-card__email">
            {{ auth.user.email }}
          </div>
          <span class="account-card__role">
            <v-icon size="12">{{ auth.isAdmin ? 'mdi-shield-account-outline' : 'mdi-account-outline' }}</v-icon>
            {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
          </span>
        </div>
      </div>

      <div class="account-meta">
        <div class="account-meta__row">
          <span class="account-meta__label">
            <v-icon size="14">mdi-clock-outline</v-icon>
            Letzte Anmeldung
          </span>
          <span class="account-meta__value">{{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}</span>
        </div>
        <div class="account-meta__row">
          <span class="account-meta__label">
            <v-icon size="14">mdi-calendar-outline</v-icon>
            Mitglied seit
          </span>
          <span class="account-meta__value">{{ formatDateTime(auth.user?.created_at) || '–' }}</span>
        </div>
      </div>

      <v-divider class="account-sep" />

      <div class="account-actions">
        <v-list-item
          prepend-icon="mdi-account-outline"
          append-icon="mdi-chevron-right"
          title="Konto"
          rounded="lg"
          class="account-action"
          @click="ui.openAccount('profile')"
        />

        <v-list-item
          prepend-icon="mdi-logout"
          title="Abmelden"
          rounded="lg"
          class="account-action account-logout"
          @click="onLogout"
        />
      </div>
    </v-list>
  </v-menu>
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

async function onLogout() {
  await auth.logout();
  router.push('/login');
}
</script>

<style scoped>
.sidebar-account {
  /* So breit wie der Inhalt: Pfeil sitzt direkt hinter dem Namen. */
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 9px;
  background: transparent;
  border: 0;
  border-radius: 10px;
  padding: 5px 6px;
  cursor: pointer;
  text-align: left;
  transition: background-color var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}

.sidebar-account:hover {
  background: var(--pm-sidebar-hover);
}

.sidebar-account__info {
  flex: 0 1 auto;
  min-width: 0;
  line-height: 1.2;
}

.sidebar-account__name {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--pm-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-account__chev {
  color: var(--pm-muted);
  flex: none;
}
</style>

<style>
/* Konto-Menü wird von v-menu ans Body-Ende teleportiert → globale Styles.
   Die --pm-*-Tokens sind auf .v-overlay-container > .v-overlay.v-theme--* gescoped
   (siehe theme.css) und stehen hier zur Verfügung.
   Kontur-Prinzip: Türkis nur als Zustand, Zonentrennung über Fläche, nicht Farbe. */
.account-menu {
  border-radius: 14px;
  padding: 0;
  overflow: hidden;
  background: var(--pm-app-surface-raised) !important;
  border: 1px solid var(--pm-divider);
  box-shadow: var(--pm-shadow);
}

/* Kopf: eigene, neutrale Flächenstufe statt Farbverlauf */
.account-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--pm-viewer-surface);
  border-bottom: 1px solid var(--pm-divider);
}

.account-card__avatar {
  position: relative;
  flex: none;
}

.account-card__dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--pm-accent);
  border: 2px solid var(--pm-viewer-surface);
}

.account-card__info {
  min-width: 0;
}

.account-card__name {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--pm-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-card__email {
  font-size: 0.79rem;
  color: var(--pm-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-card__role {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  padding: 3px 9px;
  font-size: 0.69rem;
  font-weight: 600;
  line-height: 1.4;
  border-radius: 999px;
  color: var(--pm-text);
  background: var(--pm-app-surface-raised);
  border: 1px solid var(--pm-divider);
}

.account-card__role .v-icon {
  color: var(--pm-accent);
}

/* Meta: ruhige, hairline-getrennte Zeilen, kein Farbklotz */
.account-meta {
  padding: 10px 16px 12px;
}

.account-meta__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 3px 0;
  font-size: 0.76rem;
  color: var(--pm-muted);
}

.account-meta__label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.account-meta__label .v-icon {
  color: var(--pm-muted);
}

.account-meta__value {
  color: var(--pm-text);
  font-weight: 500;
  white-space: nowrap;
}

.account-sep {
  border-color: var(--pm-divider) !important;
  opacity: 1;
}

.account-actions {
  padding: 5px 6px 6px;
}

.account-action {
  min-height: 32px !important;
  padding-top: 2px !important;
  padding-bottom: 2px !important;
  color: var(--pm-text);
}

.account-action .v-list-item-title {
  font-size: 0.8rem;
}

.account-action .v-list-item__prepend {
  margin-inline-end: -6px;
}

.account-action .v-list-item__prepend .v-icon {
  font-size: 17px;
}

.account-action .v-list-item__append .v-icon {
  font-size: 15px;
}

.account-action .v-list-item__prepend .v-icon,
.account-action .v-list-item__append .v-icon {
  color: var(--pm-muted);
  opacity: 1;
}

.account-action:hover {
  background: var(--pm-row-hover) !important;
}

.account-logout {
  color: rgb(var(--v-theme-error)) !important;
}

.account-logout .v-list-item__prepend .v-icon {
  color: rgb(var(--v-theme-error)) !important;
}

.account-logout:hover {
  background: rgba(var(--v-theme-error), 0.1) !important;
}
</style>
