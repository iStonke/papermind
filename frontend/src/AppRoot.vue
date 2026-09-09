<template>
  <router-view v-slot="{ Component }">
    <component :is="Component" v-if="Component" />
    <AppLoadingScreen v-else :timed-out="bootTimedOut" />
  </router-view>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import AppLoadingScreen from './components/AppLoadingScreen.vue';

import { useAuthStore } from './stores/auth.js';

const router = useRouter();
const authStore = useAuthStore();
const bootTimedOut = ref(false);
let bootTimer = null;

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
    if (
      status !== 'unknown'
      && !isAuth
      && router.currentRoute.value.meta.requiresAuth
    ) {
      router.push({ name: 'login' });
    }
  }
);
</script>
