<template>
  <v-app theme="dark">
    <v-main class="login-main">
      <div class="login-glow login-glow--one" aria-hidden="true" />
      <div class="login-glow login-glow--two" aria-hidden="true" />

      <div class="login-wrapper">
        <v-card class="login-card" rounded="xl">
          <div class="login-logo" aria-hidden="true">
            <v-icon icon="mdi-brain" size="34" />
          </div>
          <div class="login-brand">PaperMind</div>
          <div class="login-subtitle">Bitte anmelden</div>

          <v-form @submit.prevent="submit">
            <v-text-field
              v-model="username"
              label="Benutzername oder E-Mail"
              prepend-inner-icon="mdi-account-outline"
              variant="outlined"
              density="comfortable"
              autocomplete="username"
              autofocus
              :disabled="loading"
              hide-details="auto"
              class="mb-4"
            />
            <v-text-field
              v-model="password"
              label="Passwort"
              prepend-inner-icon="mdi-lock-outline"
              :type="showPassword ? 'text' : 'password'"
              :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
              variant="outlined"
              density="comfortable"
              autocomplete="current-password"
              :disabled="loading"
              hide-details="auto"
              class="mb-2"
              @click:append-inner="showPassword = !showPassword"
            />

            <v-alert
              v-if="error"
              type="error"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ error }}
            </v-alert>

            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              :loading="loading"
              :disabled="!username || !password"
            >
              Anmelden
            </v-btn>
          </v-form>
        </v-card>
      </div>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '../stores/auth.js';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const username = ref('');
const password = ref('');
const showPassword = ref(false);
const loading = ref(false);
const error = ref('');

async function submit() {
  if (!username.value || !password.value || loading.value) return;
  loading.value = true;
  error.value = '';
  try {
    await authStore.login(username.value.trim(), password.value);
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/';
    router.push(redirect);
  } catch (err) {
    error.value = err?.message || 'Anmeldung fehlgeschlagen.';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-main {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 20% 20%, #0c2a33 0%, transparent 55%),
    radial-gradient(circle at 85% 80%, #0d2233 0%, transparent 50%),
    linear-gradient(135deg, #0a0f19 0%, #0b1320 60%, #0a0f19 100%);
}

/* Weiche Farb-Aura hinter der Karte fuer mehr Tiefe. */
.login-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.5;
  z-index: 0;
  pointer-events: none;
}

.login-glow--one {
  width: 420px;
  height: 420px;
  top: -120px;
  left: -80px;
  background: radial-gradient(circle, rgba(8, 145, 178, 0.5), transparent 70%);
  animation: float-glow 14s ease-in-out infinite;
}

.login-glow--two {
  width: 360px;
  height: 360px;
  bottom: -100px;
  right: -60px;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.38), transparent 70%);
  animation: float-glow 18s ease-in-out infinite reverse;
}

@keyframes float-glow {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(40px, 30px) scale(1.12);
  }
}

.login-wrapper {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  padding: 36px 32px 32px;
  /* Glassmorphism */
  background: rgba(14, 20, 32, 0.62) !important;
  backdrop-filter: blur(22px) saturate(140%);
  -webkit-backdrop-filter: blur(22px) saturate(140%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  animation: card-in 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 18px;
  color: #fff;
  background: linear-gradient(135deg, #0891b2, #22d3ee);
  box-shadow: 0 8px 24px rgba(34, 211, 238, 0.4);
}

.login-brand {
  font-size: 1.8rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-align: center;
  color: #ffffff;
}

.login-subtitle {
  text-align: center;
  color: rgba(231, 237, 246, 0.6);
  margin-bottom: 26px;
}
</style>
