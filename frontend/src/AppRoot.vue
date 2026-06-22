<template>
  <router-view v-slot="{ Component }">
    <component :is="Component" v-if="Component" />
    <div v-else class="app-boot-screen" aria-label="PaperMind wird geladen">
      <div class="app-boot-card">
        <div class="app-boot-logo">
          <span class="app-boot-mark">P</span>
        </div>
        <div class="app-boot-title">PaperMind</div>
        <div v-if="!bootTimedOut" class="app-boot-subtitle">
          Wird geladen<span class="app-boot-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span>
        </div>
        <template v-else>
          <div class="app-boot-subtitle app-boot-subtitle--error">
            Die Anwendung konnte nicht vollständig gestartet werden.
          </div>
          <button type="button" class="app-boot-reload" @click="reloadApp">
            Neu laden
          </button>
        </template>
      </div>
    </div>
  </router-view>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from './stores/auth.js';

const router = useRouter();
const authStore = useAuthStore();
const bootTimedOut = ref(false);
let bootTimer = null;

function reloadApp() {
  window.location.reload();
}

onMounted(() => {
  bootTimer = window.setTimeout(() => {
    bootTimedOut.value = true;
  }, 12_000);
});

onBeforeUnmount(() => {
  if (bootTimer) window.clearTimeout(bootTimer);
});

// Wird die Session ungültig (z. B. 401 während der Nutzung), zurück zum Login.
watch(
  () => [authStore.status, authStore.isAuthenticated],
  ([status, isAuth]) => {
    if (status !== 'unknown' && !isAuth && router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' });
    }
  }
);
</script>

<style scoped>
.app-boot-screen {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  background: rgb(var(--v-theme-background, 245 247 251));
}

.app-boot-card {
  display: grid;
  justify-items: center;
  gap: 14px;
  color: rgb(var(--v-theme-on-background, 31 41 55));
  animation: boot-rise 600ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes boot-rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Logo mit pulsierendem Halo dahinter */
.app-boot-logo {
  position: relative;
  width: 64px;
  height: 64px;
}

.app-boot-logo::before {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 24px;
  border: 2px solid rgb(var(--v-theme-primary, 13 148 166));
  opacity: 0;
  animation: boot-halo 2.4s ease-out infinite;
}

@keyframes boot-halo {
  0%   { opacity: 0.45; transform: scale(0.9); }
  70%  { opacity: 0;    transform: scale(1.15); }
  100% { opacity: 0;    transform: scale(1.15); }
}

.app-boot-mark {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: rgb(var(--v-theme-primary, 13 148 166));
  color: #fff;
  font-weight: 800;
  font-size: 1.7rem;
  overflow: hidden;
  animation: boot-breathe 2.4s ease-in-out infinite;
}

/* Glanz-Sweep über das Logo */
.app-boot-mark::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 32%, rgb(255 255 255 / 0.55) 50%, transparent 68%);
  transform: translateX(-130%);
  animation: boot-sheen 2.4s ease-in-out infinite;
}

@keyframes boot-breathe {
  0%, 100% { transform: scale(1);    box-shadow: 0 8px 22px rgb(var(--v-theme-primary, 13 148 166) / 0.30); }
  50%      { transform: scale(1.06); box-shadow: 0 14px 32px rgb(var(--v-theme-primary, 13 148 166) / 0.45); }
}

@keyframes boot-sheen {
  0%   { transform: translateX(-130%); }
  55%  { transform: translateX(130%); }
  100% { transform: translateX(130%); }
}

.app-boot-title {
  font-weight: 700;
  font-size: 1.25rem;
  letter-spacing: 0.01em;
}

.app-boot-subtitle {
  font-size: 0.85rem;
  opacity: 0.64;
}

.app-boot-subtitle--error {
  max-width: 320px;
  text-align: center;
}

.app-boot-reload {
  border: 0;
  border-radius: 10px;
  padding: 9px 16px;
  background: rgb(var(--v-theme-primary, 13 148 166));
  color: #fff;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.app-boot-dots span {
  display: inline-block;
  animation: boot-dot 1.4s ease-in-out infinite;
}
.app-boot-dots span:nth-child(2) { animation-delay: 0.18s; }
.app-boot-dots span:nth-child(3) { animation-delay: 0.36s; }

@keyframes boot-dot {
  0%, 100% { opacity: 0.2; }
  50%      { opacity: 1; }
}

/* Barrierefreiheit: Bewegung respektieren */
@media (prefers-reduced-motion: reduce) {
  .app-boot-card,
  .app-boot-logo::before,
  .app-boot-mark,
  .app-boot-mark::after,
  .app-boot-dots span {
    animation: none;
  }
}
</style>
