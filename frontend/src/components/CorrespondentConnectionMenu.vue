<template>
  <v-menu v-model="connectOpen" location="bottom start" :offset="6" :close-on-content-click="false" attach=".papermind-app">
    <template #activator="{ props: activatorProps }">
      <slot name="activator" :props="activatorProps" />
    </template>
    <div class="corr-connect" role="dialog" aria-label="Verbindung hinzufügen">
      <div class="corr-connect__roles" role="radiogroup" aria-label="Art der Verbindung">
        <button
          v-for="kind in options"
          :key="kind.value"
          type="button"
          role="radio"
          class="corr-filter__btn"
          :disabled="disabled"
          :class="{ 'is-active': connectKind?.value === kind.value }"
          :aria-checked="connectKind?.value === kind.value"
          @click="connectRole = kind.roles[0]"
        >{{ kind.label }}</button>
      </div>
      <div class="corr-connect__hint">
        <span class="corr-muted">{{ connectRoleMeta?.hint(correspondent.name, correspondent.kind) }}</span>
        <button
          v-if="connectKind?.roles.length > 1"
          type="button"
          class="corr-icon-btn corr-connect__swap"
          :disabled="disabled"
          aria-label="Richtung tauschen"
          title="Richtung tauschen"
          @click="swapConnectDirection"
        ><v-icon size="16">mdi-swap-horizontal</v-icon></button>
      </div>
      <label class="pm-searchbar corr-connect__search">
        <v-icon size="16">mdi-magnify</v-icon>
        <input
          ref="connectInputRef"
          v-model="connectQuery"
          type="text"
          placeholder="Korrespondent suchen"
          aria-label="Korrespondent suchen"
          @keydown.enter.prevent="connectCandidates[0] && submitConnection(connectCandidates[0])"
        >
      </label>
      <ul class="corr-connect__results">
        <li v-for="candidate in connectCandidates.slice(0, 7)" :key="candidate.id">
          <button type="button" class="corr-connect__result" :disabled="disabled" @click="submitConnection(candidate)">
            <span class="corr-pill__avatar" aria-hidden="true">{{ candidateInitials(candidate.name) }}</span>
            <span class="corr-connect__name">{{ candidate.name }}</span>
            <span class="corr-muted corr-connect__kind">{{ correspondentKindLabel(candidate.kind) }}</span>
          </button>
        </li>
        <li v-if="!connectCandidates.length" class="corr-muted corr-connect__empty">Kein passender Korrespondent.</li>
      </ul>
      <p v-if="connectError" class="corr-connect__error" role="alert">{{ connectError }}</p>
    </div>
  </v-menu>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { CORRESPONDENT_CONNECTION_ROLES, correspondentKindLabel } from '../utils/correspondentHierarchy.js';

const props = defineProps({
  correspondent: { type: Object, required: true },
  options: { type: Array, required: true },
  findCandidates: { type: Function, required: true },
  candidateInitials: { type: Function, required: true },
  saveConnection: { type: Function, required: true },
  disabled: Boolean,
});

const connectOpen = ref(false);
const connectRole = ref('');
const connectQuery = ref('');
const connectError = ref('');
const connectInputRef = ref(null);
const connectKind = computed(() => props.options.find(kind => kind.roles.includes(connectRole.value)));
const connectRoleMeta = computed(() => CORRESPONDENT_CONNECTION_ROLES.find(role => role.value === connectRole.value));
const connectCandidates = computed(() => connectKind.value ? props.findCandidates(connectRole.value, connectQuery.value) : []);

watch(connectOpen, open => {
  if (!open) return;
  connectQuery.value = '';
  connectRole.value = props.options[0]?.roles[0] || '';
  connectError.value = '';
  setTimeout(() => {
    if (connectOpen.value) connectInputRef.value?.focus();
  }, 60);
});
watch(connectRole, () => { connectError.value = ''; });

function swapConnectDirection() {
  const roles = connectKind.value?.roles || [];
  if (roles.length > 1) connectRole.value = roles[(roles.indexOf(connectRole.value) + 1) % roles.length];
}

async function submitConnection(candidate) {
  if (props.disabled || !connectKind.value) return;
  connectError.value = '';
  try {
    if (await props.saveConnection(candidate, connectRole.value)) connectOpen.value = false;
  } catch (error) {
    connectError.value = error?.message || 'Die Verbindung konnte nicht angelegt werden.';
  }
}
</script>

<style scoped>
.corr-muted { color: var(--pm-muted); }

.corr-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}
.corr-icon-btn:hover:not(:disabled) { background: var(--pm-row-hover); color: var(--pm-error); }

.corr-pill__avatar {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--pm-chip-bg);
  color: var(--pm-muted);
  font-size: 0.64rem;
  font-weight: 650;
}

.corr-connect {
  width: min(340px, calc(100vw - 28px));
  padding: 12px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  background: var(--pm-v-card, var(--pm-app-surface-raised));
  box-shadow: var(--pm-shadow);
}
/* Ganz dezent durchscheinend wie die i-Popover; die Unschärfe hält alles lesbar. */
@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .corr-connect {
    background: color-mix(in srgb, var(--pm-v-card, var(--pm-app-surface-raised)) 86%, transparent);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    backdrop-filter: blur(14px) saturate(140%);
  }
}
.corr-connect__roles { display: flex; flex-wrap: wrap; gap: 6px; }
.corr-connect__hint { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 28px; margin: 8px 2px 6px; font-size: 0.8rem; }
.corr-connect__swap:hover:not(:disabled) { color: var(--pm-accent-text); }
.corr-connect__search {
  --pm-searchbar-h: 34px;
  gap: 6px;
  padding: 0 10px;
  color: var(--pm-muted);
}
.corr-connect__search input { flex: 1; min-width: 0; border: 0; outline: none; background: none; color: var(--pm-text); font: inherit; font-size: 0.86rem; }
.corr-connect__search input::placeholder { color: var(--pm-muted); opacity: 1; }
.corr-connect__search:focus-within .v-icon { color: var(--pm-accent); }
.corr-connect__results { list-style: none; margin: 6px 0 0; padding: 0; }
.corr-connect__result {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 34px;
  padding: 4px 6px;
  border: 0;
  border-radius: 8px;
  background: none;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.86rem;
  text-align: left;
  cursor: pointer;
}
.corr-connect__result:hover:not(:disabled) { background: var(--pm-row-hover); }
.corr-connect__name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.corr-connect__kind { font-size: 0.76rem; }
.corr-connect__empty { padding: 8px 6px; font-size: 0.82rem; }
.corr-connect__error { margin: 8px 2px 0; color: var(--pm-error); font-size: 0.8rem; }

.corr-filter__btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted);
  font-size: 0.78rem;
  font-weight: 550;
  cursor: pointer;
  transition: border-color var(--pm-duration-fast) var(--pm-easing), color var(--pm-duration-fast) var(--pm-easing), background var(--pm-duration-fast) var(--pm-easing);
}
.corr-filter__btn:hover:not(:disabled) { color: var(--pm-text); border-color: var(--pm-outline); }
.corr-filter__btn.is-active {
  color: var(--pm-accent-text);
  border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
}
.corr-filter__btn:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
