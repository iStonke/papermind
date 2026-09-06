<template>
      <Transition name="pm-ai-prompt">
      <form
        v-if="editor && aiPrompt.open && aiPrompt.presentation === 'dialog'"
        class="pm-float pm-ai-prompt pm-ai-prompt--writing"
        :class="{ 'is-generating': aiPrompt.loading }"
        :style="aiPrompt.style"
        :aria-label="aiPrompt.mode === 'selection' ? 'Auswahl mit KI bearbeiten' : 'Mit KI schreiben'"
        @submit.prevent="generateAIText"
      >
        <div class="pm-ai-prompt__head">
          <span>
            <v-icon class="pm-ai-prompt__icon" size="17" aria-hidden="true">mdi-auto-fix</v-icon>
            {{ aiPrompt.mode === 'selection' ? 'Auswahl mit KI bearbeiten' : 'Mit KI schreiben' }}
          </span>
          <button type="button" class="pm-ai-prompt__close" aria-label="Schließen" @click="closeAIPrompt">×</button>
        </div>
        <div class="pm-ai-prompt__context" :class="{ 'is-selection': aiPrompt.mode === 'selection' }">
          <span aria-hidden="true"></span>
          {{ aiContextLabel }}
        </div>
        <div class="pm-ai-prompt__input-row">
          <input
            ref="aiPromptInputEl"
            v-model="aiPrompt.instruction"
            type="text"
            maxlength="2000"
            autocomplete="off"
            :placeholder="aiPrompt.mode === 'selection' ? 'Was soll PaperMind mit der Auswahl tun?' : 'Was soll PaperMind schreiben?'"
            :disabled="aiPrompt.loading"
            @keydown.esc.prevent="closeAIPrompt"
          />
          <button
            type="submit"
            class="pm-ai-prompt__submit"
            :disabled="aiPrompt.loading || !aiPrompt.instruction.trim() || aiSelectionTooLong"
            :aria-label="aiPrompt.loading ? 'Text wird generiert' : 'Text generieren'"
          >
            <span v-if="aiPrompt.loading" class="pm-ai-prompt__spinner" aria-hidden="true"></span>
            <span v-else aria-hidden="true">→</span>
          </button>
        </div>
        <fieldset class="pm-ai-prompt__length" :disabled="aiPrompt.loading">
          <legend>Antwortlänge</legend>
          <output>{{ activeAILengthOption.label }} · {{ activeAILengthOption.lineHint }}</output>
          <input
            v-model.number="aiPrompt.lengthLevel"
            type="range"
            min="0"
            :max="AI_LENGTH_OPTIONS.length - 1"
            step="1"
            aria-label="Antwortlänge"
            :aria-valuetext="`${activeAILengthOption.label}, ${activeAILengthOption.lineHint}`"
          />
          <div aria-hidden="true">
            <span v-for="option in AI_LENGTH_OPTIONS" :key="option.label">{{ option.label }}</span>
          </div>
        </fieldset>
        <div v-if="aiPrompt.loading" class="pm-ai-prompt__progress" aria-hidden="true">
          <span></span>
        </div>
        <div
          v-if="!aiPrompt.loading && !aiPrompt.preview && visibleAIPromptSuggestions.length"
          class="pm-ai-prompt__suggestions"
        >
          <button
            v-for="suggestion in visibleAIPromptSuggestions"
            :key="suggestion"
            type="button"
            @click="applyAIPromptSuggestion(suggestion)"
          >{{ suggestion }}</button>
        </div>
        <div v-if="aiPrompt.preview" class="pm-ai-prompt__preview" aria-live="polite">
          <span>{{ aiPrompt.preview }}</span>
        </div>
        <div v-if="aiPrompt.loading" class="pm-ai-prompt__status" aria-live="polite">
          {{ aiPrompt.provider
            ? `${aiPrompt.fallbackFrom ? 'Lokaler Fallback' : providerLabel(aiPrompt.provider)} · ${aiPrompt.model}`
            : 'Modell wird gestartet …' }}
        </div>
        <div
          v-if="aiPrompt.mode === 'selection' && aiPrompt.preview && !aiPrompt.loading && !aiPrompt.error"
          class="pm-ai-prompt__result-actions"
        >
          <button type="button" class="is-primary" @click="applySelectionAIResult('replace')">
            Auswahl ersetzen
          </button>
          <button type="button" @click="applySelectionAIResult('insert')">
            Danach einfügen
          </button>
        </div>
        <div v-if="aiPrompt.error" class="pm-ai-prompt__error" role="alert">{{ aiPrompt.error }}</div>
      </form>
      </Transition>

</template>

<script setup>
import { providerLabel } from './composables/noteAILabels.js';
const props = defineProps({ controller: { type: Object, required: true } });
const { editor, aiToolbarInputEl, aiPromptInputEl, aiOptionsButtonEl, aiOptionsOpen, aiOptionsLeft, AI_LENGTH_OPTIONS, aiPrompt, aiSelectionTooLong, activeAILengthOption, aiContextLabel, visibleAIPromptSuggestions, prepareToolbarAIPromptTarget, ensureToolbarAIPromptTarget, toggleAIOptions, closeAIOptions, openAIPrompt, closeAIPrompt, applyAIPromptSuggestion, applySelectionAIResult, generateAIText, positionAIPrompt } = props.controller;
</script>

<style scoped src="./styles/aiPrompt.css"></style>
<style scoped src="./styles/progress.css"></style>
<style scoped src="./styles/floating.css"></style>
