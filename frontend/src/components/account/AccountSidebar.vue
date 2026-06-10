<template>
  <div class="acct-side">
    <button
      type="button"
      class="acct-side__avatar"
      aria-label="Profilbild bearbeiten"
      @click="emit('navigate', 'avatar')"
    >
      <UserAvatar :user="auth.user" current :size="120" />
      <span class="acct-side__avatar-badge">
        <v-icon size="16">mdi-pencil</v-icon>
      </span>
    </button>

    <div class="acct-side__name">{{ auth.user?.display_name || auth.username }}</div>
    <div v-if="auth.user?.email" class="acct-side__email">{{ auth.user.email }}</div>

    <v-chip
      size="small"
      :color="auth.isAdmin ? 'primary' : undefined"
      variant="tonal"
      class="acct-side__role"
    >
      {{ auth.isAdmin ? 'Administrator' : 'Benutzer' }}
    </v-chip>

    <div class="acct-fact">
      <span class="acct-fact__label">Mitglied seit</span>
      <span class="acct-fact__value">{{ formatDateTime(auth.user?.created_at) || '–' }}</span>
    </div>
    <div class="acct-fact">
      <span class="acct-fact__label">Letzte Anmeldung</span>
      <span class="acct-fact__value">{{ formatDateTime(auth.user?.last_login_at) || 'unbekannt' }}</span>
    </div>
  </div>
</template>

<script setup>
import UserAvatar from '../UserAvatar.vue';
import { useAuthStore } from '../../stores/auth.js';
import { formatDateTime } from '../../utils/dates';

const emit = defineEmits(['navigate']);
const auth = useAuthStore();
</script>

<style scoped>
.acct-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.acct-side__avatar {
  position: relative;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  border-radius: 50%;
}
.acct-side__avatar-badge {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
  transition: background 0.15s ease;
}
.acct-side__avatar:hover .acct-side__avatar-badge {
  background: color-mix(in srgb, rgb(var(--v-theme-surface)) 86%, rgb(var(--v-theme-primary)));
  border-color: rgba(var(--v-theme-primary), 0.5);
  color: rgb(var(--v-theme-primary));
}
.acct-side__name {
  margin-top: 16px;
  font-size: 1.15rem;
  font-weight: 600;
  line-height: 1.2;
}
.acct-side__email {
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
  margin-top: 2px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.acct-side__role {
  margin-top: 12px;
}
.acct-fact {
  margin-top: 14px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 12px;
}
.acct-fact__label {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
.acct-fact__value {
  font-size: 0.9rem;
  font-weight: 500;
}
</style>
