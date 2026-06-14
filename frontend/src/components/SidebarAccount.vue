<template>
  <v-menu location="top" offset="10">
    <template #activator="{ props: menuProps }">
      <button type="button" class="sidebar-account" v-bind="menuProps" aria-label="Konto">
        <UserAvatar :user="auth.user" current :size="30" />
        <div class="sidebar-account__info">
          <div class="sidebar-account__name">{{ auth.user?.display_name || auth.username }}</div>
          <div class="sidebar-account__role">{{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}</div>
        </div>
        <v-icon size="16" class="sidebar-account__chev">mdi-chevron-up</v-icon>
      </button>
    </template>

    <v-list class="account-menu" min-width="280">
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
  flex: 1 1 auto;
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
  flex: 1 1 auto;
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

.sidebar-account__role {
  font-size: 0.7rem;
  color: var(--pm-muted);
}

.sidebar-account__chev {
  color: var(--pm-muted);
  flex: none;
}
</style>

<style>
/* Konto-Menü wird von v-menu ans Body-Ende teleportiert → globale Styles. */
.account-menu {
  border-radius: 14px;
  padding: 0;
  overflow: hidden;
  background: rgb(var(--v-theme-card)) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
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
