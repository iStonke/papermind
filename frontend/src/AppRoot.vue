<template>
  <router-view />
</template>

<script setup>
import { watch } from 'vue';
import { useRouter } from 'vue-router';

import { useAuthStore } from './stores/auth.js';

const router = useRouter();
const authStore = useAuthStore();

// Wird die Session ungültig (z. B. 401 während der Nutzung), zurück zum Login.
watch(
  () => authStore.isAuthenticated,
  (isAuth) => {
    if (!isAuth && router.currentRoute.value.name !== 'login') {
      router.push({ name: 'login' });
    }
  }
);
</script>
