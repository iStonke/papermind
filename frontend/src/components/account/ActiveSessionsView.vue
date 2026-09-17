<template>
  <div class="sessions">
    <div v-if="loading" class="sessions__state">
      <v-progress-circular indeterminate size="20" width="2" />
      <span>Sitzungen werden geladen …</span>
    </div>

    <div v-else-if="error" class="sessions__state sessions__state--error">
      {{ error }}
    </div>

    <template v-else>
      <div class="sessions__list">
        <div v-for="s in sessions" :key="s.id" class="sessions__row">
          <v-icon size="22" class="sessions__icon">{{ deviceInfo(s.user_agent).icon }}</v-icon>
          <div class="sessions__info">
            <div class="sessions__title">
              {{ deviceInfo(s.user_agent).label }}
              <span v-if="s.current" class="sessions__badge">Diese Sitzung</span>
            </div>
            <div class="sessions__sub">
              {{ s.client_ip || 'unbekannte IP' }}
              <span class="sessions__dot">·</span>
              zuletzt aktiv {{ formatDateTime(s.last_used_at) || 'unbekannt' }}
            </div>
          </div>
          <v-btn
            v-if="!s.current"
            variant="text"
            size="small"
            class="sessions__revoke"
            :loading="revokingId === s.id"
            @click="revokeOne(s)"
          >
            Abmelden
          </v-btn>
          <span v-else class="sessions__here" aria-hidden="true">
            <v-icon size="16">mdi-check-circle</v-icon>
          </span>
        </div>
      </div>

      <div v-if="hasOthers" class="sessions__foot">
        <v-btn
          variant="tonal"
          color="primary"
          size="small"
          class="sessions__revoke-all"
          prepend-icon="mdi-logout-variant"
          :loading="revokingOthers"
          @click="revokeOthers"
        >
          Alle anderen abmelden
        </v-btn>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';

import { listSessions, revokeOtherSessions, revokeSession } from '../../api/auth.js';
import { notifyError, useNotifications } from '../../stores/notifications';
import { formatDateTime } from '../../utils/dates';

const { notify } = useNotifications();

const sessions = ref([]);
const loading = ref(false);
const error = ref('');
const revokingId = ref(null);
const revokingOthers = ref(false);

const hasOthers = computed(() => sessions.value.some((s) => !s.current));

function deviceInfo(ua) {
  const agent = ua || '';
  let browser = 'Unbekannter Browser';
  if (/edg/i.test(agent)) browser = 'Edge';
  else if (/opr|opera/i.test(agent)) browser = 'Opera';
  else if (/chrome|crios/i.test(agent)) browser = 'Chrome';
  else if (/firefox|fxios/i.test(agent)) browser = 'Firefox';
  else if (/safari/i.test(agent)) browser = 'Safari';

  let os = '';
  if (/windows/i.test(agent)) os = 'Windows';
  else if (/iphone|ipad|ipod/i.test(agent)) os = 'iOS';
  else if (/mac os x|macintosh/i.test(agent)) os = 'macOS';
  else if (/android/i.test(agent)) os = 'Android';
  else if (/linux/i.test(agent)) os = 'Linux';

  const isMobile = /mobile|iphone|android/i.test(agent);
  const icon = /ipad|tablet/i.test(agent)
    ? 'mdi-tablet'
    : isMobile
      ? 'mdi-cellphone'
      : 'mdi-monitor';

  return { label: os ? `${browser} · ${os}` : browser, icon };
}

async function refresh() {
  loading.value = true;
  error.value = '';
  try {
    sessions.value = await listSessions();
  } catch (err) {
    error.value = err?.message || 'Sitzungen konnten nicht geladen werden.';
  } finally {
    loading.value = false;
  }
}

async function revokeOne(session) {
  revokingId.value = session.id;
  try {
    await revokeSession(session.id);
    notify({ type: 'success', message: 'Sitzung abgemeldet.' });
    await refresh();
  } catch (err) {
    notifyError(err, 'Sitzung konnte nicht abgemeldet werden.');
  } finally {
    revokingId.value = null;
  }
}

async function revokeOthers() {
  revokingOthers.value = true;
  try {
    await revokeOtherSessions();
    notify({ type: 'success', message: 'Alle anderen Sitzungen abgemeldet.' });
    await refresh();
  } catch (err) {
    notifyError(err, 'Sitzungen konnten nicht abgemeldet werden.');
  } finally {
    revokingOthers.value = false;
  }
}

onMounted(refresh);
</script>

<style scoped>
.sessions {
  max-width: 460px;
  margin-inline: 0;
}
.sessions__state {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding: 6px 0;
}
.sessions__state--error {
  color: rgb(var(--v-theme-error));
}
.sessions__list {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  overflow: hidden;
}
.sessions__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
}
.sessions__row + .sessions__row {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}
.sessions__icon {
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.sessions__info {
  flex: 1 1 auto;
  min-width: 0;
}
.sessions__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.86rem;
  font-weight: 600;
}
.sessions__badge {
  font-size: 0.66rem;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
  color: rgb(var(--v-theme-primary));
  border: 1px solid rgba(var(--v-theme-primary), 0.4);
}
.sessions__sub {
  font-size: 0.74rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sessions__dot {
  margin: 0 2px;
}
.sessions__revoke {
  flex: 0 0 auto;
  text-transform: none;
  letter-spacing: normal;
  color: rgb(var(--v-theme-error));
}
.sessions__here {
  flex: 0 0 auto;
  display: inline-flex;
  color: rgb(var(--v-theme-primary));
  padding-right: 8px;
}
.sessions__foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.sessions__revoke-all {
  text-transform: none;
  letter-spacing: normal;
  font-weight: 600;
  border-radius: 10px;
}
</style>
