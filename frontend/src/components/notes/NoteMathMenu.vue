<template>
  <form
    v-if="editor && mathEditor.open"
    class="pm-float pm-math-editor"
    :style="mathEditor.style"
    aria-label="Formel bearbeiten"
    @submit.prevent="applyMath"
    @mousedown.stop
  >
    <div class="pm-math-editor__head">
      <span><span class="pm-math-editor__glyph" aria-hidden="true">∑</span> Formel</span>
      <button
        v-if="mathEditor.mode === 'insert'"
        type="button"
        class="pm-math-editor__type"
        :title="mathEditor.type === 'blockMath' ? 'Als Inline-Formel im Satz einfügen' : 'Als eigenen Formelblock einfügen'"
        @click="toggleMathType"
      >{{ mathEditor.type === 'blockMath' ? 'Block' : 'Im Text' }}</button>
      <span v-else class="pm-math-editor__type is-static">{{ mathEditor.type === 'blockMath' ? 'Block' : 'Im Text' }}</span>
    </div>
    <textarea
      ref="mathInputEl"
      v-model="mathEditor.latex"
      class="pm-math-editor__input"
      rows="2"
      spellcheck="false"
      autocomplete="off"
      autocapitalize="off"
      placeholder="LaTeX, z. B. R(\theta) = \begin{pmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{pmatrix}"
      aria-label="LaTeX-Quelltext"
      @keydown="onMathKeydown"
    ></textarea>
    <!-- KaTeX-Ausgabe (trust: false) – erzeugt nur eigenes, maskiertes Markup. -->
    <div
      class="pm-math-editor__preview"
      :class="{ 'is-empty': !previewHtml }"
      aria-live="polite"
      v-html="previewHtml || 'Vorschau'"
    ></div>
    <div class="pm-math-editor__foot">
      <span class="pm-math-editor__hint">⏎ übernehmen · ⇧⏎ Zeile</span>
      <button v-if="mathEditor.mode === 'edit'" type="button" class="pm-math-editor__remove" @click="removeMath">Entfernen</button>
      <button type="submit" class="pm-math-editor__save">{{ mathEditor.mode === 'edit' ? 'Übernehmen' : 'Einfügen' }}</button>
    </div>
  </form>
</template>

<script setup>
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  mathEditor,
  mathInputEl,
  previewHtml,
  applyMath,
  removeMath,
  toggleMathType,
  onMathKeydown,
} = props.controller;
</script>

<style scoped>
.pm-math-editor {
  box-sizing: border-box;
  width: 380px;
  max-width: calc(100% - 16px);
  padding: 10px;
  color: var(--pm-text, #0e181b);
}
.pm-math-editor__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1px 2px 8px;
  color: var(--pm-muted, #535e62);
  font-size: 0.76rem;
  font-weight: 650;
  letter-spacing: 0.02em;
}
.pm-math-editor__head > span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pm-math-editor__glyph {
  font-size: 0.95rem;
  line-height: 1;
}
.pm-math-editor__type {
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 999px;
  background: transparent;
  padding: 1px 9px;
  color: var(--pm-muted, #535e62);
  font: inherit;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
}
.pm-math-editor__type:hover,
.pm-math-editor__type:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 50%, transparent);
  color: var(--pm-text, #0e181b);
  outline: none;
}
.pm-math-editor__type.is-static { cursor: default; }
.pm-math-editor__input {
  box-sizing: border-box;
  width: 100%;
  min-height: 58px;
  resize: vertical;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 8px;
  outline: none;
  background: var(--pm-content-surface, #fff);
  padding: 8px 10px;
  color: var(--pm-text, #0e181b);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.8rem;
  line-height: 1.45;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.pm-math-editor__input::placeholder { color: var(--pm-muted, #8a969b); opacity: 0.6; }
.pm-math-editor__input:focus {
  border-color: var(--pm-accent, #006b75);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent, #006b75) 13%, transparent);
}
.pm-math-editor__preview {
  margin-top: 8px;
  min-height: 34px;
  max-height: 180px;
  overflow: auto;
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 4%, transparent);
  text-align: center;
}
.pm-math-editor__preview.is-empty {
  color: var(--pm-muted, #535e62);
  font-size: 0.74rem;
  display: grid;
  place-items: center;
}
.pm-math-editor__preview :deep(.katex-display) { margin: 0; }
.pm-math-editor__foot {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}
.pm-math-editor__hint {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--pm-muted, #535e62);
  font-size: 0.68rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pm-math-editor__remove,
.pm-math-editor__save {
  height: 30px;
  border: 0;
  border-radius: 7px;
  padding: 0 12px;
  font: inherit;
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
}
.pm-math-editor__remove {
  background: transparent;
  color: var(--pm-danger, #b42318);
}
.pm-math-editor__remove:hover { background: color-mix(in srgb, var(--pm-danger, #b42318) 10%, transparent); }
.pm-math-editor__save {
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
}
.pm-math-editor__save:hover { filter: brightness(1.07); }
</style>
