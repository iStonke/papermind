<template>
  <v-dialog
    :model-value="modelValue"
    class="pm-onboarding-overlay"
    width="min(960px, calc(100vw - 32px))"
    transition="pm-onboarding-dialog"
    @update:model-value="handleDialogUpdate"
    @keydown.left="previousStep"
    @keydown.right="nextStep"
  >
    <div class="onboarding-window" role="document" aria-labelledby="onboarding-title">
      <header class="onboarding-header">
        <div class="onboarding-brand" aria-label="PaperMind">
          <span class="onboarding-brand__mark"><v-icon size="18">mdi-brain</v-icon></span>
          <span>PaperMind</span>
        </div>
        <span class="onboarding-step-label">Willkommen</span>
        <v-btn
          icon="mdi-close"
          size="small"
          variant="text"
          aria-label="Onboarding überspringen"
          @click="dismiss"
        />
      </header>

      <main class="onboarding-main">
        <section class="onboarding-stage" :data-step="currentStep" aria-hidden="true">
          <div class="stage-aurora stage-aurora--one" />
          <div class="stage-aurora stage-aurora--two" />
          <div class="stage-grid" />

          <Transition name="onboarding-scene" mode="out-in">
            <div :key="currentStep" class="onboarding-scene">
              <div v-if="currentStep === 0" class="scene-welcome">
                <div class="orbit orbit--outer"><span class="orbit__dot" /></div>
                <div class="orbit orbit--inner"><span class="orbit__dot" /></div>
                <div class="paper paper--one"><span /><span /><span /></div>
                <div class="paper paper--two"><span /><span /><span /></div>
                <div class="paper paper--three"><span /><span /><span /></div>
                <div class="mind-core">
                  <span class="mind-core__halo" />
                  <v-icon size="42">mdi-brain</v-icon>
                </div>
              </div>

              <div v-else-if="currentStep === 1" class="scene-scan">
                <div class="scan-machine">
                  <div class="scan-machine__top"><span /><span /><span /></div>
                  <div class="scan-paper">
                    <div class="scan-paper__title" />
                    <div class="scan-paper__line scan-paper__line--long" />
                    <div class="scan-paper__line" />
                    <div class="scan-paper__line scan-paper__line--short" />
                    <div class="scan-paper__seal">P</div>
                    <div class="scan-beam" />
                  </div>
                </div>
                <div class="metadata-chip metadata-chip--sender"><span>Absender</span> Stadtwerke</div>
                <div class="metadata-chip metadata-chip--date"><span>Datum</span> 18. Juli</div>
                <div class="metadata-chip metadata-chip--type"><span>Typ</span> Rechnung</div>
              </div>

              <div v-else-if="currentStep === 2" class="scene-knowledge">
                <svg class="knowledge-lines" viewBox="0 0 480 340" preserveAspectRatio="none">
                  <path d="M240 170 L105 88 M240 170 L374 76 M240 170 L390 245 M240 170 L105 258" />
                  <path class="knowledge-lines__pulse" d="M105 88 L240 170 L390 245" />
                </svg>
                <div class="knowledge-node knowledge-node--center"><v-icon size="32">mdi-brain</v-icon></div>
                <div class="knowledge-node knowledge-node--a"><v-icon size="22">mdi-file-document-outline</v-icon></div>
                <div class="knowledge-node knowledge-node--b"><v-icon size="22">mdi-domain</v-icon></div>
                <div class="knowledge-node knowledge-node--c"><v-icon size="22">mdi-tag-outline</v-icon></div>
                <div class="knowledge-node knowledge-node--d"><v-icon size="22">mdi-calendar-outline</v-icon></div>
              </div>

              <div v-else class="scene-ready">
                <div class="mini-app">
                  <aside class="mini-app__sidebar">
                    <div class="mini-app__mini-logo">P</div>
                    <span class="mini-app__nav mini-app__nav--active" />
                    <span class="mini-app__nav" />
                    <span class="mini-app__nav mini-app__nav--short" />
                  </aside>
                  <div class="mini-app__content">
                    <div class="mini-app__toolbar"><span /><span /></div>
                    <div class="mini-app__welcome">Dein Archiv wartet.</div>
                    <div class="mini-app__dropzone">
                      <span class="mini-app__drop-icon"><v-icon size="28">mdi-tray-arrow-down</v-icon></span>
                      <strong>Erstes Dokument</strong>
                      <small>PDF ablegen oder Scanner verwenden</small>
                    </div>
                  </div>
                </div>
                <span class="ready-spark ready-spark--one" />
                <span class="ready-spark ready-spark--two" />
                <span class="ready-spark ready-spark--three" />
              </div>
            </div>
          </Transition>
        </section>

        <section class="onboarding-copy" aria-live="polite">
          <Transition name="onboarding-copy" mode="out-in">
            <div :key="currentStep" class="onboarding-copy__inner">
              <p class="onboarding-eyebrow">{{ steps[currentStep].eyebrow }}</p>
              <h1 id="onboarding-title">{{ resolvedTitle }}</h1>
              <p class="onboarding-description">{{ steps[currentStep].description }}</p>
              <div class="onboarding-highlight">
                <span class="onboarding-highlight__icon"><v-icon size="17">mdi-check</v-icon></span>
                <span>{{ steps[currentStep].highlight }}</span>
              </div>
            </div>
          </Transition>
        </section>
      </main>

      <footer class="onboarding-footer">
        <div class="onboarding-progress" role="tablist" aria-label="Onboarding-Schritte">
          <button
            v-for="(_, index) in steps"
            :key="index"
            type="button"
            class="onboarding-progress__dot"
            :class="{ 'onboarding-progress__dot--active': index === currentStep }"
            :aria-label="`Schritt ${index + 1} anzeigen`"
            :aria-selected="index === currentStep"
            role="tab"
            @click="currentStep = index"
          />
        </div>
        <div class="onboarding-actions">
          <v-btn v-if="currentStep > 0" variant="text" class="onboarding-back" @click="previousStep">
            Zurück
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            class="onboarding-next"
            append-icon="mdi-chevron-right"
            @click="nextStep"
          >
            {{ currentStep === steps.length - 1 ? 'Erstes Dokument importieren' : 'Weiter' }}
          </v-btn>
        </div>
      </footer>
    </div>
  </v-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  userName: { type: String, default: '' },
});

const emit = defineEmits(['update:modelValue', 'dismiss', 'finish']);

const currentStep = ref(0);
const steps = Object.freeze([
  {
    eyebrow: 'Willkommen',
    title: 'Schön, dass du da bist.',
    description: 'PaperMind verwandelt deinen Papierkram in ein ruhiges, intelligentes Archiv – übersichtlich, durchsuchbar und ganz bei dir.',
    highlight: 'Deine Dokumente bleiben unter deiner Kontrolle.',
  },
  {
    eyebrow: 'Automatisch verstanden',
    title: 'Ablegen. Den Rest übernimmt PaperMind.',
    description: 'Aus PDFs und Scans werden sauber benannte Dokumente. Datum, Absender, Dokumenttyp und Tags erscheinen wie von selbst.',
    highlight: 'Weniger sortieren, schneller wiederfinden.',
  },
  {
    eyebrow: 'Wissen statt Ablage',
    title: 'Frag dein Archiv.',
    description: 'Suche nicht nur nach Dateinamen. PaperMind erkennt Zusammenhänge und findet die entscheidende Stelle in deinen Unterlagen.',
    highlight: 'Antworten führen direkt zurück zur Quelle.',
  },
  {
    eyebrow: 'Alles bereit',
    title: 'Dein erstes Dokument wartet.',
    description: 'Starte mit einer PDF oder nutze deinen Scanner. PaperMind begleitet das Dokument vom Eingang bis ins fertige Archiv.',
    highlight: 'Du kannst diese Einführung jederzeit überspringen.',
  },
]);

const resolvedTitle = computed(() => {
  if (currentStep.value !== 0 || !props.userName) return steps[currentStep.value].title;
  return `Schön, dass du da bist, ${props.userName}.`;
});

function dismiss() {
  emit('update:modelValue', false);
  emit('dismiss');
}

function handleDialogUpdate(value) {
  if (value) {
    emit('update:modelValue', true);
    return;
  }
  dismiss();
}

function previousStep() {
  if (currentStep.value > 0) currentStep.value -= 1;
}

function nextStep() {
  if (currentStep.value < steps.length - 1) {
    currentStep.value += 1;
    return;
  }
  emit('update:modelValue', false);
  emit('finish');
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) currentStep.value = 0;
  },
);
</script>

<style scoped>
.onboarding-window {
  --ob-accent: rgb(var(--v-theme-primary));
  --ob-accent-soft: rgba(var(--v-theme-primary), 0.16);
  width: 100%;
  min-height: 590px;
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-primary), 0.22);
  border-radius: 26px;
  color: rgb(var(--v-theme-on-surface));
  background: rgb(var(--v-theme-surface-2));
  box-shadow:
    0 34px 90px rgba(0, 0, 0, 0.34),
    0 0 0 1px rgba(var(--v-theme-on-surface), 0.04),
    0 0 70px rgba(var(--v-theme-primary), 0.10);
}

.onboarding-header {
  min-height: 68px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 20px 0 24px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.onboarding-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 0.94rem;
  font-weight: 750;
  letter-spacing: 0.01em;
}

.onboarding-brand__mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: rgb(var(--v-theme-on-primary));
  background: var(--ob-accent);
  box-shadow: 0 8px 20px rgba(var(--v-theme-primary), 0.28);
}

.onboarding-step-label {
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 0.75rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.onboarding-header :deep(.v-btn) {
  justify-self: end;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.onboarding-main {
  min-height: 430px;
  display: grid;
  grid-template-columns: minmax(0, 1.14fr) minmax(320px, 0.86fr);
}

.onboarding-stage {
  position: relative;
  min-width: 0;
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(circle at 28% 24%, rgba(var(--v-theme-primary), 0.22), transparent 34%),
    linear-gradient(145deg, rgb(var(--v-theme-panel-left)) 0%, rgb(var(--v-theme-panel-right)) 100%);
}

.stage-grid {
  position: absolute;
  inset: 0;
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(var(--v-theme-primary), 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(var(--v-theme-primary), 0.16) 1px, transparent 1px);
  background-size: 38px 38px;
  mask-image: linear-gradient(to bottom right, black, transparent 78%);
}

.stage-aurora {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  filter: blur(75px);
  opacity: 0.28;
  background: var(--ob-accent);
  animation: aurora-float 8s ease-in-out infinite alternate;
}

.stage-aurora--one { left: -150px; top: -120px; }
.stage-aurora--two { right: -170px; bottom: -180px; animation-direction: alternate-reverse; }

.onboarding-scene {
  position: absolute;
  inset: 0;
}

.onboarding-copy {
  position: relative;
  display: flex;
  align-items: center;
  padding: 50px 50px 44px;
  overflow: hidden;
}

.onboarding-copy::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(circle at 100% 0%, rgba(var(--v-theme-primary), 0.08), transparent 42%);
}

.onboarding-copy__inner { position: relative; width: 100%; }

.onboarding-eyebrow {
  margin: 0 0 13px;
  color: var(--ob-accent);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.onboarding-copy h1 {
  max-width: 390px;
  margin: 0;
  font-size: clamp(2rem, 3.1vw, 2.85rem);
  font-weight: 740;
  line-height: 1.04;
  letter-spacing: -0.045em;
  text-wrap: balance;
}

.onboarding-description {
  max-width: 390px;
  margin: 24px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 1rem;
  line-height: 1.7;
}

.onboarding-highlight {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-top: 25px;
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 0.86rem;
  font-weight: 650;
}

.onboarding-highlight__icon {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: var(--ob-accent);
  background: var(--ob-accent-soft);
}

.onboarding-footer {
  min-height: 84px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 24px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.onboarding-progress { display: flex; align-items: center; gap: 7px; }

.onboarding-progress__dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  cursor: pointer;
  background: rgba(var(--v-theme-on-surface), 0.18);
  transition: width 260ms ease, background-color 260ms ease;
}

.onboarding-progress__dot--active { width: 28px; background: var(--ob-accent); }
.onboarding-actions { display: flex; align-items: center; gap: 8px; }
.onboarding-back { color: rgba(var(--v-theme-on-surface), 0.66); }

.onboarding-next {
  min-width: 112px;
  min-height: 44px;
  border-radius: 13px;
  padding-inline: 20px;
  font-weight: 720;
  letter-spacing: 0;
  box-shadow: 0 10px 24px rgba(var(--v-theme-primary), 0.24);
}

/* Szene 1: schwebendes Papier um den PaperMind-Kern */
.scene-welcome { position: absolute; inset: 0; }
.mind-core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 102px;
  height: 102px;
  display: grid;
  place-items: center;
  border-radius: 30px;
  color: rgb(var(--v-theme-on-primary));
  background: linear-gradient(145deg, rgba(var(--v-theme-primary), 0.96), rgba(var(--v-theme-primary), 0.62));
  box-shadow: 0 26px 58px rgba(var(--v-theme-primary), 0.36);
  transform: translate(-50%, -50%);
  animation: core-breathe 4s ease-in-out infinite;
}
.mind-core__halo { position: absolute; inset: -18px; border: 1px solid rgba(var(--v-theme-primary), 0.38); border-radius: 39px; animation: halo-pulse 2.8s ease-out infinite; }
.orbit { position: absolute; left: 50%; top: 50%; border: 1px solid rgba(var(--v-theme-primary), 0.22); border-radius: 50%; animation: orbit-spin 15s linear infinite; }
.orbit--outer { width: 330px; height: 330px; margin: -165px; }
.orbit--inner { width: 230px; height: 230px; margin: -115px; animation-direction: reverse; animation-duration: 11s; }
.orbit__dot { position: absolute; left: 50%; top: -4px; width: 8px; height: 8px; border-radius: 50%; background: var(--ob-accent); box-shadow: 0 0 16px var(--ob-accent); }
.paper { position: absolute; width: 76px; height: 98px; padding: 18px 13px; border-radius: 7px; background: rgba(255, 255, 255, 0.92); box-shadow: 0 16px 36px rgba(0, 0, 0, 0.26); }
.paper span { display: block; height: 4px; margin-bottom: 8px; border-radius: 4px; background: rgba(var(--v-theme-primary), 0.24); }
.paper span:nth-child(2) { width: 72%; }
.paper span:nth-child(3) { width: 84%; }
.paper--one { left: 11%; top: 19%; transform: rotate(-12deg); animation: paper-float-one 5.8s ease-in-out infinite; }
.paper--two { right: 10%; top: 27%; transform: rotate(9deg) scale(0.86); animation: paper-float-two 6.4s ease-in-out infinite; }
.paper--three { left: 18%; bottom: 11%; transform: rotate(7deg) scale(0.7); animation: paper-float-three 5.2s ease-in-out infinite; }

/* Szene 2: Scan und einrastende Metadaten */
.scene-scan { position: absolute; inset: 0; }
.scan-machine { position: absolute; left: 50%; top: 47%; width: 230px; height: 255px; transform: translate(-50%, -50%); }
.scan-machine__top { position: absolute; inset: 0 0 auto; height: 45px; display: flex; align-items: center; gap: 7px; padding: 0 16px; border-radius: 18px 18px 8px 8px; border: 1px solid rgba(var(--v-theme-primary), 0.26); background: rgba(var(--v-theme-on-surface), 0.09); box-shadow: 0 14px 40px rgba(0, 0, 0, 0.22); }
.scan-machine__top span { width: 7px; height: 7px; border-radius: 50%; background: rgba(var(--v-theme-on-surface), 0.22); }
.scan-machine__top span:first-child { background: var(--ob-accent); box-shadow: 0 0 12px var(--ob-accent); }
.scan-paper { position: absolute; left: 27px; right: 27px; top: 38px; height: 218px; padding: 42px 22px 20px; overflow: hidden; border-radius: 5px 5px 12px 12px; background: rgba(255, 255, 255, 0.95); box-shadow: 0 20px 48px rgba(0, 0, 0, 0.3); animation: document-feed 4.2s ease-in-out infinite; }
.scan-paper__title { width: 46%; height: 9px; margin-bottom: 23px; border-radius: 6px; background: rgba(var(--v-theme-primary), 0.42); }
.scan-paper__line { width: 78%; height: 5px; margin-bottom: 10px; border-radius: 5px; background: rgba(24, 38, 43, 0.16); }
.scan-paper__line--long { width: 100%; }
.scan-paper__line--short { width: 56%; }
.scan-paper__seal { position: absolute; right: 20px; bottom: 22px; width: 34px; height: 34px; display: grid; place-items: center; border: 2px solid rgba(var(--v-theme-primary), 0.38); border-radius: 50%; color: rgba(var(--v-theme-primary), 0.64); font-weight: 800; }
.scan-beam { position: absolute; left: 0; right: 0; top: 38px; height: 2px; background: var(--ob-accent); box-shadow: 0 0 8px 2px rgba(var(--v-theme-primary), 0.72), 0 0 30px 8px rgba(var(--v-theme-primary), 0.34); animation: scan-sweep 3.2s ease-in-out infinite; }
.metadata-chip { position: absolute; display: grid; gap: 2px; min-width: 104px; padding: 10px 13px; border: 1px solid rgba(var(--v-theme-primary), 0.26); border-radius: 12px; color: rgba(255, 255, 255, 0.9); background: rgba(20, 38, 44, 0.84); box-shadow: 0 14px 32px rgba(0, 0, 0, 0.24); backdrop-filter: blur(10px); font-size: 0.78rem; font-weight: 670; animation: chip-arrive 3.2s ease-in-out infinite both; }
.metadata-chip span { color: rgba(255, 255, 255, 0.48); font-size: 0.62rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.metadata-chip--sender { left: 7%; top: 18%; animation-delay: 0.2s; }
.metadata-chip--date { right: 5%; top: 30%; animation-delay: 0.55s; }
.metadata-chip--type { left: 9%; bottom: 11%; animation-delay: 0.9s; }

/* Szene 3: Wissensnetz */
.scene-knowledge { position: absolute; inset: 0; }
.knowledge-lines { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.knowledge-lines path { fill: none; stroke: rgba(var(--v-theme-primary), 0.28); stroke-width: 1.4; stroke-dasharray: 4 6; }
.knowledge-lines__pulse { stroke: var(--ob-accent) !important; stroke-width: 2 !important; stroke-dasharray: 44 320 !important; filter: drop-shadow(0 0 6px var(--ob-accent)); animation: line-flow 3.4s linear infinite; }
.knowledge-node { position: absolute; width: 54px; height: 54px; display: grid; place-items: center; border: 1px solid rgba(var(--v-theme-primary), 0.28); border-radius: 18px; color: var(--ob-accent); background: rgba(20, 38, 44, 0.86); box-shadow: 0 14px 32px rgba(0, 0, 0, 0.24); animation: node-float 4s ease-in-out infinite; }
.knowledge-node--center { left: 50%; top: 42%; width: 76px; height: 76px; border-radius: 24px; color: rgb(var(--v-theme-on-primary)); background: var(--ob-accent); transform: translate(-50%, -50%); box-shadow: 0 18px 46px rgba(var(--v-theme-primary), 0.34); }
.knowledge-node--a { left: 12%; top: 12%; }
.knowledge-node--b { right: 10%; top: 9%; animation-delay: -0.8s; }
.knowledge-node--c { right: 7%; bottom: 17%; animation-delay: -1.6s; }
.knowledge-node--d { left: 12%; bottom: 13%; animation-delay: -2.4s; }

/* Szene 4: kleine Vorschau der echten App */
.scene-ready { position: absolute; inset: 0; display: grid; place-items: center; }
.mini-app { width: 82%; height: 72%; display: grid; grid-template-columns: 82px 1fr; overflow: hidden; border: 1px solid rgba(var(--v-theme-primary), 0.28); border-radius: 18px; background: rgb(var(--v-theme-panel-mid)); box-shadow: 0 28px 64px rgba(0, 0, 0, 0.34); animation: mini-app-arrive 0.75s cubic-bezier(0.22, 1, 0.36, 1) both; }
.mini-app__sidebar { display: flex; flex-direction: column; align-items: center; gap: 15px; padding: 17px 10px; background: rgb(var(--v-theme-panel-left)); }
.mini-app__mini-logo { width: 30px; height: 30px; display: grid; place-items: center; margin-bottom: 14px; border-radius: 9px; color: rgb(var(--v-theme-on-primary)); background: var(--ob-accent); font-size: 0.75rem; font-weight: 850; }
.mini-app__nav { width: 47px; height: 7px; border-radius: 5px; background: rgba(255, 255, 255, 0.16); }
.mini-app__nav--active { height: 24px; background: rgba(var(--v-theme-primary), 0.34); }
.mini-app__nav--short { width: 33px; }
.mini-app__content { position: relative; padding: 18px; background: rgb(var(--v-theme-panel-mid)); }
.mini-app__toolbar { height: 23px; display: flex; justify-content: space-between; }
.mini-app__toolbar span { width: 76px; height: 7px; border-radius: 5px; background: rgba(var(--v-theme-on-surface), 0.13); }
.mini-app__toolbar span:last-child { width: 28px; }
.mini-app__welcome { margin: 17px 0 16px; color: rgba(var(--v-theme-on-surface), 0.76); font-size: 0.8rem; font-weight: 720; }
.mini-app__dropzone { height: 145px; display: flex; flex-direction: column; align-items: center; justify-content: center; border: 1px dashed rgba(var(--v-theme-primary), 0.42); border-radius: 14px; color: rgba(var(--v-theme-on-surface), 0.74); background: rgba(var(--v-theme-primary), 0.08); }
.mini-app__drop-icon { width: 48px; height: 48px; display: grid; place-items: center; margin-bottom: 9px; border-radius: 15px; color: var(--ob-accent); background: var(--ob-accent-soft); animation: drop-pulse 2.6s ease-in-out infinite; }
.mini-app__dropzone strong { font-size: 0.76rem; }
.mini-app__dropzone small { margin-top: 4px; color: rgba(var(--v-theme-on-surface), 0.46); font-size: 0.58rem; }
.ready-spark { position: absolute; width: 5px; height: 5px; border-radius: 50%; background: var(--ob-accent); box-shadow: 0 0 12px var(--ob-accent); animation: spark 2.4s ease-in-out infinite; }
.ready-spark--one { left: 7%; top: 22%; }
.ready-spark--two { right: 8%; top: 17%; animation-delay: -0.8s; }
.ready-spark--three { right: 6%; bottom: 18%; animation-delay: -1.6s; }

.onboarding-scene-enter-active, .onboarding-scene-leave-active { transition: opacity 260ms ease, transform 340ms cubic-bezier(0.22, 1, 0.36, 1); }
.onboarding-scene-enter-from { opacity: 0; transform: translateX(18px) scale(0.98); }
.onboarding-scene-leave-to { opacity: 0; transform: translateX(-14px) scale(0.98); }
.onboarding-copy-enter-active, .onboarding-copy-leave-active { transition: opacity 220ms ease, transform 320ms cubic-bezier(0.22, 1, 0.36, 1); }
.onboarding-copy-enter-from { opacity: 0; transform: translateY(10px); }
.onboarding-copy-leave-to { opacity: 0; transform: translateY(-7px); }

@keyframes aurora-float { to { transform: translate(80px, 48px) scale(1.18); } }
@keyframes core-breathe { 0%, 100% { transform: translate(-50%, -50%) scale(1); } 50% { transform: translate(-50%, -53%) scale(1.04); } }
@keyframes halo-pulse { 0% { opacity: 0.7; transform: scale(0.88); } 80%, 100% { opacity: 0; transform: scale(1.3); } }
@keyframes orbit-spin { to { transform: rotate(360deg); } }
@keyframes paper-float-one { 0%, 100% { transform: translateY(0) rotate(-12deg); } 50% { transform: translateY(-12px) rotate(-8deg); } }
@keyframes paper-float-two { 0%, 100% { transform: translateY(0) rotate(9deg) scale(0.86); } 50% { transform: translateY(13px) rotate(5deg) scale(0.86); } }
@keyframes paper-float-three { 0%, 100% { transform: translateY(0) rotate(7deg) scale(0.7); } 50% { transform: translateY(-9px) rotate(11deg) scale(0.7); } }
@keyframes document-feed { 0%, 100% { transform: translateY(-3px); } 50% { transform: translateY(8px); } }
@keyframes scan-sweep { 0%, 12% { transform: translateY(0); opacity: 0; } 22% { opacity: 1; } 72% { transform: translateY(152px); opacity: 1; } 88%, 100% { transform: translateY(152px); opacity: 0; } }
@keyframes chip-arrive { 0%, 18% { opacity: 0; transform: translateY(8px) scale(0.94); } 34%, 82% { opacity: 1; transform: none; } 100% { opacity: 0; transform: translateY(-4px); } }
@keyframes line-flow { to { stroke-dashoffset: -364; } }
@keyframes node-float { 0%, 100% { translate: 0 0; } 50% { translate: 0 -6px; } }
@keyframes mini-app-arrive { from { opacity: 0; transform: translateY(18px) scale(0.94); } }
@keyframes drop-pulse { 50% { transform: translateY(-4px); box-shadow: 0 10px 24px rgba(var(--v-theme-primary), 0.16); } }
@keyframes spark { 50% { opacity: 0.28; transform: scale(2); } }

@media (max-width: 780px) {
  .onboarding-window { min-height: min(760px, calc(100dvh - 28px)); max-height: calc(100dvh - 28px); }
  .onboarding-main { min-height: 0; grid-template-columns: 1fr; grid-template-rows: minmax(245px, 0.9fr) minmax(255px, 1fr); overflow: auto; }
  .onboarding-copy { align-items: flex-start; padding: 32px 34px; }
  .onboarding-copy h1 { font-size: clamp(1.8rem, 7vw, 2.45rem); }
  .onboarding-description { margin-top: 16px; line-height: 1.55; }
  .onboarding-highlight { margin-top: 18px; }
  .metadata-chip--sender { left: 4%; }
  .metadata-chip--date { right: 4%; }
}

@media (max-width: 520px) {
  .onboarding-header { min-height: 58px; padding-inline: 14px 10px; }
  .onboarding-brand { font-size: 0.86rem; }
  .onboarding-brand__mark { width: 30px; height: 30px; }
  .onboarding-step-label { display: none; }
  .onboarding-header { grid-template-columns: 1fr auto; }
  .onboarding-main { grid-template-rows: 230px minmax(270px, 1fr); }
  .onboarding-copy { padding: 27px 25px 30px; }
  .onboarding-copy h1 { font-size: 1.8rem; }
  .onboarding-description { font-size: 0.92rem; }
  .onboarding-footer { min-height: 76px; padding-inline: 16px; }
  .onboarding-back { display: none; }
  .onboarding-next { padding-inline: 14px; }
  .metadata-chip { min-width: 90px; padding: 7px 9px; font-size: 0.67rem; }
  .metadata-chip--sender { top: 8%; }
  .metadata-chip--date { top: 20%; }
  .metadata-chip--type { bottom: 7%; }
}

@media (prefers-reduced-motion: reduce) {
  .onboarding-window *,
  .onboarding-window *::before,
  .onboarding-window *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
  .onboarding-scene-enter-active,
  .onboarding-scene-leave-active,
  .onboarding-copy-enter-active,
  .onboarding-copy-leave-active {
    transition-duration: 0.001ms !important;
  }
}
</style>
