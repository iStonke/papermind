<template>
  <span class="note-editor__toolbar-divider" aria-hidden="true" />
  <form
    class="note-editor__toolbar-ai"
    :class="{
      'has-prompt': Boolean(aiPrompt.instruction.trim()),
      'is-generating': aiPrompt.presentation === 'toolbar' && aiPrompt.loading,
      'has-error': aiPrompt.presentation === 'toolbar' && aiPrompt.error,
    }"
    aria-label="Mit KI schreiben"
    @submit.prevent="generateAIText"
    @pointerdown.stop="prepareToolbarAIPromptTarget"
  >
    <button type="button" ref="aiOptionsButtonEl" class="note-editor__toolbar-ai-icon"
      :class="{ 'is-open': aiOptionsOpen }" title="KI-Schreiboptionen" aria-label="KI-Schreiboptionen"
      :aria-expanded="aiOptionsOpen" aria-controls="note-ai-options" :disabled="aiPrompt.loading"
      @click="toggleAIOptions">
      <span
        v-if="aiPrompt.presentation === 'toolbar' && aiPrompt.loading"
        class="note-editor__toolbar-ai-spinner"
      ></span>
      <v-icon v-else size="18">mdi-auto-fix</v-icon>
    </button>
    <input
      ref="aiToolbarInputEl"
      v-model="aiPrompt.instruction"
      type="text"
      maxlength="2000"
      autocomplete="off"
      placeholder="Einfach losschreiben …"
      aria-label="Anweisung an die KI"
      :disabled="aiPrompt.loading"
      :aria-invalid="aiPrompt.error ? 'true' : undefined"
      :aria-describedby="aiPrompt.error ? 'note-editor-ai-error' : undefined"
      @focus="ensureToolbarAIPromptTarget"
      @keydown.esc.prevent="closeAIPrompt"
    />
    <span
      v-if="aiPrompt.presentation === 'toolbar' && aiPrompt.error"
      id="note-editor-ai-error"
      class="note-editor__toolbar-ai-error"
      role="alert"
    >{{ aiPrompt.error }}</span>
    <Transition name="pm-ai-prompt">
      <div v-if="aiOptionsOpen" id="note-ai-options" class="note-editor__ai-options"
        :style="{ left: `${aiOptionsLeft}px` }"
        role="group" aria-label="KI-Schreiboptionen" @pointerdown.stop
        @keydown.esc.stop.prevent="closeAIOptions">
        <fieldset :disabled="aiPrompt.loading">
          <legend>Antwortlänge</legend>
          <div class="note-editor__ai-lengths">
            <button v-for="(option, index) in AI_LENGTH_OPTIONS" :key="option.label" type="button"
              :aria-pressed="aiPrompt.lengthLevel === index" @click="aiPrompt.lengthLevel = index">{{ option.label }}</button>
          </div>
          <output>{{ activeAILengthOption.label }} · {{ activeAILengthOption.lineHint }}</output>
        </fieldset>
        <label>Kontext
          <span class="note-editor__ai-context-select">
            <select v-model="aiPrompt.contextScope" :disabled="aiPrompt.loading">
              <option value="selection" :disabled="!aiPrompt.selectedText">Auswahl</option>
              <option value="before">Text bis zum Cursor</option>
              <option value="note">Ganze Notiz</option>
            </select>
            <v-icon size="18" aria-hidden="true">mdi-chevron-down</v-icon>
          </span>
        </label>
        <small v-if="aiPrompt.mode === 'selection'">Das Ergebnis ersetzt die markierte Auswahl.</small>
      </div>
    </Transition>
  </form>
</template>

<script setup>
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  aiToolbarInputEl,
  aiOptionsButtonEl,
  aiOptionsOpen,
  aiOptionsLeft,
  AI_LENGTH_OPTIONS,
  aiPrompt,
  activeAILengthOption,
  prepareToolbarAIPromptTarget,
  ensureToolbarAIPromptTarget,
  toggleAIOptions,
  closeAIOptions,
  closeAIPrompt,
  generateAIText,
} = props.controller;
</script>

<style scoped src="./styles/aiToolbar.css"></style>
<style scoped src="./styles/progress.css"></style>
<style scoped src="./styles/aiPrompt.css"></style>
