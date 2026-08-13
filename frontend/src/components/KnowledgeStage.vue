<template>
  <div ref="rootRef" class="kstage" :class="{ 'kstage--still': reducedMotion }">
    <canvas ref="canvasRef" class="kstage__canvas" aria-hidden="true"></canvas>
    <div class="kstage__vignette" aria-hidden="true"></div>

    <div class="kstage__content">
      <div class="kstage__intro">
        <div class="kstage__eyebrow">Wissensbasis</div>
      </div>

      <button
        type="button"
        class="kstage__entry"
        :class="primaryAttention ? `kstage__entry--${primaryAttention.tone}` : 'kstage__entry--plain'"
        @click="$emit('open-knowledge', primaryAttention ? 'review' : null)"
      >
        <span v-if="primaryAttention" class="kstage__attn-dot"></span>
        <span v-else class="kstage__entry-ic" aria-hidden="true"><v-icon size="15">mdi-brain</v-icon></span>
        <strong>{{ primaryAttention ? `${primaryAttention.count} ${primaryAttention.label}` : 'Zur Wissensbasis' }}</strong>
        <span class="kstage__entry-hint">{{ primaryAttention ? primaryAttention.hint : 'Fakten, Belege &amp; Prüfung öffnen' }}</span>
        <v-icon size="15" class="kstage__entry-arrow">mdi-chevron-right</v-icon>
      </button>

      <div class="kstage__prompts">
        <button
          v-for="(prompt, index) in prompts"
          :key="prompt.key"
          type="button"
          class="kstage__prompt"
          :class="`kstage__prompt--${prompt.tone || 'aqua'}`"
          :style="{ '--i': index }"
          :title="prompt.prompt"
          @click="$emit('ask', prompt.prompt)"
        >
          <span class="kstage__prompt-shine" aria-hidden="true"></span>
          <span class="kstage__prompt-icon" aria-hidden="true"><v-icon size="20">{{ prompt.icon }}</v-icon></span>
          <span class="kstage__prompt-copy">
            <small>{{ prompt.eyebrow }}</small>
            <strong>{{ prompt.label }}</strong>
          </span>
          <v-icon class="kstage__prompt-arrow" size="16">mdi-arrow-top-right</v-icon>
        </button>
      </div>

      <button type="button" class="kstage__more" @click="$emit('refresh')">
        <v-icon size="15">mdi-shuffle-variant</v-icon>
        Andere Vorschläge
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps({
  knows: { type: Object, default: () => ({}) },
  prompts: { type: Array, default: () => [] },
  attention: { type: Array, default: () => [] },
});
defineEmits(['ask', 'open-knowledge', 'refresh']);

// Erster Aufmerksamkeits-Eintrag (z. B. „Zu prüfen") steuert die Beschriftung des
// persistenten Wissens-Einstiegs; ohne offene Prüfung wird er zu „Zur Wissensbasis".
const primaryAttention = computed(() => props.attention?.[0] || null);

const rootRef = ref(null);
const canvasRef = ref(null);
const reducedMotion = ref(false);

// ── Canvas: driftendes Wissens-Netz ────────────────────────────────────────────
let ctx = null;
let raf = 0;
let nodes = [];
let width = 0;
let height = 0;
let accent = '#0d9488';
let resizeObserver = null;
let themeObserver = null;
const MAX_DIST = 116;
const MAX_DIST_SQ = MAX_DIST * MAX_DIST;

function readAccent() {
  const value = getComputedStyle(document.documentElement).getPropertyValue('--pm-accent').trim();
  if (value) accent = value;
}

function seedNodes() {
  const area = Math.max(1, width * height);
  const count = Math.min(60, Math.max(26, Math.round(area / 14000)));
  const glowTarget = Math.min(9, Math.max(3, Math.round((props.knows?.active_claims || 4) / 2)));
  nodes = Array.from({ length: count }, (_, index) => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.16,
    vy: (Math.random() - 0.5) * 0.16,
    r: Math.random() * 1.5 + 0.7,
    glow: index < glowTarget,
    phase: Math.random() * Math.PI * 2,
  }));
}

function resize() {
  const canvas = canvasRef.value;
  const host = rootRef.value;
  if (!canvas || !host) return;
  const rect = host.getBoundingClientRect();
  width = rect.width;
  height = rect.height;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  seedNodes();
  if (reducedMotion.value) drawFrame(0);
}

function drawFrame(time) {
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);

  if (!reducedMotion.value) {
    for (const node of nodes) {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < -10) node.x = width + 10;
      else if (node.x > width + 10) node.x = -10;
      if (node.y < -10) node.y = height + 10;
      else if (node.y > height + 10) node.y = -10;
    }
  }

  // Verbindungslinien
  ctx.strokeStyle = accent;
  ctx.lineWidth = 1;
  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const dx = nodes[i].x - nodes[j].x;
      const dy = nodes[i].y - nodes[j].y;
      const distSq = dx * dx + dy * dy;
      if (distSq < MAX_DIST_SQ) {
        const alpha = (1 - Math.sqrt(distSq) / MAX_DIST) * 0.26;
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.moveTo(nodes[i].x, nodes[i].y);
        ctx.lineTo(nodes[j].x, nodes[j].y);
        ctx.stroke();
      }
    }
  }

  // Knoten
  for (const node of nodes) {
    if (node.glow) {
      const pulse = 0.5 + 0.5 * Math.sin(time * 0.0016 + node.phase);
      ctx.globalAlpha = 0.1 + 0.12 * pulse;
      ctx.fillStyle = accent;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 7 + 5 * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 0.95;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r + 0.8, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.globalAlpha = 0.42;
      ctx.fillStyle = accent;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}

function loop(time) {
  drawFrame(time);
  raf = window.requestAnimationFrame(loop);
}

watch(() => props.knows?.active_claims, () => { if (ctx) seedNodes(); });

onMounted(() => {
  reducedMotion.value = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches || false;
  const canvas = canvasRef.value;
  if (canvas) {
    ctx = canvas.getContext('2d');
    readAccent();
    resize();
    if (!reducedMotion.value) raf = window.requestAnimationFrame(loop);
    resizeObserver = new ResizeObserver(() => resize());
    resizeObserver.observe(rootRef.value);
    themeObserver = new MutationObserver(() => { readAccent(); if (reducedMotion.value) drawFrame(0); });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
  }
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(raf);
  resizeObserver?.disconnect();
  themeObserver?.disconnect();
  ctx = null;
});
</script>

<style scoped>
.kstage {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  color: var(--pm-text);
  background:
    radial-gradient(120% 80% at 50% -10%, color-mix(in srgb, var(--pm-accent) 12%, transparent), transparent 60%),
    var(--pm-viewer-surface);
}

.kstage__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.kstage__vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(75% 55% at 50% 42%, color-mix(in srgb, var(--pm-viewer-surface) 55%, transparent), transparent 75%);
}

.kstage__content {
  position: relative;
  z-index: 1;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 40px 30px 44px;
  text-align: center;
}

/* ── Intro ── */
.kstage__intro { display: flex; flex-direction: column; gap: 6px; max-width: 460px; }

.kstage__eyebrow {
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--pm-accent);
}

/* ── Persistenter Wissens-Einstieg (ehem. „Zu prüfen") ── */
.kstage__entry {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 13px;
  border-radius: 999px;
  border: 1px solid var(--pm-divider);
  background: color-mix(in srgb, var(--pm-app-surface-raised) 82%, transparent);
  backdrop-filter: blur(6px);
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.kstage__entry:hover { transform: translateY(-1px); border-color: color-mix(in srgb, var(--pm-accent) 45%, var(--pm-divider)); }
.kstage__entry strong { color: var(--pm-text); font-weight: 700; }
.kstage__entry-hint { color: var(--pm-muted); }
.kstage__entry-arrow { color: var(--pm-muted); margin-left: 1px; transition: transform 0.15s ease; }
.kstage__entry:hover .kstage__entry-arrow { transform: translateX(2px); color: var(--pm-accent); }

.kstage__entry-ic { display: inline-flex; color: var(--pm-accent); }
.kstage__entry--plain { border-color: color-mix(in srgb, var(--pm-accent) 26%, var(--pm-divider)); }
.kstage__entry--plain:hover { background: color-mix(in srgb, var(--pm-accent) 8%, var(--pm-app-surface-raised)); }

.kstage__attn-dot { width: 7px; height: 7px; border-radius: 50%; background: rgb(var(--v-theme-warning)); box-shadow: 0 0 8px rgba(var(--v-theme-warning), 0.6); animation: kstage-pulse 2.4s ease-in-out infinite; }
.kstage__entry--bad .kstage__attn-dot { background: rgb(var(--v-theme-error)); box-shadow: 0 0 8px rgba(var(--v-theme-error), 0.6); }

/* ── Prompt-Karten ── */
.kstage__prompts {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  max-width: 420px;
  margin-top: 2px;
}

.kstage__prompt {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  border-radius: 15px;
  border: 1px solid var(--pm-divider);
  background: color-mix(in srgb, var(--pm-app-surface-raised) 88%, transparent);
  backdrop-filter: blur(8px);
  color: inherit;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
  transition: transform 0.22s cubic-bezier(0.22, 0.7, 0.24, 1), border-color 0.2s ease, box-shadow 0.22s ease;
  animation: kstage-enter 0.6s cubic-bezier(0.22, 0.9, 0.26, 1) backwards, kstage-drift 6s ease-in-out infinite;
  animation-delay: calc(var(--i) * 90ms), calc(var(--i) * 320ms);
}

.kstage__prompt:hover {
  transform: translateY(-4px) scale(1.012);
  border-color: color-mix(in srgb, var(--pm-accent) 46%, var(--pm-divider));
  box-shadow: 0 16px 34px color-mix(in srgb, var(--pm-accent) 20%, rgba(15, 23, 42, 0.12));
}

.kstage__prompt:focus-visible {
  outline: 2px solid var(--pm-accent);
  outline-offset: 2px;
}

.kstage__prompt-shine {
  position: absolute;
  top: 0;
  left: -60%;
  width: 45%;
  height: 100%;
  transform: skewX(-18deg);
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--pm-accent) 16%, transparent), transparent);
  opacity: 0;
  pointer-events: none;
}

.kstage__prompt:hover .kstage__prompt-shine { animation: kstage-shine 0.9s ease; }

.kstage__prompt-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: 11px;
  color: var(--tone, var(--pm-accent));
  background: color-mix(in srgb, var(--tone, var(--pm-accent)) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--tone, var(--pm-accent)) 30%, var(--pm-divider));
  transition: transform 0.22s ease;
}

.kstage__prompt:hover .kstage__prompt-icon { transform: scale(1.08) rotate(-3deg); }

.kstage__prompt-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }

.kstage__prompt-copy small {
  font-size: 0.58rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--tone, var(--pm-accent)) 78%, var(--pm-muted));
}

.kstage__prompt-copy strong {
  font-size: 0.9rem;
  font-weight: 640;
  color: var(--pm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kstage__prompt-arrow { flex: none; color: var(--pm-muted); opacity: 0.6; transition: transform 0.2s ease, opacity 0.2s ease, color 0.2s ease; }
.kstage__prompt:hover .kstage__prompt-arrow { color: var(--tone, var(--pm-accent)); opacity: 1; transform: translate(2px, -2px); }

.kstage__prompt--aqua { --tone: var(--pm-accent); }
.kstage__prompt--blue { --tone: #3b82f6; }
.kstage__prompt--violet { --tone: #8b5cf6; }
.kstage__prompt--amber { --tone: #d97706; }

.kstage__more {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 2px;
  padding: 7px 12px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.15s ease;
}

.kstage__more:hover { color: var(--pm-accent); }

/* ── Keyframes ── */
@keyframes kstage-pulse { 0%, 100% { transform: scale(1); opacity: 0.6; } 50% { transform: scale(1.14); opacity: 1; } }
@keyframes kstage-enter { from { opacity: 0; transform: translateY(14px) scale(0.97); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes kstage-drift { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
@keyframes kstage-shine { from { left: -60%; opacity: 0; } 40% { opacity: 1; } to { left: 120%; opacity: 0; } }

.kstage--still .kstage__attn-dot,
.kstage--still .kstage__prompt {
  animation: none !important;
}

@media (prefers-reduced-motion: reduce) {
  .kstage__attn-dot,
  .kstage__prompt,
  .kstage__prompt-shine {
    animation: none !important;
  }
  .kstage__prompt { opacity: 1; transform: none; }
}
</style>
