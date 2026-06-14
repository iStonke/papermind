<template>
  <router-view v-slot="{ Component }">
    <component :is="Component" v-if="Component" />
    <div v-else class="app-boot-screen" aria-label="PaperMind wird geladen">
      <div class="app-boot-card">
        <div class="app-boot-mark">P</div>
        <div class="app-boot-title">PaperMind</div>
        <div class="app-boot-subtitle">Wird geladen...</div>
      </div>
    </div>
  </router-view>
</template>

<script setup>
import { watch } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from './stores/auth.js';

const router = useRouter();
const authStore = useAuthStore();

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
  gap: 8px;
  color: rgb(var(--v-theme-on-background, 31 41 55));
}

.app-boot-mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: rgb(var(--v-theme-primary, 13 148 166));
  color: white;
  font-weight: 800;
}

.app-boot-title {
  font-weight: 700;
}

.app-boot-subtitle {
  font-size: 0.85rem;
  opacity: 0.64;
}
</style>
