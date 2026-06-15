<template>
  <v-avatar :size="size" :color="hasImage ? undefined : bgColor" class="user-avatar">
    <v-img v-if="hasImage" :src="imageUrl" :alt="`Avatar von ${displayLabel}`" cover />
    <span v-else class="user-avatar__initials" :style="{ fontSize: `${Math.round(size * 0.4)}px` }">
      {{ initials }}
    </span>
  </v-avatar>
</template>

<script setup>
import { computed } from 'vue';

import { authedUrl, getBaseUrl } from '../api/client.js';
import { useAuthStore } from '../stores/auth.js';

const props = defineProps({
  /** Nutzer-Objekt mit has_avatar, id, display_name, username. */
  user: { type: Object, default: null },
  /** Kantenlänge des Avatars in px. */
  size: { type: Number, default: 40 },
  /** True, wenn es der aktuell eingeloggte Nutzer ist (nutzt /me-Endpoint). */
  current: { type: Boolean, default: false },
});

const auth = useAuthStore();

const hasImage = computed(() => !!props.user?.has_avatar);

const displayLabel = computed(
  () => props.user?.display_name || props.user?.username || 'Benutzer'
);

const imageUrl = computed(() => {
  if (!hasImage.value) return '';
  const endpoint = props.current
    ? '/api/auth/me/avatar'
    : `/api/users/${props.user?.id}/avatar`;
  // fileTokenVersion bewusst mitlesen: Die URL hängt über authedUrl vom
  // kurzlebigen Datei-Token ab. Beim App-Start rendert der Avatar evtl. bevor das
  // Token da ist (refreshFileToken läuft async) → tokenlose URL → 401. Ohne diese
  // Abhängigkeit würde die computed nicht neu berechnen, sobald das Token kommt,
  // und der <img> bliebe kaputt. Token-Version zusätzlich an ?v= → Cache-Bust.
  return authedUrl(`${getBaseUrl()}${endpoint}?v=${auth.avatarVersion}.${auth.fileTokenVersion}`);
});

const initials = computed(() => {
  const source = (props.user?.display_name || props.user?.username || '').trim();
  if (!source) return '?';
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
});

// Deterministische Hintergrundfarbe aus dem Namen (stabiler Hue).
const bgColor = computed(() => {
  const source = displayLabel.value;
  let hash = 0;
  for (let i = 0; i < source.length; i += 1) {
    hash = source.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 55%, 45%)`;
});
</script>

<style scoped>
.user-avatar__initials {
  color: #fff;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.01em;
  user-select: none;
}
</style>
