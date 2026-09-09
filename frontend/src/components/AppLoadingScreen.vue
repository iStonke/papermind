<template>
  <main class="app-loading" :data-mode="mode" :class="{ 'is-still': !animate || timedOut }" :aria-busy="!timedOut">
    <div class="app-loading__content">
      <div class="workspace-scene" aria-hidden="true">
        <div class="workspace-scene__halo"></div>
        <div class="workspace-window">
          <div class="workspace-window__bar"><i></i><i></i><i></i><span></span></div>
          <div class="workspace-window__body">
            <div class="workspace-nav"><b></b><i></i><i></i><i></i></div>
            <div class="workspace-pages">
              <div class="workspace-note"><span></span><i></i><i></i><i></i></div>
              <div class="workspace-document"><span></span><i></i><i></i></div>
              <div class="workspace-lines"><i></i><i></i></div>
            </div>
          </div>
        </div>
        <div class="workspace-orbit"><i></i><i></i><i></i></div>
      </div>
      <h1>PaperMind</h1>
      <div role="status" aria-live="polite">
        <p v-if="!timedOut">Dein Arbeitsbereich wird vorbereitet …</p>
        <p v-else>Das Laden dauert länger als erwartet.</p>
      </div>
      <button v-if="timedOut" type="button" @click="reload">Erneut laden</button>
    </div>
  </main>
</template>

<script setup>
import { ref } from 'vue';
import { readBootTheme } from '../utils/bootTheme.js';
defineProps({ timedOut: { type: Boolean, default: false } });
const mode = ref(readBootTheme());
let animate = true;
try { animate = localStorage.getItem('pm.animationsEnabled') !== '0'; } catch { /* Storage optional. */ }
function reload() { window.location.reload(); }
</script>

<style scoped>
.app-loading {
  --boot-bg: #f5f8f9; --boot-paper: #fff; --boot-text: #162f36;
  --boot-muted: #596c72; --boot-accent: #007782; --boot-line: #d9e5e8;
  --boot-shadow: rgba(20, 55, 65, .12);
  min-height: 100dvh; display: grid; place-items: center; padding: 32px 20px;
  background: var(--boot-bg); color: var(--boot-text); color-scheme: light;
}
.app-loading[data-mode="dark"] {
  --boot-bg: #1a2326; --boot-paper: #303d42; --boot-text: #edf5f6;
  --boot-muted: #a7bbc1; --boot-accent: #55c5cc; --boot-line: #52666d;
  --boot-shadow: rgba(0, 0, 0, .25); color-scheme: dark;
}
.app-loading, .app-loading * { box-sizing: border-box; }
.app-loading__content { text-align: center; width: min(100%, 420px); }
.app-loading h1 { font-size: 27px; font-weight: 650; letter-spacing: -.025em; margin: 18px 0 8px; }
.app-loading p { color: var(--boot-muted); font-size: 14px; line-height: 1.6; margin: 0; }
.workspace-scene { width: 272px; max-width: 100%; height: 200px; margin: auto; position: relative; }
.workspace-scene__halo { position: absolute; inset: -25px; background: radial-gradient(ellipse, color-mix(in srgb, var(--boot-accent) 12%, transparent), transparent 68%); }
.workspace-window { position: absolute; inset: 14px 8px 28px; border: 1px solid var(--boot-line); border-radius: 12px; overflow: hidden; background: var(--boot-paper); box-shadow: 0 16px 36px var(--boot-shadow); transform: perspective(700px) rotateY(-8deg) rotateX(5deg); }
.workspace-window__bar { height: 25px; border-bottom: 1px solid var(--boot-line); display: flex; align-items: center; gap: 4px; padding: 0 10px; }
.workspace-window__bar i { width: 4px; height: 4px; border-radius: 50%; background: var(--boot-line); }
.workspace-window__bar span { width: 42px; height: 4px; margin: auto; border-radius: 3px; background: var(--boot-line); }
.workspace-window__body { display: flex; height: calc(100% - 25px); }
.workspace-nav { width: 49px; flex: none; padding: 13px 9px; background: color-mix(in srgb, var(--boot-accent) 8%, var(--boot-paper)); border-right: 1px solid var(--boot-line); }
.workspace-nav b { display: block; width: 13px; height: 13px; border-radius: 4px; background: var(--boot-accent); margin-bottom: 16px; }
.workspace-nav i { display: block; width: 26px; height: 4px; border-radius: 3px; background: var(--boot-line); margin-bottom: 11px; animation: workspace-wake 4.8s ease-in-out infinite; }
.workspace-nav i:nth-child(3) { animation-delay: .15s; }
.workspace-nav i:nth-child(4) { animation-delay: .3s; }
.workspace-pages { flex: 1; min-width: 0; padding: 15px 13px; display: grid; grid-template-columns: 1.2fr 1fr; gap: 9px; }
.workspace-note, .workspace-document { border: 1px solid var(--boot-line); border-radius: 6px; padding: 10px 8px; animation: workspace-arrive 4.8s ease-in-out infinite; }
.workspace-note { background: color-mix(in srgb, var(--boot-accent) 7%, var(--boot-paper)); }
.workspace-document { animation-delay: .25s; }
.workspace-note span { display: block; width: 21px; height: 4px; background: var(--boot-accent); border-radius: 3px; margin-bottom: 10px; }
.workspace-document span { display: block; width: 16px; height: 19px; border: 1px solid var(--boot-accent); border-radius: 3px; margin-bottom: 6px; }
.workspace-pages i { display: block; height: 3px; border-radius: 3px; margin-top: 5px; background: var(--boot-line); }
.workspace-pages i:last-child { width: 65%; }
.workspace-lines { grid-column: 1 / -1; animation: workspace-wake 4.8s .5s ease-in-out infinite; }
.workspace-lines i { margin-top: 0; margin-bottom: 6px; }
.workspace-orbit { position: absolute; bottom: 2px; left: 0; right: 0; display: flex; justify-content: center; gap: 7px; }
.workspace-orbit i { width: 5px; height: 5px; border-radius: 50%; background: var(--boot-accent); opacity: .4; animation: workspace-pulse 1.8s ease-in-out infinite; }
.workspace-orbit i:nth-child(2) { animation-delay: .2s; }
.workspace-orbit i:nth-child(3) { animation-delay: .4s; }
.app-loading button { margin-top: 20px; padding: 10px 18px; border-radius: 10px; border: 1px solid var(--boot-accent); color: var(--boot-text); background: transparent; font: inherit; cursor: pointer; }
.app-loading button:hover { background: color-mix(in srgb, var(--boot-accent) 12%, transparent); }
.app-loading button:focus-visible { outline: 2px solid var(--boot-accent); outline-offset: 4px; }
@keyframes workspace-arrive { 0%,100% { opacity: .35; transform: translateY(5px); } 18%,82% { opacity: 1; transform: translateY(0); } }
@keyframes workspace-wake { 0%,100% { opacity: .3; } 22%,80% { opacity: 1; } }
@keyframes workspace-pulse { 0%,100% { opacity: .3; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-3px); } }
.is-still *, :global(.pm-no-animations) .app-loading * { animation: none !important; }
@media (prefers-reduced-motion: reduce) {
  .app-loading * { animation: none !important; }
}
</style>
