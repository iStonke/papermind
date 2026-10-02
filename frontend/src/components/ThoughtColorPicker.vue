<template>
  <span class="thought-color-picker" @pointerdown.stop>
    <button ref="trigger" type="button" class="color-trigger" aria-label="Titelleistenfarbe wählen" title="Titelleistenfarbe wählen" :aria-expanded="open" :disabled="disabled" @click.stop="toggle">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1.6-3.2 1.6 1.6 0 0 1 1.3-2.6H18A5 5 0 0 0 23 10c0-4-5-7-11-7Z" stroke="currentColor" stroke-width="1.7"/><circle cx="7" cy="10" r="1.4" fill="currentColor"/><circle cx="11" cy="7" r="1.4" fill="currentColor"/><circle cx="16" cy="8" r="1.4" fill="currentColor"/></svg>
    </button>
    <Teleport to="body">
      <div v-if="open" ref="panel" class="thought-color-menu papermind-app" :class="theme.themeClasses.value" role="group" aria-label="Titelleistenfarbe" :style="position" @keydown.esc.stop="close" @pointerdown.stop>
        <button v-for="color in colors" :key="color.value" type="button" :aria-label="color.name" :aria-pressed="modelValue === color.value" :style="{ background: color.value }" @click="choose(color.value)">{{ modelValue === color.value ? '✓' : '' }}</button>
      </div>
    </Teleport>
  </span>
</template>
<script setup>
import { THOUGHT_COLORS } from '../utils/thoughtColors.js';
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useTheme } from 'vuetify';
const theme = useTheme();
const props = defineProps({ modelValue: String, disabled: Boolean });
const emit = defineEmits(['update:modelValue']);
const colors = THOUGHT_COLORS;
const open = ref(false), trigger = ref(null), panel = ref(null), position = ref({});
async function toggle() {
  if (open.value) { close(); return; }
  const rect = trigger.value.getBoundingClientRect();
  position.value = { left:`${Math.max(8, Math.min(rect.right - 238, window.innerWidth - 246))}px`, top:`${Math.min(rect.bottom + 6, window.innerHeight - 54)}px` };
  open.value = true;
  await nextTick(); panel.value?.querySelector('button')?.focus();
}
function close() { open.value = false; }
function choose(value) { emit('update:modelValue',value); close(); trigger.value?.focus(); }
function outside(event) { if (!event.target.closest('.thought-color-picker') && !panel.value?.contains(event.target)) close(); }
onMounted(() => { window.addEventListener('pointerdown',outside); window.addEventListener('scroll',close,true); });
onBeforeUnmount(() => { window.removeEventListener('pointerdown',outside); window.removeEventListener('scroll',close,true); });
</script>
<style scoped>
.thought-color-picker { display:flex; margin-right:4px; }
.color-trigger { display:flex; align-items:center; justify-content:center; width:23px; height:23px; padding:3px; border:0; border-radius:5px; color:inherit; background:transparent; cursor:pointer; }
.color-trigger:hover { background:rgba(0,0,0,.08); }
.color-trigger:focus-visible { outline:2px solid currentColor; }
.thought-color-menu { position:fixed; z-index:10000; display:flex; gap:6px; padding:8px; color:var(--pm-text,#172c32); background:var(--pm-app-surface-raised,#fff); border:1px solid var(--pm-divider,#d8dfe1); border-radius:9px; box-shadow:var(--pm-shadow,0 4px 18px #0002); }
.thought-color-menu button { width:26px; height:26px; border:1px solid #0002; border-radius:50%; cursor:pointer; color:#172c32; }
.thought-color-menu button:focus-visible { outline:2px solid var(--pm-accent,#26736b); outline-offset:2px; }
</style>
