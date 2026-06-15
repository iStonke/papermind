<template>
  <v-app theme="dark">
    <v-main ref="rootEl" class="login-main">
      <div class="login-glow login-glow--one" aria-hidden="true" />
      <div class="login-glow login-glow--two" aria-hidden="true" />
      <div class="login-glow login-glow--three" aria-hidden="true" />

      <div class="login-wrapper">
        <v-card class="login-card" rounded="xl">
          <div class="login-logo login-rise login-rise--1" aria-hidden="true">
            <v-icon icon="mdi-brain" size="34" />
          </div>
          <div class="login-brand login-rise login-rise--2">PaperMind</div>
          <div class="login-subtitle login-rise login-rise--3">Bitte anmelden</div>

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
              class="mb-4 login-rise login-rise--4"
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
              class="mb-2 login-rise login-rise--5"
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
              class="login-rise login-rise--6"
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
import { onBeforeUnmount, onMounted, ref } from 'vue';
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

// ── Maus-Parallax: Aura und Karte folgen leicht dem Cursor (Tiefe) ──────────
const rootEl = ref(null);
let parallaxTarget = null;

function rootElement() {
  const el = rootEl.value;
  return el?.$el || el || null;
}

function onParallaxMove(event) {
  if (!parallaxTarget) return;
  const rect = parallaxTarget.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const px = (event.clientX - rect.left) / rect.width - 0.5;
  const py = (event.clientY - rect.top) / rect.height - 0.5;
  parallaxTarget.style.setProperty('--px', px.toFixed(3));
  parallaxTarget.style.setProperty('--py', py.toFixed(3));
}

function resetParallax() {
  if (!parallaxTarget) return;
  parallaxTarget.style.setProperty('--px', '0');
  parallaxTarget.style.setProperty('--py', '0');
}

onMounted(() => {
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  if (reduce) return;
  parallaxTarget = rootElement();
  if (!parallaxTarget) return;
  parallaxTarget.addEventListener('pointermove', onParallaxMove);
  parallaxTarget.addEventListener('pointerleave', resetParallax);
});

onBeforeUnmount(() => {
  if (!parallaxTarget) return;
  parallaxTarget.removeEventListener('pointermove', onParallaxMove);
  parallaxTarget.removeEventListener('pointerleave', resetParallax);
  parallaxTarget = null;
});

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
  isolation: isolate;
  background: linear-gradient(135deg, #06131a 0%, #071824 45%, #08101b 100%);
}

.login-main::before,
.login-main::after {
  content: "";
  position: absolute;
  pointer-events: none;
  z-index: 0;
}

.login-main::before {
  inset: -30%;
  background:
    radial-gradient(circle at 18% 22%, rgba(34, 211, 238, 0.22) 0 12%, transparent 34%),
    radial-gradient(circle at 72% 34%, rgba(8, 145, 178, 0.18) 0 10%, transparent 31%),
    radial-gradient(circle at 40% 78%, rgba(13, 148, 136, 0.18) 0 11%, transparent 33%),
    radial-gradient(circle at 86% 76%, rgba(59, 130, 246, 0.11) 0 9%, transparent 28%);
  opacity: 0.92;
  transform: translate3d(calc(var(--px, 0) * -14px), calc(var(--py, 0) * -14px), 0);
  animation: login-aurora-drift 18s ease-in-out infinite alternate;
  will-change: transform;
}

.login-main::after {
  inset: -18%;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(255, 255, 255, 0.04), transparent 34%),
    radial-gradient(ellipse at 72% 82%, rgba(34, 211, 238, 0.08), transparent 42%);
  opacity: 0.68;
  transform: translate3d(calc(var(--px, 0) * 10px), calc(var(--py, 0) * 10px), 0);
  animation: login-sheen-drift 24s ease-in-out infinite alternate;
  will-change: transform;
}

/* Weiche Farb-Auren ohne Blur-Kacheln: Radials laufen gross ueber den Viewport,
   damit keine rechteckigen Compositing-Artefakte sichtbar werden. */
.login-glow {
  position: absolute;
  inset: -42%;
  border-radius: 0;
  opacity: 0.42;
  z-index: 0;
  pointer-events: none;
  background-repeat: no-repeat;
  background-size: 100% 100%;
  will-change: transform, opacity;
  transition: opacity 0.4s ease-out;
}

.login-glow--one {
  background: radial-gradient(circle at 12% 18%, rgba(8, 145, 178, 0.34) 0%, transparent 42%);
  animation: drift-one 13s ease-in-out infinite alternate;
}

.login-glow--two {
  background: radial-gradient(circle at 88% 86%, rgba(34, 211, 238, 0.28) 0%, transparent 40%);
  animation: drift-two 16s ease-in-out infinite alternate;
}

.login-glow--three {
  opacity: 0.32;
  background: radial-gradient(circle at 46% 56%, rgba(13, 148, 136, 0.26) 0%, transparent 38%);
  animation: drift-three 19s ease-in-out infinite alternate;
}

@keyframes login-aurora-drift {
  0% {
    transform:
      translate3d(calc(-2% + var(--px, 0) * -14px), calc(-1% + var(--py, 0) * -14px), 0)
      rotate(0deg)
      scale(1.02);
  }
  50% {
    transform:
      translate3d(calc(2% + var(--px, 0) * -14px), calc(3% + var(--py, 0) * -14px), 0)
      rotate(5deg)
      scale(1.07);
  }
  100% {
    transform:
      translate3d(calc(4% + var(--px, 0) * -14px), calc(-2% + var(--py, 0) * -14px), 0)
      rotate(-3deg)
      scale(1.04);
  }
}

@keyframes login-sheen-drift {
  0% {
    transform:
      translate3d(calc(2% + var(--px, 0) * 10px), calc(-2% + var(--py, 0) * 10px), 0)
      rotate(-4deg)
      scale(1.02);
  }
  100% {
    transform:
      translate3d(calc(-3% + var(--px, 0) * 10px), calc(3% + var(--py, 0) * 10px), 0)
      rotate(4deg)
      scale(1.06);
  }
}

@keyframes drift-one {
  0% {
    transform: translate3d(calc(var(--px, 0) * -24px), calc(var(--py, 0) * -24px), 0) scale(1);
  }
  100% {
    transform: translate3d(calc(9vw + var(--px, 0) * -24px), calc(6vh + var(--py, 0) * -24px), 0) scale(1.1);
  }
}

@keyframes drift-two {
  0% {
    transform: translate3d(calc(var(--px, 0) * 28px), calc(var(--py, 0) * 28px), 0) scale(1.02);
  }
  100% {
    transform: translate3d(calc(-8vw + var(--px, 0) * 28px), calc(-8vh + var(--py, 0) * 28px), 0) scale(1.14);
  }
}

@keyframes drift-three {
  0% {
    transform: translate3d(calc(var(--px, 0) * 16px), calc(var(--py, 0) * -16px), 0) scale(1);
    opacity: 0.24;
  }
  100% {
    transform: translate3d(calc(6vw + var(--px, 0) * 16px), calc(-5vh + var(--py, 0) * -16px), 0) scale(1.12);
    opacity: 0.38;
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
  /* Karte folgt dem Cursor leicht (geringere Amplitude als die Aura = Tiefe). */
  transform: translate(calc(var(--px, 0) * 8px), calc(var(--py, 0) * 8px));
  transition: transform 0.3s ease-out;
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
  animation: card-in 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Gestaffelter Auftritt: Logo → Titel → Felder → Button erscheinen nacheinander. */
.login-rise {
  animation: login-rise 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.login-rise--1 { animation-delay: 0.10s; }
.login-rise--2 { animation-delay: 0.17s; }
.login-rise--3 { animation-delay: 0.23s; }
.login-rise--4 { animation-delay: 0.31s; }
.login-rise--5 { animation-delay: 0.39s; }
.login-rise--6 { animation-delay: 0.48s; }

@keyframes login-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
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

/* Atmendes Logo: sanftes Heben + Glow-Puls, startet nach dem Auftritt. */
.login-logo.login-rise {
  animation:
    login-rise 0.55s cubic-bezier(0.22, 1, 0.36, 1) both,
    logo-breathe 4.5s ease-in-out 1s infinite;
}

@keyframes logo-breathe {
  0%, 100% {
    transform: translateY(0);
    box-shadow: 0 8px 24px rgba(34, 211, 238, 0.32);
  }
  50% {
    transform: translateY(-3px);
    box-shadow: 0 14px 32px rgba(34, 211, 238, 0.55);
  }
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

/* Bewegungsempfindliche Nutzer/Systeme: alle Dauer-Animationen still, Inhalte
   sofort sichtbar, Parallax neutral. Der Maus-Parallax wird zusätzlich im Script
   gar nicht erst registriert, wenn reduce gesetzt ist. */
@media (prefers-reduced-motion: reduce) {
  .login-glow--one,
  .login-glow--two,
  .login-glow--three,
  .login-logo.login-rise {
    animation: none;
  }
  .login-card,
  .login-rise {
    animation: none;
    opacity: 1;
    transform: none;
  }
  .login-glow,
  .login-wrapper {
    transform: none;
  }
}
</style>
