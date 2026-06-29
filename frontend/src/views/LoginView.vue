<template>
  <v-app theme="dark">
    <v-main class="login-main">
      <div class="login-glow login-glow--one" aria-hidden="true" />
      <div class="login-glow login-glow--two" aria-hidden="true" />
      <div class="login-glow login-glow--three" aria-hidden="true" />
      <div class="login-glow login-glow--four" aria-hidden="true" />
      <div class="login-glow login-glow--five" aria-hidden="true" />

      <div class="login-wrapper">
        <v-card class="login-card" rounded="xl">
          <div class="login-logo login-rise login-rise--1" aria-hidden="true">
            <v-icon icon="mdi-brain" size="34" />
          </div>
          <div class="login-brand login-rise login-rise--2">PaperMind</div>
          <div class="login-subtitle login-rise login-rise--3">
            {{ isRegisterMode ? 'Konto erstellen' : 'Bitte anmelden' }}
          </div>

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
            <v-expand-transition>
              <div v-if="isRegisterMode">
                <v-text-field
                  v-model="displayName"
                  label="Anzeigename"
                  prepend-inner-icon="mdi-card-account-details-outline"
                  variant="outlined"
                  density="comfortable"
                  autocomplete="name"
                  :disabled="loading"
                  hide-details="auto"
                  class="mb-4 login-rise login-rise--4"
                />
                <v-text-field
                  v-model="email"
                  label="E-Mail (optional)"
                  prepend-inner-icon="mdi-email-outline"
                  variant="outlined"
                  density="comfortable"
                  autocomplete="email"
                  :disabled="loading"
                  hide-details="auto"
                  class="mb-4 login-rise login-rise--4"
                />
              </div>
            </v-expand-transition>
            <v-text-field
              ref="passwordField"
              v-model="password"
              label="Passwort"
              prepend-inner-icon="mdi-lock-outline"
              :type="showPassword ? 'text' : 'password'"
              :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
              variant="outlined"
              density="comfortable"
              :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
              :disabled="loading"
              hide-details="auto"
              :class="isRegisterMode ? 'mb-4 login-rise login-rise--5' : 'mb-2 login-rise login-rise--5'"
              @click:append-inner="showPassword = !showPassword"
            />
            <v-expand-transition>
              <v-text-field
                v-if="isRegisterMode"
                v-model="passwordConfirm"
                label="Passwort wiederholen"
                prepend-inner-icon="mdi-lock-check-outline"
                :type="showPassword ? 'text' : 'password'"
                variant="outlined"
                density="comfortable"
                autocomplete="new-password"
                :disabled="loading"
                hide-details="auto"
                class="mb-2 login-rise login-rise--5"
              />
            </v-expand-transition>

            <v-expand-transition>
              <v-alert
                v-if="error"
                type="error"
                variant="tonal"
                density="compact"
                icon="mdi-alert-circle-outline"
                :title="error.title"
                :text="error.text"
                class="mb-3 login-alert"
                role="alert"
                aria-live="assertive"
              />
            </v-expand-transition>

            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              class="login-rise login-rise--6"
              :loading="loading"
              :disabled="!canSubmit"
            >
              {{ isRegisterMode ? 'Registrieren' : 'Anmelden' }}
            </v-btn>

            <v-btn
              type="button"
              variant="text"
              color="primary"
              block
              class="mt-2 login-rise login-rise--6"
              :disabled="loading"
              @click="toggleMode"
            >
              {{ isRegisterMode ? 'Schon ein Konto? Anmelden' : 'Neues Konto erstellen' }}
            </v-btn>
          </v-form>
        </v-card>
      </div>
    </v-main>
  </v-app>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '../stores/auth.js';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const username = ref('');
const displayName = ref('');
const email = ref('');
const password = ref('');
const passwordConfirm = ref('');
const showPassword = ref(false);
const loading = ref(false);
const isRegisterMode = ref(false);
/** Fehler als { title, text } oder null. */
const error = ref(null);
const passwordField = ref(null);
const canSubmit = computed(() => {
  if (!username.value.trim() || !password.value) return false;
  if (!isRegisterMode.value) return true;
  return password.value.length >= 8 && passwordConfirm.value.length >= 8;
});

// Fehler verschwindet, sobald der Nutzer die Eingabe korrigiert.
watch([username, displayName, email, password, passwordConfirm, isRegisterMode], () => {
  if (error.value) error.value = null;
});

/**
 * Übersetzt einen Login-Fehler in eine freundliche, deutsche, handlungs-
 * leitende Meldung. Der Text wird hier im Frontend bestimmt – die (englischen)
 * Backend-Texte werden bewusst nicht durchgereicht.
 */
function mapLoginError(err) {
  const status = err?.status;
  const code = err?.code;
  const raw = String(err?.message || '').toLowerCase();
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;

  if (status === 401) {
    return {
      title: 'Anmeldung fehlgeschlagen',
      text: 'Benutzername oder Passwort ist falsch.',
      focusPassword: true,
    };
  }
  if (status === 429) {
    return {
      title: 'Zu viele Versuche',
      text: 'Aus Sicherheitsgründen pausiert. Bitte warte ein paar Minuten und versuche es erneut.',
    };
  }
  if (code === 'REQUEST_TIMEOUT') {
    return {
      title: 'Server antwortet nicht',
      text: 'Die Anmeldung dauert ungewöhnlich lange. Bitte versuche es gleich erneut.',
    };
  }
  if (
    offline ||
    err instanceof TypeError ||
    raw.includes('failed to fetch') ||
    raw.includes('load failed') ||
    raw.includes('networkerror')
  ) {
    return {
      title: 'Keine Verbindung',
      text: 'Prüfe deine Internetverbindung und versuche es erneut.',
    };
  }
  if (typeof status === 'number' && status >= 500) {
    return {
      title: 'Serverfehler',
      text: 'Auf dem Server ist etwas schiefgelaufen. Bitte versuche es später erneut.',
    };
  }
  return {
    title: 'Anmeldung fehlgeschlagen',
    text: 'Es ist ein unerwarteter Fehler aufgetreten. Bitte versuche es erneut.',
  };
}

function mapRegisterError(err) {
  const status = err?.status;
  const raw = String(err?.message || '').toLowerCase();

  if (status === 409) {
    if (raw.includes('e-mail')) {
      return {
        title: 'E-Mail bereits vergeben',
        text: 'Diese E-Mail-Adresse ist schon registriert.',
      };
    }
    return {
      title: 'Benutzername bereits vergeben',
      text: 'Bitte wähle einen anderen Benutzernamen.',
    };
  }
  if (status === 400 || status === 422) {
    return {
      title: 'Registrierung nicht möglich',
      text: 'Bitte prüfe Benutzername, E-Mail und Passwort.',
    };
  }
  if (status === 429) {
    return {
      title: 'Zu viele Versuche',
      text: 'Aus Sicherheitsgründen pausiert. Bitte warte ein paar Minuten und versuche es erneut.',
    };
  }
  return mapLoginError(err);
}

function toggleMode() {
  isRegisterMode.value = !isRegisterMode.value;
  password.value = '';
  passwordConfirm.value = '';
  error.value = null;
}

async function submit() {
  if (!canSubmit.value || loading.value) return;
  if (isRegisterMode.value && password.value !== passwordConfirm.value) {
    error.value = {
      title: 'Passwörter stimmen nicht überein',
      text: 'Bitte gib zweimal dasselbe Passwort ein.',
    };
    await nextTick();
    passwordField.value?.focus?.();
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    if (isRegisterMode.value) {
      await authStore.register({
        username: username.value.trim(),
        password: password.value,
        display_name: displayName.value.trim() || null,
        email: email.value.trim() || null,
      });
    } else {
      await authStore.login(username.value.trim(), password.value);
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/';
    router.push(redirect);
  } catch (err) {
    const mapped = isRegisterMode.value ? mapRegisterError(err) : mapLoginError(err);
    error.value = { title: mapped.title, text: mapped.text };
    // Erst die Sperre lösen, dann fokussieren – ein disabled-Feld nimmt keinen
    // Fokus an.
    loading.value = false;
    if (mapped.focusPassword) {
      await nextTick();
      passwordField.value?.focus?.();
    }
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
    radial-gradient(circle at 18% 22%, rgba(34, 211, 238, 0.34) 0 12%, transparent 36%),
    radial-gradient(circle at 72% 34%, rgba(8, 145, 178, 0.30) 0 10%, transparent 33%),
    radial-gradient(circle at 40% 78%, rgba(13, 148, 136, 0.30) 0 11%, transparent 35%),
    radial-gradient(circle at 86% 76%, rgba(59, 130, 246, 0.22) 0 9%, transparent 30%);
  opacity: 0.95;
  animation: login-aurora-drift 14s ease-in-out infinite;
  will-change: transform;
}

.login-main::after {
  inset: -18%;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(255, 255, 255, 0.06), transparent 34%),
    radial-gradient(ellipse at 72% 82%, rgba(34, 211, 238, 0.14), transparent 42%);
  opacity: 0.72;
  animation: login-sheen-drift 18s ease-in-out infinite alternate;
  will-change: transform;
}

/* Weiche Farb-Auren ohne Blur-Kacheln: Radials laufen gross ueber den Viewport,
   damit keine rechteckigen Compositing-Artefakte sichtbar werden. */
.login-glow {
  position: absolute;
  inset: -42%;
  border-radius: 0;
  opacity: 0.5;
  z-index: 0;
  pointer-events: none;
  background-repeat: no-repeat;
  background-size: 100% 100%;
  will-change: transform, opacity;
}

.login-glow--one {
  background: radial-gradient(circle at 12% 18%, rgba(8, 145, 178, 0.5) 0%, transparent 44%);
  animation: drift-one 11s ease-in-out infinite alternate;
}

.login-glow--two {
  background: radial-gradient(circle at 88% 86%, rgba(34, 211, 238, 0.44) 0%, transparent 42%);
  animation: drift-two 13s ease-in-out infinite alternate;
}

.login-glow--three {
  opacity: 0.44;
  background: radial-gradient(circle at 46% 56%, rgba(13, 148, 136, 0.42) 0%, transparent 40%);
  animation: drift-three 16s ease-in-out infinite alternate;
}

.login-glow--four {
  opacity: 0.4;
  background: radial-gradient(circle at 78% 16%, rgba(59, 130, 246, 0.36) 0%, transparent 40%);
  animation: drift-four 12s ease-in-out infinite alternate;
}

.login-glow--five {
  opacity: 0.36;
  background: radial-gradient(circle at 22% 88%, rgba(45, 212, 191, 0.36) 0%, transparent 42%);
  animation: drift-five 14s ease-in-out infinite alternate;
}

/* Hintergrund-Auren bewegen sich jetzt frei (kein Cursor-Einfluss mehr) ueber
   einen geschlossenen Pfad, mit kraeftigeren Wegen und mehr Rotation. */
@keyframes login-aurora-drift {
  0% {
    transform: translate3d(-7%, -5%, 0) rotate(0deg) scale(1.06);
  }
  33% {
    transform: translate3d(9%, 7%, 0) rotate(14deg) scale(1.22);
  }
  66% {
    transform: translate3d(-5%, 10%, 0) rotate(-10deg) scale(1.14);
  }
  100% {
    transform: translate3d(-7%, -5%, 0) rotate(0deg) scale(1.06);
  }
}

@keyframes login-sheen-drift {
  0% {
    transform: translate3d(7%, -7%, 0) rotate(-12deg) scale(1.04);
  }
  100% {
    transform: translate3d(-9%, 9%, 0) rotate(12deg) scale(1.16);
  }
}

@keyframes drift-one {
  0% {
    transform: translate3d(-10vw, -8vh, 0) scale(1) rotate(0deg);
  }
  100% {
    transform: translate3d(26vw, 18vh, 0) scale(1.4) rotate(14deg);
  }
}

@keyframes drift-two {
  0% {
    transform: translate3d(11vw, 9vh, 0) scale(1.06) rotate(0deg);
  }
  100% {
    transform: translate3d(-24vw, -22vh, 0) scale(1.46) rotate(-15deg);
  }
}

@keyframes drift-three {
  0% {
    transform: translate3d(-12vw, 8vh, 0) scale(1) rotate(0deg);
    opacity: 0.3;
  }
  100% {
    transform: translate3d(20vw, -18vh, 0) scale(1.42) rotate(12deg);
    opacity: 0.55;
  }
}

@keyframes drift-four {
  0% {
    transform: translate3d(12vw, -9vh, 0) scale(1.02) rotate(0deg);
    opacity: 0.26;
  }
  100% {
    transform: translate3d(-22vw, 20vh, 0) scale(1.38) rotate(-13deg);
    opacity: 0.5;
  }
}

@keyframes drift-five {
  0% {
    transform: translate3d(-11vw, -11vh, 0) scale(1) rotate(0deg);
    opacity: 0.22;
  }
  100% {
    transform: translate3d(24vw, 16vh, 0) scale(1.36) rotate(14deg);
    opacity: 0.5;
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
  max-width: 420px;
  padding: 36px 32px 32px;
  /* Glassmorphism — staerkerer Blur + hoehere Saettigung fuer kraeftigeres Glas. */
  background: rgba(14, 20, 32, 0.5) !important;
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.12),
    inset 0 0 0 1px rgba(255, 255, 255, 0.04);
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
   sofort sichtbar. */
@media (prefers-reduced-motion: reduce) {
  .login-main::before,
  .login-main::after,
  .login-glow,
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
