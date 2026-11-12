<!--
  CorrespondentRecognition — Abschnitt „Aliase“ im Korrespondenten-Profil,
  direkt bearbeitbar: Namen (Aliase bzw. Erkennungsnamen) als Chips mit
  Entfernen und Eingabefeld. Die Erklärung steckt hinter dem ⓘ der Überschrift.
  Speichert über den Korrespondenten-Store (Meldungen zeigt der Store).
-->
<template>
  <section class="pm-recog" :aria-labelledby="headingId">
    <PmInfoHeading title="Aliase" :heading-id="headingId" :reset-key="correspondent.id" info-label="Wofür werden diese Namen verwendet?">
      <p>{{ hint }}</p>
    </PmInfoHeading>

    <TransitionGroup
      name="corr-alias"
      tag="div"
      class="pm-recog__chips"
      move-class="pm-inline-add-move"
      @leave="(_, done) => done()"
    >
      <span v-for="alias in names" :key="alias.id" class="pm-recog__chip">
        <span class="pm-recog__chip-text">{{ alias.alias }}</span>
        <button
          type="button"
          class="pm-recog__remove"
          :disabled="busy"
          :aria-label="`Namen „${alias.alias}“ entfernen`"
          title="Entfernen"
          @click="removeAlias(alias)"
        ><v-icon size="13">mdi-close</v-icon></button>
      </span>
      <form
        v-if="isAddingName"
        v-click-outside="closeEmptyEditor"
        key="editor"
        class="pm-recog__add"
        @submit.prevent="addName"
        @keydown.esc.stop.prevent="!busy && closeNameEditor()"
      >
        <input
          ref="nameInputRef"
          v-model="newName"
          type="text"
          maxlength="120"
          placeholder="Alias hinzufügen"
          aria-label="Weiteren Alias hinzufügen"
          :disabled="busy"
          :size="Math.max(18, newName.length + 2)"
        >
        <button type="submit" class="pm-recog__editor-action" :disabled="busy || !newName.trim()" aria-label="Alias speichern" title="Alias speichern">
          <v-icon size="16" aria-hidden="true">mdi-check</v-icon>
        </button>
        <button type="button" class="pm-recog__editor-action" :disabled="busy" aria-label="Eingabe abbrechen" title="Eingabe abbrechen" @click="closeNameEditor()">
          <v-icon size="16" aria-hidden="true">mdi-close</v-icon>
        </button>
      </form>
      <button
        v-else
        key="add"
        ref="addButtonRef"
        type="button"
        class="pm-recog__action"
        :disabled="busy"
        @click="openNameEditor"
      >
        <v-icon size="16" aria-hidden="true">mdi-plus</v-icon>
        Alias hinzufügen
      </button>
    </TransitionGroup>
  </section>
</template>

<script setup>
import { correspondentDisplayName } from '../utils/correspondentHierarchy.js';
import { computed, nextTick, ref, watch } from 'vue';
import { ClickOutside as vClickOutside } from 'vuetify/directives';
import PmInfoHeading from './PmInfoHeading.vue';
import { useCorrespondentStore } from '../stores/correspondents.js';
import { animateInlinePlaceholderResize } from '../utils/inlinePlaceholderMotion.js';

const props = defineProps({
  correspondent: { type: Object, required: true },
  /** id der Überschrift (für aria-labelledby des umgebenden Abschnitts). */
  headingId: { type: String, default: undefined },
});

const store = useCorrespondentStore();
const collator = new Intl.Collator('de-DE', { sensitivity: 'base' });
const names = computed(() => (props.correspondent.aliases || []).slice().sort((a, b) => collator.compare(a.alias, b.alias)));
const busy = ref(false);
const newName = ref('');
const isAddingName = ref(false);
const nameInputRef = ref(null);
const addButtonRef = ref(null);

const hint = computed(() =>
  props.correspondent.kind === 'collection'
    ? 'Dokumente, in denen einer dieser Namen vorkommt, landen direkt in der Sammlung – für Absender ohne eigenen Eintrag.'
    : `Dokumente, in denen einer dieser Namen vorkommt, werden „${correspondentDisplayName(props.correspondent)}“ zugeordnet.`
);

watch(() => props.correspondent.id, () => closeNameEditor(false));

async function openNameEditor() {
  const placeholderBounds = addButtonRef.value?.getBoundingClientRect();
  isAddingName.value = true;
  await nextTick();
  const input = nameInputRef.value;
  animateInlinePlaceholderResize(input?.form, placeholderBounds);
  input?.focus();
}

function closeNameEditor(restoreFocus = true) {
  const editorBounds = nameInputRef.value?.form?.getBoundingClientRect();
  newName.value = '';
  isAddingName.value = false;
  nextTick(() => {
    const placeholder = addButtonRef.value;
    animateInlinePlaceholderResize(placeholder, editorBounds);
    if (restoreFocus) placeholder?.focus();
  });
}

function closeEmptyEditor() {
  if (!newName.value.trim()) closeNameEditor(false);
}

/** Store meldet Fehler selbst; hier nur Doppelklicks verhindern. */
async function run(action) {
  if (busy.value) return false;
  busy.value = true;
  try {
    await action();
    return true;
  } catch {
    return false;
  } finally {
    busy.value = false;
  }
}

async function addName() {
  const name = newName.value.trim();
  if (!name) return;
  if (await run(() => store.addAlias(props.correspondent.id, name))) closeNameEditor();
}
const removeAlias = (alias) => run(() => store.deleteAlias(props.correspondent.id, alias.id));
</script>

<style scoped>
.pm-recog { display: flex; flex-direction: column; }
.pm-recog__chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.pm-recog__chip, .pm-recog__action {
  display: inline-flex;
  align-items: center;
  box-sizing: border-box;
  max-width: 100%;
  min-height: 28px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  font-size: 0.86rem;
}
.pm-recog__chip {
  gap: 2px;
  padding: 0 4px 0 11px;
  border-color: color-mix(in srgb, var(--pm-accent) 24%, var(--pm-divider));
  background: color-mix(in srgb, var(--pm-accent) 9%, var(--pm-app-surface));
  color: var(--pm-text);
}
.pm-recog__chip.corr-alias-enter-active { transition: opacity var(--pm-duration-fast, 140ms) ease; }
.pm-recog__chip.corr-alias-enter-from { opacity: 0; }
.pm-recog__action {
  gap: 5px;
  padding: 0 10px;
  border-style: dashed;
  border-color: color-mix(in srgb, var(--pm-muted) 45%, var(--pm-divider));
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
}
.pm-recog__action .v-icon { color: var(--pm-accent-text); }
.pm-recog__action:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--pm-accent) 45%, var(--pm-divider));
  color: var(--pm-text);
}
.pm-recog__chip-text { min-width: 0; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pm-recog__remove,
.pm-recog__editor-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--pm-muted);
  opacity: 0.55;
  cursor: pointer;
  transition: opacity var(--pm-duration-fast, 140ms) var(--pm-easing), background-color var(--pm-duration-fast, 140ms) var(--pm-easing);
}
.pm-recog__chip:hover .pm-recog__remove,
.pm-recog__remove:focus-visible { opacity: 1; }
.pm-recog__remove:hover:not(:disabled) { background: var(--pm-row-hover); color: var(--pm-error); }
.pm-recog__editor-action { width: 24px; height: 24px; opacity: 1; }
.pm-recog__editor-action[type="submit"] { color: var(--pm-accent-text); }
.pm-recog__editor-action:hover:not(:disabled) { background: var(--pm-row-hover); }
.pm-recog__editor-action:disabled, .pm-recog__action:disabled { opacity: 0.5; cursor: default; }
.pm-recog__add {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  max-width: 100%;
  padding-inline: 10px 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent) 4%, transparent);
  color: var(--pm-accent-text);
}
.pm-recog__add:focus-within { border-color: var(--pm-accent); }
.pm-recog__add .v-icon { flex: none; }
.pm-recog__add input {
  field-sizing: content;
  min-width: 0;
  max-width: 220px;
  padding: 0;
  border: 0;
  outline: none;
  background: none;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.86rem;
}
.pm-recog__add input::placeholder { color: var(--pm-muted); opacity: 1; }
@media (pointer: coarse) {
  .pm-recog__action { min-height: 44px; }
}
</style>
