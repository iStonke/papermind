<template>
  <div class="acct-edit">
    <div class="acct-edit__rows">
      <button type="button" class="acct-row" @click="emit('navigate', 'profile-edit')">
        <v-icon size="22" class="acct-row__icon">mdi-card-account-details-outline</v-icon>
        <span class="acct-row__text">
          <span class="acct-row__title">Anzeigename &amp; E-Mail ändern</span>
          <span class="acct-row__sub">Profildaten bearbeiten</span>
        </span>
        <v-icon size="22" class="acct-row__chevron">mdi-chevron-right</v-icon>
      </button>

      <button type="button" class="acct-row" @click="emit('navigate', 'password')">
        <v-icon size="22" class="acct-row__icon">mdi-lock-outline</v-icon>
        <span class="acct-row__text">
          <span class="acct-row__title">Passwort ändern</span>
          <span class="acct-row__sub">Passwort und Anmeldesicherheit</span>
        </span>
        <v-icon size="22" class="acct-row__chevron">mdi-chevron-right</v-icon>
      </button>

      <button type="button" class="acct-row" @click="emit('navigate', 'session')">
        <v-icon size="22" class="acct-row__icon">mdi-shield-lock-outline</v-icon>
        <span class="acct-row__text">
          <span class="acct-row__title">Sitzung &amp; Sicherheit</span>
          <span class="acct-row__sub">Automatische Abmeldung bei Inaktivität</span>
        </span>
        <v-icon size="22" class="acct-row__chevron">mdi-chevron-right</v-icon>
      </button>

      <button type="button" class="acct-row" @click="emit('navigate', 'avatar')">
        <v-icon size="22" class="acct-row__icon">mdi-image-outline</v-icon>
        <span class="acct-row__text">
          <span class="acct-row__title">Profilbild verwalten</span>
          <span class="acct-row__sub">Hochladen, zuschneiden oder entfernen</span>
        </span>
        <v-icon size="22" class="acct-row__chevron">mdi-chevron-right</v-icon>
      </button>

      <button
        v-if="auth.isAdmin"
        type="button"
        class="acct-row"
        @click="emit('navigate', 'users')"
      >
        <v-icon size="22" class="acct-row__icon">mdi-account-group-outline</v-icon>
        <span class="acct-row__text">
          <span class="acct-row__title">Benutzerverwaltung</span>
          <span class="acct-row__sub">Rollen, Status und Zugänge · nur für Administratoren</span>
        </span>
        <v-icon size="22" class="acct-row__chevron">mdi-chevron-right</v-icon>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '../../stores/auth.js';

const emit = defineEmits(['navigate']);

const auth = useAuthStore();
</script>

<style scoped>
.acct-edit {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 560px;
  margin-inline: auto;
}
.acct-edit__rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.acct-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.acct-row:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}
.acct-row__icon {
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.acct-row__text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.acct-row__title {
  font-size: 0.96rem;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}
.acct-row__sub {
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.58);
}
.acct-row__chevron {
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.4);
}

</style>
