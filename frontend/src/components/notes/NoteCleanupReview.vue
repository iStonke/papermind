<template>
  <Teleport v-if="editor && cleanupAnchorEl" :to="cleanupAnchorEl">
    <Transition name="pm-cleanup-review" appear>
      <section
        v-if="cleanup.open"
        class="pm-cleanup-review"
        :class="{ 'is-generating': cleanup.loading }"
        role="dialog"
        aria-label="Vorschlag · noch nicht übernommen"
        @mousedown.stop
      >
        <div class="pm-cleanup-review__head">
          <span class="pm-cleanup-review__title">
            <v-icon size="19" aria-hidden="true">mdi-auto-fix</v-icon>
            Vorschlag · noch nicht übernommen
          </span>
          <div class="pm-cleanup-review__views" role="group" aria-label="Ansicht">
            <button
              v-for="view in cleanupViews"
              :key="view.value"
              type="button"
              :class="{ 'is-active': cleanup.view === view.value }"
              :aria-pressed="cleanup.view === view.value ? 'true' : 'false'"
              :disabled="cleanup.loading || !cleanup.draftBlocks.length"
              @click="cleanup.view = view.value"
            >{{ view.label }}</button>
          </div>
        </div>

        <div v-if="cleanup.loading" class="pm-cleanup-review__loading" aria-live="polite">
          <div class="pm-ai-prompt__progress" aria-hidden="true"><span></span></div>
          <span>{{ cleanup.provider
            ? `${cleanup.fallbackFrom ? 'Lokaler Fallback' : providerLabel(cleanup.provider)} · ${cleanup.model}`
            : 'Vorschlag wird erstellt …' }}</span>
        </div>

        <div v-else-if="cleanup.draftBlocks.length" class="pm-cleanup-review__content">
          <div v-if="cleanup.view === 'original'" class="pm-cleanup-review__text">
            {{ cleanupOriginalText }}
          </div>
          <div v-else-if="cleanup.view === 'diff'" class="pm-cleanup-review__text" aria-label="Vergleich">
            <template v-for="(part, index) in cleanupDiffParts" :key="index">
              <del v-if="part.type === 'removed'">{{ part.text }}</del>
              <ins v-else-if="part.type === 'added'">{{ part.text }}</ins>
              <span v-else>{{ part.text }}</span>
            </template>
          </div>
          <div v-else class="pm-cleanup-review__editors">
            <textarea
              v-for="(_block, index) in cleanup.draftBlocks"
              :key="index"
              v-model="cleanup.draftBlocks[index]"
              rows="2"
              :aria-label="cleanup.draftBlocks.length === 1 ? 'Vorschlag bearbeiten' : `Vorschlag für Absatz ${index + 1} bearbeiten`"
              @input="cleanup.error = ''"
            ></textarea>
          </div>
        </div>

        <div v-if="cleanup.instructionOpen" class="pm-cleanup-review__instruction">
          <input
            v-model="cleanup.instruction"
            type="text"
            maxlength="600"
            placeholder="Zusätzliche Anweisung …"
            aria-label="Zusätzliche Anweisung"
            @keydown.enter.prevent="regenerateCleanup"
          />
          <button type="button" :disabled="cleanup.loading" @click="regenerateCleanup">Anwenden</button>
        </div>

        <div v-if="cleanup.error" class="pm-cleanup-review__error" role="alert">{{ cleanup.error }}</div>

        <div class="pm-cleanup-review__actions">
          <div>
            <button
              v-if="cleanup.draftBlocks.length"
              type="button"
              class="is-quiet"
              :disabled="cleanup.loading"
              @click="regenerateCleanup"
            ><v-icon size="17">mdi-refresh</v-icon> Neu erzeugen</button>
            <button
              v-if="cleanup.draftBlocks.length"
              type="button"
              class="is-quiet"
              @click="cleanup.instructionOpen = !cleanup.instructionOpen"
            ><v-icon size="17">mdi-message-text-outline</v-icon> Anweisung ergänzen</button>
          </div>
          <div>
            <button type="button" @click="discardCleanup">Verwerfen</button>
            <button
              type="button"
              class="is-primary"
              :disabled="cleanup.loading || !cleanupCanApply"
              @click="applyCleanup"
            ><v-icon size="17">mdi-check</v-icon> Übernehmen</button>
          </div>
        </div>
      </section>
    </Transition>

    <Transition name="pm-cleanup-review">
      <div v-if="cleanupRestore.open" class="pm-cleanup-restore" role="status" aria-live="polite">
        <span>Bereinigte Fassung übernommen.</span>
        <button type="button" @click="restoreCleanupOriginal">
          <v-icon size="17">mdi-undo</v-icon> Ursprung wiederherstellen
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { providerLabel } from './composables/noteAILabels.js';
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  cleanup,
  cleanupRestore,
  cleanupAnchorEl,
  cleanupViews,
  cleanupOriginalText,
  cleanupDiffParts,
  cleanupCanApply,
  regenerateCleanup,
  discardCleanup,
  applyCleanup,
  restoreCleanupOriginal,
} = props.controller;
</script>

<style scoped src="./styles/cleanup.css"></style>
<style scoped src="./styles/progress.css"></style>
