<template>
  <section class="lernraum-panel" :class="{ 'lernraum-panel--focus': learning || focusEditorOpen, 'lernraum-panel--nq': learning || focusEditorOpen }">
    <!-- Der Lernmodus ist eine eigene, ruhige Ebene statt eines Overlays über der Navigation. -->
    <div v-if="learning" class="lr-focus lr-learning-focus" :class="{ 'lr-learning-focus--exit-warning': learnExitWarningOpen }">
      <Transition name="lr-exit-backdrop">
        <button
          v-if="learnExitWarningOpen"
          type="button"
          class="lr-learn-exit-backdrop"
          aria-label="Warnung schließen und weiterlernen"
          @click="learnExitWarningOpen = false"
        ></button>
      </Transition>
      <header class="lr-nq-head lr-learn-head">
        <div class="lr-learn-exit-wrap">
          <button
            type="button"
            class="lr-focus-exit"
            :aria-expanded="learnExitWarningOpen"
            aria-controls="learn-exit-warning"
            @click="requestExitLearning"
          >
            <span aria-hidden="true">←</span>
            <span>Beenden</span>
          </button>
          <Transition name="lr-exit-warning">
            <div v-if="learnExitWarningOpen" id="learn-exit-warning" class="lr-learn-exit-warning lr-learn-exit-options" role="alert">
              <div class="lr-start-heading">
                <span class="lr-start-heading-icon" aria-hidden="true"><v-icon size="20">mdi-pause-circle-outline</v-icon></span>
                <div><strong>Lerndurchlauf beenden?</strong><p>Du kannst noch weiterlernen.</p></div>
              </div>
              <div class="lr-exit-summary">
                <span class="lr-exit-remaining">{{ remainingLearnCount }} {{ remainingLearnCount === 1 ? 'Karte ist' : 'Karten sind' }} noch offen</span>
                <p>Deine bisherigen Einschätzungen bleiben gespeichert.</p>
              </div>
              <div class="lr-learn-exit-actions">
                <button type="button" class="lr-learn-exit-cancel" @click="learnExitWarningOpen = false">Weiterlernen</button>
                <button type="button" class="lr-learn-exit-confirm" @click="exitLearning">Beenden</button>
              </div>
            </div>
          </Transition>
        </div>
        <div class="lr-nq-title">
          <strong>{{ openSheet?.title || store.activeCourse?.title || 'Lernmodus' }}</strong>
          <span class="lr-nq-sub">
            <span v-if="openSheet" class="lr-nq-course">{{ store.activeCourse?.title || 'Kurs' }}</span>
            <span v-if="openSheet" aria-hidden="true">·</span>
            <span v-if="currentLearn">Karte {{ learnIndex + 1 }} von {{ learnQueue.length }}</span>
            <span v-else>{{ learnQueue.length }} Karten bearbeitet</span>
          </span>
        </div>
        <div
          class="lr-learn-progress-ring"
          :class="{ 'lr-learn-progress-ring--pulse': learnProgressPulse }"
          role="progressbar"
          :aria-valuenow="assessedLearnCount"
          aria-valuemin="0"
          :aria-valuemax="learnQueue.length"
          :aria-label="`${assessedLearnCount} von ${learnQueue.length} Karten eingeschätzt`"
          :title="`${assessedLearnCount} von ${learnQueue.length} Karten eingeschätzt`"
          :style="{ '--learn-progress': `${learnCompletion}%` }"
        >
          <span>{{ assessedLearnCount }}</span>
        </div>
      </header>

      <main class="lr-focus-stage">
        <div v-if="!currentLearn" class="lr-confetti" aria-hidden="true">
          <i v-for="piece in confettiPieces" :key="piece.id" :style="piece.style"></i>
        </div>
        <!-- Schrittfolge: Reihenfolge ordnen (Prozess/Anleitung) -->
        <article v-if="currentLearn && currentLearnFormat === 'sequence'" class="lr-focus-card lr-focus-card--seq">
          <div class="lr-focus-card-meta">
            <span class="lr-kind-chip lr-kind-chip--lg" :style="kindChipStyle(currentLearn.kind)">{{ kindLabel(currentLearn.kind) }}</span>
            <span
              v-if="currentLearn.sessionAssessment"
              class="lr-learn-answered"
              :class="`lr-learn-answered--${currentLearn.sessionAssessment}`"
            >{{ assessmentLabel(currentLearn.sessionAssessment) }}</span>
          </div>
          <div class="lr-learn-front">{{ currentLearn.front }}</div>
          <p class="lr-seq-instruction">
            <template v-if="currentLearn.seqChecked">{{ seqAllCorrect ? 'Alles richtig geordnet.' : `${seqCorrectCount} von ${currentLearn.seqItems.length} an der richtigen Stelle.` }}</template>
            <template v-else>Bring die Schritte mit ↑ ↓ in die richtige Reihenfolge.</template>
          </p>
          <ol class="lr-seq-list" :class="{ 'lr-seq-list--checked': currentLearn.seqChecked }">
            <li
              v-for="(item, i) in currentLearn.seqItems"
              :key="item.idx"
              class="lr-seq-item"
              :class="currentLearn.seqChecked ? (item.idx === i ? 'lr-seq-item--ok' : 'lr-seq-item--bad') : ''"
            >
              <span class="lr-seq-pos">{{ i + 1 }}</span>
              <span class="lr-seq-text">{{ item.text }}</span>
              <span v-if="currentLearn.seqChecked && item.idx !== i" class="lr-seq-hintpos">richtig: {{ item.idx + 1 }}</span>
              <span v-if="!currentLearn.seqChecked" class="lr-seq-moves">
                <button type="button" class="lr-seq-move" :disabled="i === 0" aria-label="Schritt nach oben" @click="moveSeq(i, -1)">↑</button>
                <button type="button" class="lr-seq-move" :disabled="i === currentLearn.seqItems.length - 1" aria-label="Schritt nach unten" @click="moveSeq(i, 1)">↓</button>
              </span>
            </li>
          </ol>
          <div v-if="!currentLearn.seqChecked" class="lr-learn-actions">
            <button type="button" class="lr-btn lr-btn--primary lr-btn--learn" @click="checkSeq">Prüfen</button>
          </div>
          <div v-else class="lr-learn-assessment">
            <p class="lr-learn-selfhint">Wie sicher war deine Reihenfolge?</p>
            <div class="lr-learn-actions">
              <button type="button" class="lr-assess lr-assess--weak" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'weak' }" @click="assess('weak')"><span>Nicht gekonnt</span><kbd>1</kbd></button>
              <button type="button" class="lr-assess lr-assess--medium" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'medium' }" @click="assess('medium')"><span>Mit Mühe</span><kbd>2</kbd></button>
              <button type="button" class="lr-assess lr-assess--strong" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'strong' }" @click="assess('strong')"><span>Sicher</span><kbd>3</kbd></button>
            </div>
          </div>
          <div class="lr-learn-card-nav" aria-label="Kartennavigation">
            <button type="button" class="lr-nq-arrow" :disabled="learnIndex === 0" aria-label="Vorherige Karte" @click="moveLearn(-1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6 8.5 12l6 6" /></svg></button>
            <button type="button" class="lr-nq-arrow" :disabled="learnIndex >= learnQueue.length - 1" aria-label="Nächste Karte" @click="moveLearn(1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6" /></svg></button>
          </div>
        </article>

        <article v-else-if="currentLearn" class="lr-focus-card" :class="{ 'lr-focus-card--revealed': revealed }" :style="!revealed ? { width: `${learnFrontWidth}px` } : null">
          <div class="lr-focus-card-inner">
            <section class="lr-focus-card-face lr-focus-card-face--front" :aria-hidden="revealed" :inert="revealed">
              <div class="lr-focus-card-meta">
                <span class="lr-kind-chip lr-kind-chip--lg" :style="kindChipStyle(currentLearn.kind)">{{ kindLabel(currentLearn.kind) }}</span>
                <span
                  v-if="currentLearn.sessionAssessment"
                  class="lr-learn-answered"
                  :class="`lr-learn-answered--${currentLearn.sessionAssessment}`"
                  :aria-label="`Einschätzung: ${assessmentLabel(currentLearn.sessionAssessment)}`"
                  :title="`Einschätzung: ${assessmentLabel(currentLearn.sessionAssessment)}`"
                >{{ assessmentLabel(currentLearn.sessionAssessment) }}</span>
              </div>
              <div class="lr-learn-front">{{ currentLearn.front }}</div>
              <button type="button" class="lr-learn-hint-link" :disabled="currentLearn.hintBusy" @click="toggleLearnHint">
                <PmActionIcon name="sparkle" :size="14" />
                <span>{{ currentLearn.hintVisible ? 'Hinweis ausblenden' : 'Hinweis anzeigen' }}</span>
              </button>
              <Transition name="lr-learn-hint-reveal">
                <div v-if="currentLearn.hintVisible" class="lr-learn-hint-shell">
                  <div class="lr-learn-hint" role="status">
                    <p v-if="currentLearn.hintBusy">Die lokale KI formuliert einen Denkanstoß …</p>
                    <p v-else-if="currentLearn.hintError" class="lr-learn-hint-error">{{ currentLearn.hintError }}</p>
                    <p v-else>{{ currentLearn.aiHint }}</p>
                  </div>
                </div>
              </Transition>
              <div class="lr-learn-actions">
                <button type="button" class="lr-btn lr-btn--primary lr-btn--learn" @click="revealed = true">Antwort aufdecken</button>
              </div>
              <div class="lr-learn-card-nav" aria-label="Kartennavigation">
                <button type="button" class="lr-nq-arrow" :disabled="learnIndex === 0" aria-label="Vorherige Karte" @click="moveLearn(-1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6 8.5 12l6 6" /></svg></button>
                <button type="button" class="lr-nq-arrow" :disabled="learnIndex >= learnQueue.length - 1" aria-label="Nächste Karte" @click="moveLearn(1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6" /></svg></button>
              </div>
            </section>

            <section class="lr-focus-card-face lr-focus-card-face--back" :aria-hidden="!revealed" :inert="!revealed">
              <div class="lr-focus-card-meta">
                <button type="button" class="lr-learn-flip-back" @click="revealed = false">
                  <span aria-hidden="true">←</span>
                  <span>Zur Frage</span>
                </button>
                <span class="lr-kind-chip lr-kind-chip--lg" :style="kindChipStyle(currentLearn.kind)">{{ kindLabel(currentLearn.kind) }}</span>
              </div>
              <div class="lr-learn-question-label">Frage</div>
              <div class="lr-learn-front">{{ currentLearn.front }}</div>
              <div class="lr-learn-back">
                <div class="lr-learn-back-label">{{ currentLearn.back ? 'Antwort' : 'Zum Abgleich' }}</div>
                <div class="lr-learn-back-text">{{ currentLearn.back || 'Formuliere frei und gleiche deine Antwort anschließend mit der Notiz ab.' }}</div>
              </div>
              <div class="lr-learn-assessment">
                <p class="lr-learn-selfhint">Wie gut konntest du die Antwort ohne Hilfe?</p>
                <div class="lr-learn-actions">
                  <button type="button" class="lr-assess lr-assess--weak" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'weak' }" :aria-pressed="currentLearn.sessionAssessment === 'weak'" @click="assess('weak')"><span>Nicht gekonnt</span><kbd>1</kbd></button>
                  <button type="button" class="lr-assess lr-assess--medium" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'medium' }" :aria-pressed="currentLearn.sessionAssessment === 'medium'" @click="assess('medium')"><span>Mit Mühe</span><kbd>2</kbd></button>
                  <button type="button" class="lr-assess lr-assess--strong" :class="{ 'lr-assess--selected': currentLearn.sessionAssessment === 'strong' }" :aria-pressed="currentLearn.sessionAssessment === 'strong'" @click="assess('strong')"><span>Sicher</span><kbd>3</kbd></button>
                </div>
              </div>
              <div class="lr-learn-card-nav" aria-label="Kartennavigation">
                <button type="button" class="lr-nq-arrow" :disabled="learnIndex === 0" aria-label="Vorherige Karte" @click="moveLearn(-1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6 8.5 12l6 6" /></svg></button>
                <button type="button" class="lr-nq-arrow" :disabled="learnIndex >= learnQueue.length - 1" aria-label="Nächste Karte" @click="moveLearn(1)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6" /></svg></button>
              </div>
            </section>
          </div>
        </article>

        <section v-else class="lr-learn-done" :style="{ '--done-score': learnScore, '--done-offset': 100 - learnScore }">
          <div class="lr-done-orbit" role="img" :aria-label="`${learnScore} Prozent Lernsicherheit`">
            <svg viewBox="0 0 100 100" aria-hidden="true">
              <circle class="lr-done-orbit-track" cx="50" cy="50" r="43" pathLength="100" />
              <circle class="lr-done-orbit-value" cx="50" cy="50" r="43" pathLength="100" />
            </svg>
            <div class="lr-done-orbit-copy"><strong>{{ learnScore }}%</strong><span>Lernsicherheit</span></div>
          </div>
          <div class="lr-learn-done-title">Durchlauf abgeschlossen</div>
          <p>{{ learnQueue.length }} von {{ learnQueue.length }} Karten bearbeitet</p>
          <div class="lr-done-results" aria-label="Ergebnis des Lerndurchlaufs">
            <div v-for="result in learnResultRows" :key="result.key" class="lr-done-result-row" :class="`lr-done-result-row--${result.key}`">
              <div class="lr-done-result-label"><i class="lr-result-dot" :class="`lr-result-dot--${result.key}`"></i><span>{{ result.label }}</span><strong>{{ result.count }}</strong></div>
              <div class="lr-done-result-track"><i :style="{ width: `${result.percent}%` }"></i></div>
            </div>
          </div>
          <div class="lr-done-actions">
            <button type="button" class="lr-btn lr-btn--primary lr-btn--md" @click="exitLearning">Zurück zu {{ openSheet ? '„' + openSheet.title + '“' : '„' + store.activeCourse?.title + '“' }}</button>
            <button type="button" class="lr-done-restart" @click="restartLearning">Erneut lernen</button>
          </div>
        </section>
      </main>
    </div>

    <!-- Nachbereiten und Kartenbearbeitung nutzen dieselbe Fokusoberfläche. -->
    <div v-else-if="focusEditorOpen" class="lr-focus lr-nq" :style="{ '--nq-tint': nqTint }">
      <header class="lr-nq-head">
        <button type="button" class="lr-focus-exit" @click="closeFocusEditor">
          <span aria-hidden="true">←</span>
          <span>Beenden</span>
        </button>
        <div class="lr-nq-title">
          <strong>{{ cardEditorOpen ? (openSheet?.title || 'Lernblatt') : (current?.noteTitle || 'Ohne Titel') }}</strong>
          <span class="lr-nq-sub">
            <span v-if="cardEditorOpen">Karte {{ dialog.index + 1 }} von {{ dialog.items.length }}</span>
            <span v-else>Markierung {{ dialog.index + 1 }} von {{ dialog.items.length }}<template v-if="queueDone"> · {{ queueDone }} übernommen</template></span>
          </span>
        </div>
        <div class="lr-nq-nav">
          <button type="button" class="lr-nq-arrow" :disabled="dialog.index === 0" :aria-label="cardEditorOpen ? 'Vorherige Karte' : 'Vorherige Markierung'" @click="focusEditorPrev"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 6 8.5 12l6 6" /></svg></button>
          <button type="button" class="lr-nq-arrow" :disabled="dialog.index >= dialog.items.length - 1" :aria-label="cardEditorOpen ? 'Nächste Karte' : 'Nächste Markierung'" @click="focusEditorNext"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6" /></svg></button>
        </div>
      </header>

      <div class="lr-nq-body" :class="{ 'lr-nq-body--solo': !current?.noteId }">
        <section v-if="current?.noteId" class="lr-nq-source" aria-label="Ursprüngliche Notiz">
          <button
            type="button"
            class="lr-nq-note-theme-toggle"
            :aria-pressed="notePreviewTheme === 'dark'"
            :aria-label="notePreviewTheme === 'dark' ? 'Helle Notizansicht aktivieren' : 'Dunkle Notizansicht aktivieren'"
            :title="notePreviewTheme === 'dark' ? 'Helle Ansicht' : 'Dunkle Ansicht'"
            @click="toggleNotePreviewTheme"
          >
            <v-icon size="19">{{ notePreviewTheme === 'dark' ? 'mdi-weather-sunny' : 'mdi-weather-night' }}</v-icon>
          </button>
          <div class="lr-nq-paper" :class="`lr-nq-paper--${notePreviewTheme}`">
            <NotePreview
              :note-id="current?.noteId || null"
              compact
              :theme="notePreviewTheme"
              :marker-states="editorMarkerStates"
              :current-pm-id="current?.marker.node_pm_id || null"
              @select-marker="onSelectMarker"
            />
          </div>
        </section>

        <section v-if="current" class="lr-nq-work" :class="{ 'lr-nq-work--seq': currentIsSequence }" aria-label="Karte">
          <div class="lr-nq-meta">
            <div v-if="!cardEditorOpen" class="lr-nq-field">
              <span class="lr-nq-label">Kurs</span>
              <div class="lr-kind-picker" role="group" aria-label="Kurs auswählen">
                <button
                  v-for="c in store.courses"
                  :key="c.id"
                  type="button"
                  class="lr-kind-opt"
                  :class="{ 'lr-kind-opt--on': current.courseId === c.id }"
                  :aria-pressed="current.courseId === c.id"
                  @click="current.courseId = c.id"
                >{{ c.title }}</button>
              </div>
            </div>
            <div class="lr-nq-field">
              <div class="lr-nq-label-row">
                <span class="lr-nq-label">Art</span>
                <button type="button" class="lr-nq-ai" :disabled="!!nqAiBusy || current.kindAiBusy" aria-label="Art mit KI bestimmen" @click="generateQueueKind">
                  <PmActionIcon name="sparkle" :size="14" />{{ current.kindAiBusy ? 'Prüft …' : 'KI' }}
                </button>
              </div>
              <div class="lr-kind-picker">
                <button v-for="k in cardKinds" :key="k.value" type="button" class="lr-kind-opt" :class="{ 'lr-kind-opt--on': current.cardKind === k.value }" @click="selectQueueKind(k.value)">{{ k.label }}</button>
              </div>
            </div>
          </div>

          <div class="lr-nq-field lr-nq-field--editor lr-nq-field--question">
            <div class="lr-nq-label-row">
              <label class="lr-nq-label" for="lr-nq-front">Frage</label>
              <button type="button" class="lr-nq-ai" :disabled="!!nqAiBusy || current.kindAiBusy" aria-label="Frage mit KI formulieren" @click="generateQueueField('front')">
                <PmActionIcon name="sparkle" :size="14" />{{ nqAiBusy === 'front' ? 'Erstellt …' : 'KI' }}
              </button>
            </div>
            <textarea id="lr-nq-front" ref="nqFront" v-model="current.front" class="lr-field lr-field--area lr-nq-area" rows="3" placeholder="Formuliere die Frage, die dich zur Antwort bringt …" @input="fitNqFront($event.currentTarget)"></textarea>
          </div>

          <!-- Flip-Karte: Antwort. Schrittfolge: geordnete Schritte. -->
          <template v-if="!currentIsSequence">
            <button type="button" class="lr-nq-swap" title="Vertauscht den Inhalt von Frage und Antwort" @click="swapSides">
              <span aria-hidden="true">⇅</span> Frage &amp; Antwort tauschen
            </button>

            <div class="lr-nq-field lr-nq-field--editor lr-nq-field--answer">
              <div class="lr-nq-label-row">
                <label class="lr-nq-label" for="lr-nq-back">
                  <span>Antwort</span>
                  <span v-if="cardEditorOpen || current.fromNote !== 'back'" class="lr-nq-opt">optional · leer = Selbstabgleich</span>
                </label>
                <button type="button" class="lr-nq-ai" :disabled="!!nqAiBusy || current.kindAiBusy" aria-label="Antwort mit KI formulieren" @click="generateQueueField('back')">
                  <PmActionIcon name="sparkle" :size="14" />{{ nqAiBusy === 'back' ? 'Erstellt …' : 'KI' }}
                </button>
              </div>
              <textarea id="lr-nq-back" ref="nqBack" v-model="current.back" class="lr-field lr-field--area lr-nq-area" rows="1" placeholder="Die Antwort in deinen Worten …" @input="fitNqBack($event.currentTarget)"></textarea>
            </div>
          </template>

          <div v-else class="lr-nq-field lr-nq-field--editor lr-nq-steps">
            <div class="lr-nq-label-row">
              <label class="lr-nq-label"><span>Schritte</span><span class="lr-nq-opt">in richtiger Reihenfolge</span></label>
              <button type="button" class="lr-nq-ai" :disabled="!!nqAiBusy || current.kindAiBusy" aria-label="Schritte mit KI aus der Notiz" @click="generateQueueSteps">
                <PmActionIcon name="sparkle" :size="14" />{{ nqAiBusy === 'steps' ? 'Erstellt …' : 'KI' }}
              </button>
            </div>
            <ol class="lr-steps-list">
              <li v-for="(step, i) in current.steps" :key="i" class="lr-steps-row">
                <span class="lr-steps-num">{{ i + 1 }}</span>
                <input
                  class="lr-field lr-steps-input"
                  :value="step"
                  :placeholder="`Schritt ${i + 1}`"
                  @input="current.steps[i] = $event.target.value"
                  @keydown.enter.prevent="addStep(i + 1)"
                />
                <button type="button" class="lr-steps-move" :disabled="i === 0" aria-label="Schritt nach oben" @click="moveStep(i, -1)">↑</button>
                <button type="button" class="lr-steps-move" :disabled="i === current.steps.length - 1" aria-label="Schritt nach unten" @click="moveStep(i, 1)">↓</button>
                <button type="button" class="lr-steps-del" aria-label="Schritt entfernen" @click="removeStep(i)">✕</button>
              </li>
            </ol>
            <button type="button" class="lr-steps-add" @click="addStep()">+ Schritt</button>
            <p class="lr-steps-hint">Mindestens zwei Schritte. Beim Lernen werden sie gemischt und du bringst sie in die richtige Reihenfolge.</p>
          </div>

          <div class="lr-nq-actions">
            <span v-if="dialogError" class="lr-nq-error" role="alert">{{ dialogError }}</span>
            <v-btn class="lr-action-button lr-nq-submit" variant="flat" :loading="dialogBusy" :disabled="dialogBusy" @click="cardEditorOpen ? saveCurrentCard() : acceptCurrent()">
              <v-icon size="18" class="mr-1" aria-hidden="true">mdi-check</v-icon>
              {{ cardEditorOpen ? 'Änderungen speichern' : (lastOpen ? 'Fertig' : 'Übernehmen') }}
            </v-btn>
          </div>
        </section>
      </div>
    </div>

    <template v-else>
      <div class="lr-head">
      <nav v-if="store.courses.length" class="lr-crumbs" aria-label="Pfad">
        <template v-for="(c, i) in crumbs" :key="i">
          <span v-if="i" class="lr-crumb-sep" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6" /></svg></span>
          <span v-if="c.current" class="lr-crumb lr-crumb--current" aria-current="page">{{ c.label }}</span>
          <button v-else type="button" class="lr-crumb" @click="c.go">{{ c.label }}</button>
        </template>
      </nav>

      <!-- Der Seitenkopf gehört zur Seite und scrollt mit. -->
      <header v-if="store.courses.length" class="lr-pagehead">
        <div class="lr-pagehead-main">
          <div class="lr-title-block">
            <h1 class="lr-title">
            <input
              v-if="editingCourseTitle"
              ref="courseTitleInput"
              v-model="courseTitleDraft"
              class="lr-title-input"
              :size="Math.max(6, Math.min(32, courseTitleDraft.length || 6))"
              aria-label="Kursname"
              :disabled="courseTitleBusy"
              @keydown.enter.prevent="saveCourseTitle"
              @keydown.esc.prevent="cancelCourseTitle"
              @blur="saveCourseTitle"
            />
            <input
              v-else-if="openSheet && editingSheetId === openSheet.id"
              v-model="sheetTitleDraft"
              class="lr-title-input"
              :size="Math.max(6, Math.min(32, sheetTitleDraft.length || 6))"
              aria-label="Lernblattname"
              :disabled="sheetTitleBusy"
              @keydown.enter.prevent="saveSheetTitle"
              @keydown.esc.prevent="cancelSheetTitle"
              @blur="saveSheetTitle"
            />
            <button
              v-else-if="view === 'course' && store.activeCourse && !openSheet"
              type="button"
              class="lr-title-edit"
              title="Kurs umbenennen"
              @click="editCourseTitle"
            >{{ pageTitle }}<span aria-hidden="true">✎</span></button>
            <button
              v-else-if="openSheet"
              type="button"
              class="lr-title-edit"
              title="Lernblatt umbenennen"
              @click="onRenameSheet(openSheet)"
            >{{ pageTitle }}<span aria-hidden="true">✎</span></button>
            <template v-else>{{ pageTitle }}</template>
            </h1>
            <span v-if="courseTitleError || (openSheet && sheetTitleError)" class="lr-title-error" role="alert">{{ courseTitleError || sheetTitleError }}</span>
            <p v-else class="lr-subtitle">{{ pageSubtitle }}</p>
          </div>
        </div>
      </header>

      <div
        v-if="store.courses.length && !openSheet"
        class="lr-header-progress"
        :title="`${pct(headerProficiency, 'strong')} % sicher · ${pct(headerProficiency, 'medium')} % mit Mühe · ${pct(headerProficiency, 'weak')} % offen · ${pct(headerProficiency, 'open')} % neu`"
      >
        <div class="lr-header-progress-label"><strong>{{ pct(headerProficiency, 'strong') }} %</strong> sicher</div>
        <div
          class="lr-progress-band"
          :class="{ 'lr-progress-band--updated': progressFeedbackActive }"
          role="img"
          :aria-label="(view === 'home' ? 'Gesamter Lernfortschritt: ' : 'Lernfortschritt des Kurses: ') + pct(headerProficiency, 'strong') + ' Prozent sicher'"
        >
          <span
            v-for="seg in barSegments(headerProficiency)"
            :key="seg.key"
            class="lr-progress-band-segment"
            :style="{ width: seg.pct + '%', background: seg.color }"
          ></span>
        </div>
      </div>
      <div v-if="openSheet" class="lr-head-actions">
        <button type="button" class="lr-favorite-toggle" :class="{ 'lr-favorite-toggle--on': openSheet.is_favorite || favoriteAnimating }" :aria-pressed="openSheet.is_favorite" :aria-label="openSheet.is_favorite ? 'Favorit entfernen' : 'Als Favorit markieren'" :disabled="favoriteBusy" @click="toggleFavorite(openSheet)">
          <span class="lr-favorite-icon-wrap" :class="{ 'lr-favorite-icon-wrap--pop': favoriteAnimating }" aria-hidden="true">
            <span class="lr-favorite-icon">{{ openSheet.is_favorite || favoriteAnimating ? '★' : '☆' }}</span>
          </span>
          <span>Favorit</span>
        </button>
        <v-menu v-model="learnStartOptionsOpen" class="lr-learn-start-overlay" :scrim="true" :close-on-content-click="false" location="bottom end" :offset="12">
          <template #activator="{ props }">
        <v-btn class="lr-action-button lr-head-action" variant="flat" :disabled="!learnableCards.length" :title="cards.length && !learnableCards.length ? 'Zum Lernen müssen Vorder- und Rückseite ausgefüllt sein.' : ''" v-bind="props">
          <v-icon size="18" class="mr-1" aria-hidden="true">mdi-arrow-right</v-icon>
          Jetzt lernen
        </v-btn>
          </template>
          <div class="lernraum-panel lr-learn-start-panel">
            <div class="lr-learn-exit-warning lr-learn-start-options">
              <div class="lr-start-heading">
                <span class="lr-start-heading-icon" aria-hidden="true"><v-icon size="20">mdi-school-outline</v-icon></span>
                <div><strong>Dein Lerndurchlauf</strong><p>Wie möchtest du die Karten durchgehen?</p></div>
              </div>
              <fieldset>
                <legend>Reihenfolge</legend>
                <label class="lr-start-choice" :class="{ 'lr-start-choice--selected': learnOrder === 'original' }">
                  <input v-model="learnOrder" type="radio" value="original" name="learn-order">
                  <span><b>Wie im Lernblatt</b><small>In der vertrauten Reihenfolge lernen.</small></span>
                </label>
                <label class="lr-start-choice" :class="{ 'lr-start-choice--selected': learnOrder === 'random' }">
                  <input v-model="learnOrder" type="radio" value="random" name="learn-order">
                  <span><b>Zufällig gemischt</b><small>Mit einer neuen Reihenfolge starten.</small></span>
                </label>
                <label class="lr-start-choice" :class="{ 'lr-start-choice--selected': learnOrder === 'difficult' }">
                  <input v-model="learnOrder" type="radio" value="difficult" name="learn-order">
                  <span><b>Schwierige Karten zuerst</b><small>Unsichere und neue Karten zuerst üben.</small></span>
                </label>
              </fieldset>
              <div class="lr-start-footer">
                <span>{{ learnableCards.length }} {{ learnableCards.length === 1 ? 'Karte' : 'Karten' }} · Auswahl wird gemerkt</span>
                <button type="button" class="lr-start-submit" @click="startLearning">Lernen starten <v-icon size="18" aria-hidden="true">mdi-arrow-right</v-icon></button>
              </div>
            </div>
          </div>
        </v-menu>
      </div>
      </div>

      <div class="lr-scroll">


      <!-- Leerer Lernraum -->
      <div v-if="!store.courses.length && !store.loadingCourses" class="lr-empty">
        <div class="lr-empty-hero">
          <div class="lr-empty-visual" aria-hidden="true">
            <span class="lr-empty-card lr-empty-card--left"><i>?</i><b></b><b></b></span>
            <span class="lr-empty-card lr-empty-card--right"><i>✓</i><b></b><b></b></span>
            <span class="lr-empty-card lr-empty-card--front"><i>?</i><b></b><b></b><b></b></span>
            <span class="lr-empty-plus"><v-icon size="20">mdi-plus</v-icon></span>
          </div>
          <h2 class="lr-empty-title">Kein Kurs angelegt</h2>
          <div class="lr-empty-body">Lege einen Kurs an. Darin sammelst du Lernblätter, Karten und offene Nachbereitungen an einem Ort.</div>
          <button type="button" class="lr-empty-action" @click="onCreateCourse">
            <v-icon size="20">mdi-plus</v-icon>
            <span>Neuer Kurs</span>
          </button>
        </div>
      </div>

      <!-- Startseite: Aufgaben und Kurse, ohne aufklappbare Unter-Navigation. -->
      <main v-else-if="view === 'home'" class="lr-page">
        <section v-if="markerTasks.length" class="lr-section">
          <div class="lr-section-head">
            <div>
              <span class="lr-overline">Als Nächstes</span>
              <h2>Offene Nachbereitungen</h2>
            </div>
            <span class="lr-section-meta">{{ store.openMarkers.length }} {{ store.openMarkers.length === 1 ? 'Markierung' : 'Markierungen' }} · etwa {{ estMinutes(store.openMarkers.length) }} Min.</span>
          </div>
          <div class="lr-task-list">
            <article
              v-for="task in markerTasks"
              :key="task.marker.id"
              class="lr-task"
              role="button"
              tabindex="0"
              :aria-label="`Markierung aus „${task.group.sessionTitle || task.group.noteTitle || 'Ohne Titel'}“ nachbereiten`"
              @click="openQueue(task.group, task.markerIndex)"
              @keydown.enter.self="openQueue(task.group, task.markerIndex)"
              @keydown.space.self.prevent="openQueue(task.group, task.markerIndex)"
            >
              <div class="lr-task-icon" aria-hidden="true">↗</div>
              <div class="lr-task-copy">
                <span>{{ task.marker.course_title || 'Noch keinem Kurs zugeordnet' }}</span>
                <strong>{{ task.group.sessionTitle || task.group.noteTitle || 'Ohne Titel' }}</strong>
                <p class="lr-task-preview">{{ task.marker.snippet || 'Keine Textvorschau verfügbar' }}</p>
                <small>1 Markierung · {{ markerKindLabel(task.marker.kind) }}</small>
              </div>
              <button type="button" class="lr-btn lr-btn--secondary lr-btn--sm lr-task-action" @click.stop="openQueue(task.group, task.markerIndex)">Nachbereiten</button>
            </article>
          </div>
        </section>

        <section class="lr-section">
          <div class="lr-section-head">
            <div>
              <span class="lr-overline">Bibliothek</span>
              <h2>Deine Kurse</h2>
            </div>
            <span class="lr-section-meta">Kurs öffnen, Material wählen, lernen.</span>
          </div>
          <span v-if="courseCardTitleError && !editingCourseCardId" class="lr-title-error" role="alert">{{ courseCardTitleError }}</span>
          <div class="lr-course-grid">
            <article
              v-for="course in store.courses"
              :key="course.id"
              class="lr-course-card lr-sheet-tile"
              role="button"
              tabindex="0"
              :aria-label="`Kurs „${course.title}“ öffnen`"
              @click="openCourse(course.id)"
              @keydown.enter.self="openCourse(course.id)"
              @keydown.space.self.prevent="openCourse(course.id)"
            >
              <div class="lr-course-card-top">
                <span class="lr-course-monogram">{{ courseMonogram(course.title) }}</span>
                <div class="lr-sheet-tile-tools" @click.stop>
                  <button type="button" class="lr-icon-btn" :aria-label="`„${course.title}“ umbenennen`" title="Umbenennen" @click="onRenameCourseCard(course)">✎</button>
                  <button type="button" class="lr-icon-btn lr-icon-btn--danger" :aria-label="`„${course.title}“ löschen`" title="Löschen" :disabled="deletingCourseIds.has(course.id)" @click="onDeleteCourse(course)">✕</button>
                </div>
              </div>
              <input
                v-if="editingCourseCardId === course.id"
                v-model="courseCardTitleDraft"
                class="lr-sheet-title-input"
                aria-label="Kursname in der Kachel"
                :disabled="courseCardTitleBusy"
                @click.stop
                @keydown.enter.prevent="saveCourseCardTitle"
                @keydown.esc.prevent="cancelCourseCardTitle"
                @blur="saveCourseCardTitle"
              />
              <div v-else class="lr-course-name">{{ course.title }}</div>
              <span v-if="editingCourseCardId === course.id && courseCardTitleError" class="lr-title-error" role="alert">{{ courseCardTitleError }}</span>
              <div class="lr-course-meta">{{ courseSub(course) }}</div>
              <div class="lr-course-progress">
                <div class="lr-bar" :class="{ 'lr-bar--empty': !course.card_count, 'lr-bar--updated': progressFeedbackActive }">
                  <span v-for="seg in barSegments(course.proficiency)" :key="seg.key" class="lr-bar-seg" :style="{ width: seg.pct + '%', background: seg.color }"></span>
                </div>
                <span>{{ course.card_count ? strongPct(course.proficiency) + ' % sicher' : 'Noch keine Karten' }}</span>
              </div>
            </article>
            <button type="button" class="lr-course-card lr-course-card--add" @click="onCreateCourse">
              <span class="lr-course-add-icon" aria-hidden="true">+</span>
              <strong>Neuen Kurs anlegen</strong>
              <small>Organisiere deine Lernblätter an einem Ort.</small>
            </button>
          </div>
        </section>

        <section v-if="favoriteSheets.length" class="lr-section" aria-labelledby="lr-favorites-title">
          <div class="lr-section-head">
            <div>
              <span class="lr-overline">Schnellzugriff</span>
              <h2 id="lr-favorites-title">Favoriten</h2>
            </div>
            <span class="lr-section-meta">{{ favoriteSheets.length }} {{ favoriteSheets.length === 1 ? 'Lernblatt' : 'Lernblätter' }}</span>
          </div>
          <div class="lr-course-grid lr-sheet-grid">
            <article
              v-for="sheet in favoriteSheets"
              :key="sheet.id"
              class="lr-course-card lr-sheet-tile lr-favorite-sheet-card"
              role="button"
              tabindex="0"
              :aria-label="`Favorisiertes Lernblatt „${sheet.title}“ öffnen`"
              @click="openFavoriteSheet(sheet)"
              @keydown.enter.self="openFavoriteSheet(sheet)"
              @keydown.space.self.prevent="openFavoriteSheet(sheet)"
            >
              <div class="lr-course-card-top">
                <span class="lr-course-monogram">{{ courseMonogram(sheet.title) }}</span>
                <span class="lr-favorite-sheet-star" aria-label="Favorit">★</span>
              </div>
              <span class="lr-favorite-sheet-course">{{ sheet.courseTitle }}</span>
              <div class="lr-course-name">{{ sheet.title }}</div>
              <div class="lr-course-meta">{{ sheet.card_count }} {{ sheet.card_count === 1 ? 'Karte' : 'Karten' }}<template v-if="sheet.kind_summary"> · {{ kindSummaryLabel(sheet.kind_summary) }}</template></div>
              <div class="lr-course-progress">
                <div class="lr-bar" :class="{ 'lr-bar--empty': !sheet.card_count, 'lr-bar--updated': progressFeedbackActive }">
                  <span v-for="seg in barSegments(sheet.proficiency)" :key="seg.key" class="lr-bar-seg" :style="{ width: seg.pct + '%', background: seg.color }"></span>
                </div>
                <span>{{ sheet.card_count ? strongPct(sheet.proficiency) + ' % sicher' : 'Noch keine Karten' }}</span>
              </div>
              <div class="lr-sheet-tile-actions" @click.stop>
                <button type="button" class="lr-btn lr-btn--primary lr-btn--sm" :disabled="!sheetLearnableCount(sheet)" :title="sheet.card_count && !sheetLearnableCount(sheet) ? 'Zum Lernen müssen Vorder- und Rückseite ausgefüllt sein.' : ''" @click="startSheetLearn(sheet)">Jetzt lernen</button>
                <button type="button" class="lr-link" @click="openFavoriteSheet(sheet)">Öffnen <span aria-hidden="true">→</span></button>
              </div>
            </article>
          </div>
        </section>
      </main>

      <!-- Kurs: Nachbereitung ist ein Abschnitt, kein konkurrierender Navigationsmodus. -->
      <main v-else-if="store.activeCourse && !openSheet" class="lr-page lr-course-page" :class="{ 'lr-course-page--empty': !courseSheets.length }">
        <div v-if="!courseSheets.length" class="lr-course-empty-page">
          <div class="lr-empty-hero">
            <div class="lr-empty-visual" aria-hidden="true">
              <span class="lr-empty-card lr-empty-card--left"><i>?</i><b></b><b></b></span>
              <span class="lr-empty-card lr-empty-card--right"><i>✓</i><b></b><b></b></span>
              <span class="lr-empty-card lr-empty-card--front"><i>?</i><b></b><b></b><b></b></span>
              <span class="lr-empty-plus"><v-icon size="20">mdi-plus</v-icon></span>
            </div>
            <h2 class="lr-empty-title">Dieser Kurs ist noch leer</h2>
            <div class="lr-empty-body">Lege ein Lernblatt an. Darin sammelst du Karten und behältst deinen Lernfortschritt im Blick.</div>
            <button type="button" class="lr-empty-action" @click="onCreateSheet">
              <v-icon size="20">mdi-plus</v-icon>
              <span>Erstes Lernblatt anlegen</span>
            </button>
          </div>
        </div>

        <template v-else>
        <section v-if="courseMarkerTasks.length" class="lr-section">
          <div class="lr-section-head">
            <div>
              <span class="lr-overline">Als Nächstes</span>
              <h2>Offene Nachbereitungen</h2>
            </div>
            <span class="lr-section-meta">{{ courseMarkerCount }} {{ courseMarkerCount === 1 ? 'Markierung' : 'Markierungen' }} · etwa {{ estMinutes(courseMarkerCount) }} Min.</span>
          </div>
          <div class="lr-task-list">
            <article
              v-for="task in courseMarkerTasks"
              :key="task.marker.id"
              class="lr-task"
              role="button"
              tabindex="0"
              :aria-label="`Markierung aus „${task.group.sessionTitle || task.group.noteTitle || 'Ohne Titel'}“ nachbereiten`"
              @click="openQueue(task.group, task.markerIndex)"
              @keydown.enter.self="openQueue(task.group, task.markerIndex)"
              @keydown.space.self.prevent="openQueue(task.group, task.markerIndex)"
            >
              <div class="lr-task-icon" aria-hidden="true">↗</div>
              <div class="lr-task-copy">
                <span>{{ task.marker.course_title || 'Noch keinem Kurs zugeordnet' }}</span>
                <strong>{{ task.group.sessionTitle || task.group.noteTitle || 'Ohne Titel' }}</strong>
                <p class="lr-task-preview">{{ task.marker.snippet || 'Keine Textvorschau verfügbar' }}</p>
                <small>1 Markierung · {{ markerKindLabel(task.marker.kind) }}</small>
              </div>
              <button type="button" class="lr-btn lr-btn--secondary lr-btn--sm lr-task-action" @click.stop="openQueue(task.group, task.markerIndex)">Nachbereiten</button>
            </article>
          </div>
        </section>

        <section class="lr-section">
          <div class="lr-section-head">
            <div>
              <span class="lr-overline">Lernmaterial</span>
              <h2>Lernblätter</h2>
            </div>
          </div>
          <span v-if="sheetTitleError && !editingSheetId" class="lr-title-error" role="alert">{{ sheetTitleError }}</span>

          <div class="lr-course-grid lr-sheet-grid">
            <article
              v-for="sheet in courseSheets"
              :key="sheet.id"
              class="lr-course-card lr-sheet-tile"
              role="button"
              tabindex="0"
              :aria-label="`Lernblatt „${sheet.title}“ öffnen`"
              @click="openSheetView(sheet.id)"
              @keydown.enter.self="openSheetView(sheet.id)"
              @keydown.space.self.prevent="openSheetView(sheet.id)"
            >
              <div class="lr-course-card-top">
                <span class="lr-course-monogram">{{ courseMonogram(sheet.title) }}</span>
                <div class="lr-sheet-tile-tools" @click.stop>
                  <button type="button" class="lr-icon-btn" :aria-label="`„${sheet.title}“ umbenennen`" title="Umbenennen" @click="onRenameSheet(sheet)">✎</button>
                  <button type="button" class="lr-icon-btn lr-icon-btn--danger" :aria-label="`„${sheet.title}“ löschen`" title="Löschen" :disabled="deletingSheetIds.has(sheet.id)" @click="onDeleteSheet(sheet)">✕</button>
                </div>
              </div>
              <input
                v-if="editingSheetId === sheet.id"
                v-model="sheetTitleDraft"
                class="lr-sheet-title-input"
                aria-label="Lernblattname"
                :disabled="sheetTitleBusy"
                @click.stop
                @keydown.enter.prevent="saveSheetTitle"
                @keydown.esc.prevent="cancelSheetTitle"
                @blur="saveSheetTitle"
              />
              <div v-else class="lr-course-name">{{ sheet.title }}</div>
              <span v-if="editingSheetId === sheet.id && sheetTitleError" class="lr-title-error" role="alert">{{ sheetTitleError }}</span>
              <div class="lr-course-meta">{{ sheet.card_count }} {{ sheet.card_count === 1 ? 'Karte' : 'Karten' }}<template v-if="sheet.kind_summary"> · {{ kindSummaryLabel(sheet.kind_summary) }}</template></div>
              <div class="lr-course-progress">
                <div class="lr-bar" :class="{ 'lr-bar--empty': !sheet.card_count, 'lr-bar--updated': progressFeedbackActive }">
                  <span v-for="seg in barSegments(sheet.proficiency)" :key="seg.key" class="lr-bar-seg" :style="{ width: seg.pct + '%', background: seg.color }"></span>
                </div>
                <span>{{ sheet.card_count ? strongPct(sheet.proficiency) + ' % sicher' : 'Noch keine Karten' }}</span>
              </div>
              <div class="lr-sheet-tile-actions" @click.stop>
                <button type="button" class="lr-btn lr-btn--primary lr-btn--sm" :disabled="!sheetLearnableCount(sheet)" :title="sheet.card_count && !sheetLearnableCount(sheet) ? 'Zum Lernen müssen Vorder- und Rückseite ausgefüllt sein.' : ''" @click="startSheetLearn(sheet)">Jetzt lernen</button>
                <button type="button" class="lr-link" @click="openSheetView(sheet.id)">Öffnen <span aria-hidden="true">→</span></button>
              </div>
            </article>
            <button
              type="button"
              class="lr-course-card lr-course-card--add lr-sheet-add"
              :class="{ 'lr-sheet-add--empty': !courseSheets.length }"
              @click="onCreateSheet"
            >
              <span class="lr-course-add-icon" aria-hidden="true">+</span>
              <strong>{{ courseSheets.length ? 'Neues Lernblatt' : 'Erstes Lernblatt anlegen' }}</strong>
              <small>Bündele deine Karten zu einem klaren Lernstoff.</small>
            </button>
          </div>
        </section>
        </template>
      </main>

      <!-- Lernblatt: gleiche Hierarchie und dieselbe Hauptaktion wie im Kurs. -->
      <main v-else-if="openSheet" class="lr-page lr-sheet-page" :class="{ 'lr-sheet-page--empty': !cards.length && !sheetLearningRuns.length }">
        <div v-if="!cards.length && !sheetLearningRuns.length" class="lr-sheet-empty-page">
          <div class="lr-empty-hero">
            <div class="lr-empty-visual" aria-hidden="true">
              <span class="lr-empty-card lr-empty-card--left"><i>?</i><b></b><b></b></span>
              <span class="lr-empty-card lr-empty-card--right"><i>✓</i><b></b><b></b></span>
              <span class="lr-empty-card lr-empty-card--front"><i>?</i><b></b><b></b><b></b></span>
              <span class="lr-empty-plus"><v-icon size="20">mdi-plus</v-icon></span>
            </div>
            <h2 class="lr-empty-title">Dieses Lernblatt ist noch leer</h2>
            <div class="lr-empty-body">Markiere Lerninhalte in deinen Notizen. Daraus entstehen neue Karten, die du diesem Lernblatt zuordnen und anschließend lernen kannst.</div>
          </div>
        </div>

        <template v-else>
        <section v-if="sheetLearningRuns.length" class="lr-sheet-progress" aria-labelledby="lr-sheet-history-title">
          <div class="lr-sheet-column-head">
            <div>
              <button type="button" class="lr-overline lr-progress-label-toggle" :aria-expanded="progressExpanded" aria-controls="lr-progress-content" :aria-label="progressExpanded ? 'Lernfortschritt einklappen' : 'Lernfortschritt ausklappen'" @click="progressExpanded = !progressExpanded">
                <svg viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4 3 4 3-4Z" /></svg>
                <span>Lernfortschritt</span>
              </button>
              <h2 id="lr-sheet-history-title">Deine Entwicklung</h2>
            </div>
            <span v-if="sheetLearningRuns.length" class="lr-section-meta">{{ latestRunScore }} % · {{ sheetLearningRuns.length }} {{ sheetLearningRuns.length === 1 ? 'Durchlauf' : 'Durchläufe' }}</span>
          </div>
          <Transition name="lr-progress-reveal">
            <div v-show="progressExpanded" id="lr-progress-content" class="lr-progress-content">
              <p v-if="runDeleteError" class="lr-run-error" role="alert">{{ runDeleteError }}</p>

              <div class="lr-progress-chart-card" :class="{ 'lr-progress-chart-card--intro': chartIntroSheetId === String(openSheetId) }">
            <div class="lr-progress-chart-summary">
              <div><strong>{{ latestRunScore }} %</strong><span>letzte Lernsicherheit</span></div>
              <div class="lr-progress-chart-legend" aria-label="Legende">
                <span><i class="lr-result-dot lr-result-dot--strong"></i>Sicher</span>
                <span><i class="lr-result-dot lr-result-dot--medium"></i>Mit Mühe</span>
                <span><i class="lr-result-dot lr-result-dot--weak"></i>Offen</span>
                <span><i class="lr-chart-line-key"></i>Lernsicherheit</span>
              </div>
            </div>
            <div class="lr-progress-chart-scroll">
              <svg
                class="lr-progress-chart"
                :viewBox="`0 0 ${sheetRunChartWidth} 190`"
                :style="{ width: `${sheetRunChartWidth}px` }"
                role="img"
                aria-label="Entwicklung der Lernsicherheit über die letzten Lerndurchläufe"
              >
                <g class="lr-chart-grid" aria-hidden="true">
                  <line x1="48" :x2="sheetRunChartWidth - 24" y1="16" y2="16" />
                  <line x1="48" :x2="sheetRunChartWidth - 24" y1="66" y2="66" />
                  <line x1="48" :x2="sheetRunChartWidth - 24" y1="116" y2="116" />
                  <text x="8" y="20">100 %</text><text x="15" y="70">50 %</text><text x="27" y="120">0</text>
                </g>
                <g v-for="(run, index) in sheetRunChart" :key="run.id" class="lr-chart-run" :class="{ 'lr-chart-run--paused': !run.completed, 'lr-chart-run--intro': chartIntroSheetId === String(openSheetId), 'lr-chart-run--fresh': progressFeedbackActive && String(run.id) === String(freshRunId) }" tabindex="0" :aria-label="run.ariaLabel">
                  <title>{{ run.ariaLabel }}</title>
                  <rect class="lr-chart-bar-bg" :x="run.x" y="16" :width="run.barWidth" height="100" rx="5" />
                  <rect class="lr-chart-bar lr-chart-bar--weak" :style="{ animationDelay: `${100 + index * 65}ms` }" :x="run.x" :y="run.weakY" :width="run.barWidth" :height="run.weakH" />
                  <rect class="lr-chart-bar lr-chart-bar--medium" :style="{ animationDelay: `${145 + index * 65}ms` }" :x="run.x" :y="run.mediumY" :width="run.barWidth" :height="run.mediumH" />
                  <rect class="lr-chart-bar lr-chart-bar--strong" :style="{ animationDelay: `${190 + index * 65}ms` }" :x="run.x" :y="run.strongY" :width="run.barWidth" :height="run.strongH" rx="3" />
                  <text class="lr-chart-date" :x="run.x + run.barWidth / 2" y="142" text-anchor="middle">{{ run.day }}</text>
                  <text class="lr-chart-time" :x="run.x + run.barWidth / 2" y="158" text-anchor="middle">{{ run.time }}</text>
                </g>
                <polyline v-if="sheetRunChart.length > 1" class="lr-chart-score-line" pathLength="1" :points="sheetRunChartPoints" />
                <circle v-for="(run, index) in sheetRunChart" :key="`score-${run.id}`" class="lr-chart-score-point" :class="{ 'lr-chart-score-point--fresh': progressFeedbackActive && String(run.id) === String(freshRunId) }" :style="{ animationDelay: `${220 + index * 65}ms` }" :cx="run.centerX" :cy="run.scoreY" r="4.5"><title>{{ run.score }} % Lernsicherheit</title></circle>
              </svg>
            </div>
              </div>
            </div>
          </Transition>
        </section>

        <section class="lr-sheet-column lr-sheet-cards" aria-labelledby="lr-sheet-cards-title">
          <div class="lr-sheet-column-head lr-sheet-column-head--sticky">
              <div>
                <span class="lr-overline">Lernmaterial</span>
                <h2 id="lr-sheet-cards-title">Karten</h2>
              </div>
              <span class="lr-section-meta">{{ cards.length }}</span>
            </div>

            <div class="lr-cards-list">
              <div v-if="cards.length" class="lr-cards-grid">
                <article v-for="card in cards" :key="card.id" class="lr-card-row" role="button" tabindex="0" :aria-label="`Karte bearbeiten: ${card.front || 'Unvollständige Karte'}`" @click="onEditCard(card)" @keydown.enter.self="onEditCard(card)" @keydown.space.self.prevent="onEditCard(card)">
                  <div class="lr-card-row-main">
                    <span class="lr-card-kind" :style="{ color: kindChipStyle(card.kind).color }">{{ kindLabel(card.kind) }}</span>
                    <div v-if="card.front" class="lr-card-front">{{ card.front }}</div>
                    <div v-else class="lr-card-front lr-card-side--empty">Vorderseite noch leer</div>
                    <template v-if="cardFormat(card.kind) === 'sequence'">
                      <div v-if="cardSteps(card).length" class="lr-card-back">{{ cardSteps(card).length }} Schritte · {{ cardSteps(card).join(' → ') }}</div>
                      <div v-else class="lr-card-back lr-card-side--empty">Noch keine Schritte</div>
                    </template>
                    <template v-else>
                      <div v-if="card.back" class="lr-card-back">{{ card.back }}</div>
                      <div v-else class="lr-card-back lr-card-side--empty">Rückseite noch leer</div>
                    </template>
                  </div>
                  <div class="lr-card-row-actions">
                    <button type="button" class="lr-icon-btn" title="Bearbeiten" aria-label="Karte bearbeiten" @click.stop="onEditCard(card)">✎</button>
                    <button type="button" class="lr-icon-btn lr-icon-btn--danger" title="Löschen" aria-label="Karte löschen" @click.stop="onDeleteCard(card)">✕</button>
                  </div>
                </article>
              </div>
              <div v-else class="lr-cards-empty">
                <span>Noch keine Karten. Karten entstehen beim Nachbereiten markierter Notizzeilen.</span>
              </div>
            </div>
        </section>
        </template>
      </main>
      </div>
    </template>


    <!-- ===== Anlege-/Bearbeiten-Dialog (klein, im Panel) ===== -->
    <div v-if="dialog && !['queue', 'card-edit'].includes(dialog.kind)" class="lr-modal-scrim" @click.self="closeDialog" @keydown.esc="closeDialog">
      <div class="lr-modal" role="dialog" aria-modal="true">
        <div class="lr-modal-title">{{ dialogTitle }}</div>

        <label class="lr-field-label">{{ dialog.kind === 'course' ? 'Kursname' : 'Name des Lernblatts' }}</label>
        <input ref="dialogInput" class="lr-field" v-model="dialog.name" @keydown.enter="submitDialog" :placeholder="dialog.kind === 'course' ? 'z. B. Computergrafik 1' : 'z. B. Rasterisierung'" />

        <div v-if="dialogError" class="lr-field-error">{{ dialogError }}</div>

        <div class="lr-modal-actions">
          <button type="button" class="lr-btn lr-btn--ghost lr-btn--md" @click="closeDialog">Abbrechen</button>
          <button type="button" class="lr-btn lr-btn--primary lr-btn--md" :disabled="dialogBusy" @click="submitDialog">{{ dialogSubmitLabel }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useLearnStore } from '../stores/learn.js';
import { listCards } from '../api/learn.js';
import { streamNoteText } from '../api/notes.js';
import PmActionIcon from '../components/PmActionIcon.vue';
import NotePreview from '../components/notes/NotePreview.vue';
import { useSidebarAppearance } from '../composables/useSidebarAppearance.js';

// Lernraum: Startseite (Übersicht) → Kurs öffnen → Lernblatt öffnen.
// Rendert INNERHALB der gemeinsamen Shell (echte App-Seitenleiste bleibt stehen).
// „Offene Nachbereitungen" laufen vorerst über den Lernblatt-Status (draft/in_progress),
// bis die Marker-/Karten-Ebene (Maske 1b) echte Marker liefert.

const store = useLearnStore();
const route = useRoute();
const router = useRouter();
const LEARN_NAV_STORAGE_KEY = 'papermind:lernraum:last-navigation:v1';

function readRememberedNavigation() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(LEARN_NAV_STORAGE_KEY) || 'null');
    if (!saved || typeof saved !== 'object') return null;
    return {
      courseId: saved.courseId == null ? null : String(saved.courseId),
      sheetId: saved.sheetId == null ? null : String(saved.sheetId),
    };
  } catch {
    return null;
  }
}
function rememberNavigation(courseId = null, sheetId = null) {
  try {
    window.localStorage.setItem(LEARN_NAV_STORAGE_KEY, JSON.stringify({
      courseId: courseId == null ? null : String(courseId),
      sheetId: sheetId == null ? null : String(sheetId),
    }));
  } catch {
    // Die Navigation bleibt auch ohne verfügbaren Browserspeicher funktionsfähig.
  }
}

const CONFETTI_COLORS = ['#55cbd0', '#f1b24f', '#f17f78', '#7bc58e', '#91aee8', '#d78bc2'];
const confettiPieces = Array.from({ length: 156 }, (_, index) => ({
  id: index,
  style: {
    '--confetti-x': `${(index * 37) % 101}%`,
    '--confetti-size': `${6 + (index % 4) * 2}px`,
    '--confetti-color': CONFETTI_COLORS[index % CONFETTI_COLORS.length],
    '--confetti-delay': `${(index % 48) * 0.13}s`,
    '--confetti-duration': `${5.6 + (index % 8) * 0.31}s`,
    '--confetti-drift': `${-68 + ((index * 29) % 137)}px`,
    '--confetti-sway': `${(index % 2 ? -1 : 1) * (18 + (index % 6) * 7)}px`,
    '--confetti-sway-back': `${(index % 2 ? 1 : -1) * (18 + (index % 6) * 7)}px`,
    '--confetti-rotate': `${540 + (index % 6) * 150}deg`,
  },
}));

const view = ref('home'); // 'home' | 'course'
const openSheetId = ref(null);
const navigationReady = ref(false);
const chartIntroSheetId = ref(null);
let chartIntroTimer = null;
const editingCourseTitle = ref(false);
const courseTitleDraft = ref('');
const courseTitleInput = ref(null);
const courseTitleBusy = ref(false);
const courseTitleError = ref('');
const editingCourseCardId = ref(null);
const courseCardTitleDraft = ref('');
const courseCardTitleBusy = ref(false);
const courseCardTitleError = ref('');
const deletingCourseIds = ref(new Set());
const editingSheetId = ref(null);
const sheetTitleDraft = ref('');
const sheetTitleBusy = ref(false);
const sheetTitleError = ref('');
const deletingSheetIds = ref(new Set());
const deletingRunIds = ref(new Set());
const runDeleteError = ref('');
const progressExpanded = ref(true);
const favoriteAnimating = ref(false);
const favoriteBusy = ref(false);
let favoriteAnimTimer = null;

const totalSheets = computed(() => store.courses.reduce((n, c) => n + (c.sheet_count || 0), 0));
const favoriteSheets = computed(() => store.allSheets
  .filter((sheet) => sheet.is_favorite)
  .map((sheet) => ({
    ...sheet,
    courseTitle: store.courses.find((course) => course.id === sheet.course_id)?.title || 'Unbekannter Kurs',
  })));

// Lernblätter des aktiven Kurses (mit Sitzungstitel als Etikett).
const courseSheets = computed(() => {
  const board = store.board;
  if (!board) return [];
  const rows = [];
  for (const s of board.sessions || []) for (const sheet of s.sheets) rows.push({ ...sheet, sessionTitle: s.title });
  for (const sheet of board.loose_sheets || []) rows.push({ ...sheet, sessionTitle: null });
  return rows;
});
const openSheet = computed(() => courseSheets.value.find((s) => s.id === openSheetId.value) || null);

const pageTitle = computed(() => {
  if (openSheet.value) return openSheet.value.title;
  if (view.value === 'course') return store.activeCourse?.title || 'Kurs';
  return 'Lernraum';
});
const pageSubtitle = computed(() => {
  if (openSheet.value) {
    const n = cards.value.length;
    return `${n} ${n === 1 ? 'Karte' : 'Karten'}${openSheet.value.sessionTitle ? ` · ${openSheet.value.sessionTitle}` : ''}`;
  }
  if (view.value === 'course') return courseStatLine.value;
  return statLine.value;
});
function courseMonogram(title = '') {
  return title.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toLocaleUpperCase('de-DE') || 'K';
}

// --- Lernobjekt-Format je Kartentyp ---
// Flip-Karte (Standard) vs. Schrittfolge (Prozess/Anleitung, Payload: steps).
const SEQUENCE_KINDS = new Set(['prozess', 'prozedural']);
function cardFormat(kind) { return SEQUENCE_KINDS.has(kind) ? 'sequence' : 'card'; }
function cardSteps(card) {
  const steps = card?.payload?.steps;
  return Array.isArray(steps) ? steps.filter((s) => String(s || '').trim()) : [];
}

// --- Karten des offenen Lernblatts ---
const cards = computed(() => (store.cardsSheetId === openSheetId.value ? store.cards : []));
function isLearnableCard(card) {
  if (!String(card?.front || '').trim()) return false;
  if (cardFormat(card?.kind) === 'sequence') return cardSteps(card).length >= 2;
  return Boolean(String(card?.back || '').trim());
}
const learnableCards = computed(() => cards.value.filter(isLearnableCard));
function sheetLearnableCount(sheet) {
  return sheet?.learnable_card_count ?? sheet?.card_count ?? 0;
}
const sheetLearningRuns = computed(() => {
  const sheetId = openSheetId.value;
  if (!sheetId) return [];
  return store.learningRuns
    .filter((run) => String(run.sheet_id || '') === String(sheetId))
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
});
function runScore(run) {
  const total = Math.max(1, Number(run?.total_cards) || 0);
  return Math.round((((Number(run?.strong_count) || 0) + (Number(run?.medium_count) || 0) * 0.5) / total) * 100);
}
const latestRunScore = computed(() => sheetLearningRuns.value.length ? runScore(sheetLearningRuns.value[0]) : 0);
const sheetRunChartWidth = computed(() => Math.max(720, Math.min(12, sheetLearningRuns.value.length) * 84 + 96));
const sheetRunChart = computed(() => {
  const runs = sheetLearningRuns.value.slice(0, 12).reverse();
  const width = sheetRunChartWidth.value;
  const step = (width - 104) / Math.max(1, runs.length);
  const barWidth = Math.min(34, Math.max(22, step * 0.48));
  return runs.map((run, index) => {
    const total = Math.max(1, Number(run.total_cards) || 0);
    const strongH = ((Number(run.strong_count) || 0) / total) * 100;
    const mediumH = ((Number(run.medium_count) || 0) / total) * 100;
    const weakH = ((Number(run.weak_count) || 0) / total) * 100;
    const x = 56 + index * step + (step - barWidth) / 2;
    const score = runScore(run);
    return {
      id: run.id,
      x,
      centerX: x + barWidth / 2,
      barWidth,
      strongH,
      mediumH,
      weakH,
      weakY: 116 - weakH,
      mediumY: 116 - weakH - mediumH,
      strongY: 116 - weakH - mediumH - strongH,
      score,
      scoreY: 116 - score,
      day: formatRunDay(run.started_at),
      time: formatRunTime(run.started_at),
      completed: Boolean(run.completed_at),
      ariaLabel: `${formatRunDay(run.started_at)}, ${formatRunTime(run.started_at)}: ${score} Prozent Lernsicherheit, ${run.strong_count || 0} sicher, ${run.medium_count || 0} mit Mühe, ${run.weak_count || 0} offen${run.completed_at ? '' : ', pausiert'}`,
    };
  });
});
const sheetRunChartPoints = computed(() => sheetRunChart.value.map((run) => `${run.centerX},${run.scoreY}`).join(' '));

const KIND = {
  fakt: { label: 'Fakt', tint: 'success' },
  prozess: { label: 'Prozess', tint: 'accent' },
  zusammenhang: { label: 'Vergleich', tint: 'accent' },
  prozedural: { label: 'Anleitung', tint: 'neutral' },
  verstaendnis: { label: 'Verständnis', tint: 'accent' },
  uebung: { label: 'Übung', tint: 'warning' },
};
function kindLabel(kind) { return (KIND[kind] || KIND.fakt).label; }
function kindChipStyle(kind) {
  const tint = (KIND[kind] || KIND.fakt).tint;
  if (tint === 'success') return { background: 'color-mix(in oklab, var(--pm-success) 16%, transparent)', color: 'var(--pm-success)' };
  if (tint === 'warning') return { background: 'color-mix(in oklab, var(--pm-star) 18%, transparent)', color: 'var(--pm-star)' };
  if (tint === 'accent') return { background: 'var(--pm-selected)', color: 'var(--pm-accent-text)' };
  return { background: 'var(--pm-chip-bg)', color: 'var(--pm-chip-text)' };
}

// --- Startseite: Kopf, Lernstand, Nachbereitungen ---------------------------
const totalCards = computed(() => store.courses.reduce((n, c) => n + (c.card_count || 0), 0));
const overallProficiency = computed(() => store.courses.reduce((sum, course) => {
  const proficiency = course.proficiency || {};
  sum.total += proficiency.total || course.card_count || 0;
  sum.strong += proficiency.strong || 0;
  sum.medium += proficiency.medium || 0;
  sum.weak += proficiency.weak || 0;
  sum.open += proficiency.open || 0;
  return sum;
}, { total: 0, strong: 0, medium: 0, weak: 0, open: 0 }));
const headerProficiency = computed(() => view.value === 'home'
  ? overallProficiency.value
  : store.activeCourse?.proficiency || { total: 0, strong: 0, medium: 0, weak: 0, open: 0 });
const headerProgressMarkerPosition = computed(() => Math.min(98.5, Math.max(1.5, strongPct(headerProficiency.value))));
const statLine = computed(() => {
  const k = store.courses.length;
  const parts = [`${k} ${k === 1 ? 'Kurs' : 'Kurse'}`];
  parts.push(`${totalSheets.value} ${totalSheets.value === 1 ? 'Lernblatt' : 'Lernblätter'}`);
  if (totalCards.value) parts.push(`${totalCards.value} Karten`);
  return parts.join(' · ');
});
function estMinutes(markerCount) { return Math.max(1, Math.round((markerCount || 0) * 1.5)); }
function formatRunDay(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '–' : new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: 'short' }).format(date);
}
function formatRunTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(date);
}
// Lernstand-Farben (Karten-Status)
const CARD_STATUS = {
  strong: { label: 'Sicher', color: 'var(--pm-success)' },
  medium: { label: 'Mit Mühe', color: 'var(--pm-star)' },
  weak: { label: 'Nicht gekonnt', color: 'var(--pm-danger)' },
  open: { label: 'Noch offen', color: 'var(--pm-border)' },
};
function statusLabel(s) { return (CARD_STATUS[s] || CARD_STATUS.open).label; }
function statusColor(s) { return (CARD_STATUS[s] || CARD_STATUS.open).color; }
function pct(prof, key) {
  const t = prof?.total || 0;
  return t ? Math.round(((prof[key] || 0) * 100) / t) : 0;
}
function strongPct(prof) { return pct(prof, 'strong'); }
// Segmente des Fortschrittsbalkens (sicher→Mühe→nicht→offen).
function barSegments(prof) {
  const order = [
    ['strong', 'var(--pm-success)'],
    ['medium', 'var(--pm-star)'],
    ['weak', 'var(--pm-danger)'],
    ['open', 'var(--pm-track)'],
  ];
  return order.map(([key, color]) => ({ key, color, pct: pct(prof, key) }));
}
function courseSub(course) {
  const n = course.sheet_count || 0;
  const c = course.card_count || 0;
  if (!n && !c) return 'Noch keine Lernblätter';
  return `${n} ${n === 1 ? 'Lernblatt' : 'Lernblätter'} · ${c} ${c === 1 ? 'Karte' : 'Karten'}`;
}

// --- Kursübersicht (Lernmaterial als klare zweite Ebene) ---
function kindSummaryLabel(k) { return k === 'gemischt' ? 'Gemischt' : kindLabel(k); }
const courseStatLine = computed(() => {
  const c = store.activeCourse;
  if (!c) return '';
  const n = courseSheets.value.length;
  const parts = [`${n} ${n === 1 ? 'Lernblatt' : 'Lernblätter'}`];
  if (c.card_count) parts.push(`${c.card_count} Karten`);
  return parts.join(' · ');
});
const markerTasks = computed(() => markerNoteGroups.value.flatMap((group) =>
  group.markers.map((marker, markerIndex) => ({ group, marker, markerIndex })),
));
const courseMarkerTasks = computed(() => markerTasks.value.filter((task) =>
  task.marker.course_id && task.marker.course_id === store.activeCourseId,
));
const courseMarkerCount = computed(() => courseMarkerTasks.value.length);
// „Später": Marker der Gruppe für diese Sitzung ausblenden (nur clientseitig).
const dismissedNoteIds = ref(new Set());
function dismissGroup(g) { dismissedNoteIds.value = new Set([...dismissedNoteIds.value, g.noteId]); }

// --- Lernmodus (generalisiert: beliebige Kartenliste + Selbsteinschätzung) ---
const LEARN_ORDER_STORAGE_KEY = 'papermind:lernraum:learn-order:v1';
const learnStartOptionsOpen = ref(false);
const learnOrder = ref(readLearnOrder());
const learnOriginalCards = ref([]);
function readLearnOrder() {
  try {
    const saved = window.localStorage.getItem(LEARN_ORDER_STORAGE_KEY);
    return ['random', 'difficult'].includes(saved) ? saved : 'original';
  }
  catch { return 'original'; }
}
watch(learnOrder, (value) => {
  try { window.localStorage.setItem(LEARN_ORDER_STORAGE_KEY, value); } catch { /* Storage may be unavailable. */ }
});
const learning = ref(false);
const learnIndex = ref(0);
const revealed = ref(false);
const learnQueue = ref([]); // Kopien der zu lernenden Karten
const learnDirty = ref(false); // wurde eingeschätzt? → am Ende Aggregate neu laden
const learnResults = ref({ weak: 0, medium: 0, strong: 0 });
const learnOpenedInternally = ref(false);
const learnExitWarningOpen = ref(false);
const learnProgressPulse = ref(false);
const progressFeedbackActive = ref(false);
const freshRunId = ref(null);
const learnRunId = ref(null);
let learnProgressPulseTimer = null;
let progressFeedbackTimer = null;
let learnRunToken = 0;
let learnRunStartedAt = '';
let learnRunCompletedAt = '';
let learnRunCourseId = null;
let learnRunSheetId = null;
let learnRunScope = 'sheet';
let learnRunSaveChain = Promise.resolve();
const currentLearn = computed(() => learnQueue.value[learnIndex.value] || null);

// --- Schrittfolge im Lernmodus (Reihenfolge ordnen) ---
const currentLearnFormat = computed(() => cardFormat(currentLearn.value?.kind));
function shuffleSteps(steps) {
  const items = steps.map((text, idx) => ({ idx, text }));
  if (items.length < 2) return items;
  for (let i = items.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  if (items.every((it, i) => it.idx === i)) [items[0], items[1]] = [items[1], items[0]];
  return items;
}
function moveSeq(i, dir) {
  const card = currentLearn.value;
  if (!card || card.seqChecked) return;
  const items = card.seqItems || [];
  const j = i + dir;
  if (j < 0 || j >= items.length) return;
  [items[i], items[j]] = [items[j], items[i]];
}
function checkSeq() {
  const card = currentLearn.value;
  if (card) card.seqChecked = true;
}
const seqCorrectCount = computed(() =>
  (currentLearn.value?.seqItems || []).reduce((n, it, i) => n + (it.idx === i ? 1 : 0), 0),
);
const seqAllCorrect = computed(() => {
  const items = currentLearn.value?.seqItems || [];
  return items.length > 0 && seqCorrectCount.value === items.length;
});

const learnFrontWidth = computed(() => {
  const question = String(currentLearn.value?.front || '').trim();
  const longestWord = question.split(/\s+/).reduce((max, word) => Math.max(max, word.length), 0);
  return Math.min(720, Math.max(360, 360 + Math.max(0, question.length - 18) * 12, 120 + longestWord * 14));
});
const assessedLearnCount = computed(() => learnQueue.value.filter((card) => card.sessionAssessment).length);
const remainingLearnCount = computed(() => Math.max(0, learnQueue.value.length - assessedLearnCount.value));
function assessmentLabel(value) {
  return {
    weak: 'Nicht gekonnt',
    medium: 'Mit Mühe',
    strong: 'Sicher',
  }[value] || 'Beantwortet';
}
const learnCompletion = computed(() => learnQueue.value.length
  ? Math.round((assessedLearnCount.value / learnQueue.value.length) * 100)
  : 0);
const learnScore = computed(() => {
  if (!learnQueue.value.length) return 0;
  return Math.round(((learnResults.value.strong + learnResults.value.medium * .5) / learnQueue.value.length) * 100);
});
const learnResultRows = computed(() => [
  { key: 'strong', label: 'Sicher', count: learnResults.value.strong },
  { key: 'medium', label: 'Mit Mühe', count: learnResults.value.medium },
  { key: 'weak', label: 'Offen', count: learnResults.value.weak },
].map((result) => ({
  ...result,
  percent: learnQueue.value.length ? Math.round((result.count / learnQueue.value.length) * 100) : 0,
})));

function startLearn(cardList, startId = null, scope = openSheet.value ? 'sheet' : 'course', updateUrl = true) {
  const list = (cardList || []).filter(isLearnableCard);
  if (!list.length) return;
  learnStartOptionsOpen.value = false;
  learnOriginalCards.value = [...list];
  const ordered = [...list];
  if (['random', 'difficult'].includes(learnOrder.value)) {
    for (let i = ordered.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [ordered[i], ordered[j]] = [ordered[j], ordered[i]];
    }
  }
  if (learnOrder.value === 'difficult') {
    const priority = { weak: 0, open: 1, medium: 2, strong: 3 };
    // Stable sorting preserves the shuffled order within each proficiency group.
    ordered.sort((a, b) => (priority[a.status] ?? 1) - (priority[b.status] ?? 1));
  }
  learnQueue.value = ordered.map((c) => {
    const base = { ...c, aiHint: '', hintVisible: false, hintBusy: false, hintError: '', sessionAssessment: '' };
    if (cardFormat(c.kind) === 'sequence') {
      base.seqItems = shuffleSteps(cardSteps(c));
      base.seqChecked = false;
    }
    return base;
  });
  const at = startId ? learnQueue.value.findIndex((c) => c.id === startId) : 0;
  learnIndex.value = at >= 0 ? at : 0;
  revealed.value = false;
  learnDirty.value = false;
  learnResults.value = { weak: 0, medium: 0, strong: 0 };
  learnOpenedInternally.value = updateUrl;
  learnExitWarningOpen.value = false;
  learnRunToken += 1;
  learnRunId.value = null;
  learnRunStartedAt = new Date().toISOString();
  learnRunCompletedAt = '';
  learnRunCourseId = store.activeCourseId;
  learnRunScope = scope;
  learnRunSheetId = scope === 'sheet' ? (openSheet.value?.id || store.cardsSheetId || null) : null;
  learning.value = true;
  if (updateUrl && route.query.learn !== '1') {
    router.push({ name: 'lernraum', query: { ...route.query, learn: '1', scope } }).catch(() => {});
  }
}

function cleanLearnHint(value) {
  return String(value || '')
    .trim()
    .replace(/^```(?:text|markdown)?\s*/i, '')
    .replace(/\s*```$/, '')
    .replace(/^>\s?/gm, '')
    .replace(/^hinweis\s*:\s*/i, '')
    .trim();
}

async function toggleLearnHint() {
  const card = currentLearn.value;
  if (!card || card.hintBusy) return;
  if (card.hintVisible) {
    card.hintVisible = false;
    return;
  }
  card.hintVisible = true;
  card.hintError = '';
  if (card.aiHint) return;

  card.hintBusy = true;
  let generated = '';
  try {
    await streamNoteText({
      instruction: [
        `Erzeuge einen kurzen didaktischen Hinweis für eine Lernkarte der Art „${kindLabel(card.kind)}“.`,
        'Der Hinweis soll einen Denkweg, eine passende Rückfrage oder einen relevanten Zusammenhang anbieten.',
        'Verrate weder die Lösung noch eine Teilantwort. Nenne keine Zahl, keinen Eigennamen und keinen Schlüsselbegriff aus der Lösung, der die Antwort unmittelbar vorwegnimmt.',
        'Formuliere ermutigend und konkret. Gib ausschließlich den Hinweis ohne Überschrift aus.',
      ].join(' '),
      length_instruction: 'Ein bis zwei kurze Sätze.',
      note_context: '',
      context_scope: 'note',
      selected_text: '',
      // Der Lösungstext dient nur zur Abgrenzung und erzwingt serverseitig das lokale Modell.
      document_context: `Frage: ${card.front}\nInterne Lösung – nicht ausgeben: ${card.back || 'Keine feste Musterlösung.'}`,
    }, {
      onEvent: (event) => {
        if (event.type === 'delta') generated += event.text || '';
      },
    });
    const hint = cleanLearnHint(generated);
    if (!hint) throw new Error('Es konnte kein Hinweis erzeugt werden.');
    card.aiHint = hint;
  } catch (err) {
    card.hintError = err?.message || 'Der Hinweis konnte nicht erzeugt werden.';
  } finally {
    card.hintBusy = false;
  }
}
function startLearning() { startLearn(cards.value, null, 'sheet'); }
function restartLearning() { startLearn(learnOriginalCards.value, null, learnRunScope, false); }
async function startSheetLearn(sheet) {
  const courseId = sheet?.course_id || store.activeCourseId;
  if (!sheet?.id || !sheetLearnableCount(sheet) || !courseId) return;
  if (store.activeCourseId !== courseId) await store.selectCourse(courseId);
  await router.push({ name: 'lernraum', query: { course: String(courseId), sheet: String(sheet.id) } });
  openSheetId.value = sheet.id;
  await store.fetchCards(sheet.id);
  startLearn(store.cards, null, 'sheet');
}

async function clearLearning() {
  learnExitWarningOpen.value = false;
  learning.value = false;
  learnQueue.value = [];
  learnOpenedInternally.value = false;
  if (learnDirty.value) {
    await learnRunSaveChain.catch(() => {});
    triggerProgressFeedback(learnRunCompletedAt ? learnRunId.value : null);
    learnDirty.value = false;
    await Promise.all([store.fetchCourses(), store.fetchBoard()]);
    if (store.cardsSheetId) await store.fetchCards(store.cardsSheetId);
  }
}

function triggerProgressFeedback(runId = null) {
  progressFeedbackActive.value = false;
  freshRunId.value = null;
  if (progressFeedbackTimer) window.clearTimeout(progressFeedbackTimer);
  window.requestAnimationFrame(() => {
    progressFeedbackActive.value = true;
    freshRunId.value = runId;
    progressFeedbackTimer = window.setTimeout(() => {
      progressFeedbackActive.value = false;
      freshRunId.value = null;
      progressFeedbackTimer = null;
    }, 900);
  });
}

function requestExitLearning() {
  if (!remainingLearnCount.value) {
    exitLearning();
    return;
  }
  learnExitWarningOpen.value = !learnExitWarningOpen.value;
}

async function exitLearning() {
  learnExitWarningOpen.value = false;
  if (route.query.learn === '1') {
    if (learnOpenedInternally.value) {
      router.back();
    } else {
      const { learn: _learn, scope: _scope, ...query } = route.query;
      await router.replace({ name: 'lernraum', query });
    }
    return;
  }
  await clearLearning();
}

async function pulseLearnProgress() {
  learnProgressPulse.value = false;
  if (learnProgressPulseTimer) window.clearTimeout(learnProgressPulseTimer);
  await nextTick();
  learnProgressPulse.value = true;
  learnProgressPulseTimer = window.setTimeout(() => {
    learnProgressPulse.value = false;
    learnProgressPulseTimer = null;
  }, 620);
}

async function assess(status) {
  const card = currentLearn.value;
  if (!card) return;
  try {
    await store.reviewCard(card.id, status);
    card.status = status; // lokale Kopie fürs Overlay
    const originalCard = learnOriginalCards.value.find((item) => item.id === card.id);
    if (originalCard) originalCard.status = status;
    learnDirty.value = true;
    const previous = card.sessionAssessment;
    const nextResults = { ...learnResults.value };
    if (previous && previous !== status) nextResults[previous] = Math.max(0, nextResults[previous] - 1);
    if (previous !== status) nextResults[status] += 1;
    card.sessionAssessment = status;
    learnResults.value = nextResults;
    pulseLearnProgress();
    scheduleLearningRunSave();
  } catch { /* Fehler ignorieren, trotzdem weiter */ }
  if (learnIndex.value + 1 < learnQueue.value.length) {
    learnIndex.value += 1;
    revealed.value = false;
  } else {
    // letzte Karte → Abschluss anzeigen (currentLearn wird null)
    learnIndex.value = learnQueue.value.length;
  }
}

function moveLearn(offset) {
  const next = learnIndex.value + offset;
  if (next < 0 || next >= learnQueue.value.length) return;
  learnIndex.value = next;
  revealed.value = false;
}

function scheduleLearningRunSave() {
  const token = learnRunToken;
  const courseId = learnRunCourseId;
  if (!courseId || !assessedLearnCount.value) return;
  const totalCards = learnQueue.value.length;
  const sheetId = learnRunSheetId;
  const scope = learnRunScope;
  const startedAt = learnRunStartedAt;
  if (assessedLearnCount.value >= totalCards && !learnRunCompletedAt) learnRunCompletedAt = new Date().toISOString();
  const snapshot = {
    assessed_cards: assessedLearnCount.value,
    weak_count: learnResults.value.weak,
    medium_count: learnResults.value.medium,
    strong_count: learnResults.value.strong,
    completed_at: learnRunCompletedAt || null,
  };
  learnRunSaveChain = learnRunSaveChain
    .catch(() => {})
    .then(async () => {
      if (token !== learnRunToken) return;
      if (!learnRunId.value) {
        const run = await store.addLearningRun(courseId, {
          sheet_id: sheetId,
          scope,
          total_cards: totalCards,
          started_at: startedAt,
        });
        if (token !== learnRunToken) return;
        learnRunId.value = run.id;
      }
      await store.patchLearningRun(learnRunId.value, snapshot);
    })
    .catch(() => {});
}

const sheetCountLabel = computed(() => {
  const n = courseSheets.value.length;
  return n === 1 ? '1 Lernblatt' : `${n} Lernblätter`;
});

// Startseite: Marker ohne vollständige Karte, nach Herkunfts-Notiz gruppiert.
const markerNoteGroups = computed(() => {
  const byNote = new Map();
  for (const m of store.openMarkers || []) {
    if (dismissedNoteIds.value.has(m.note_id)) continue;
    let g = byNote.get(m.note_id);
    if (!g) {
      g = {
        noteId: m.note_id,
        noteTitle: m.note_title,
        courseId: m.course_id || null,
        courseTitle: m.course_title || null,
        sessionTitle: m.session_title || null,
        markers: [],
      };
      byNote.set(m.note_id, g);
    }
    g.markers.push(m);
  }
  // Zugeordnete Notizen zuerst, dann nach Anzahl offener Marker.
  return Array.from(byNote.values()).sort((a, b) => {
    if (!!a.courseTitle !== !!b.courseTitle) return a.courseTitle ? -1 : 1;
    return b.markers.length - a.markers.length;
  });
});

// Marker-Vokabular (Schnell-Markierung) → Anzeige.
const MARKER_KIND = {
  lernen: { label: 'Lernstoff', tint: 'accent' },
  fakt: { label: 'Fakt', tint: 'success' },
  warum: { label: 'Warum', tint: 'accent' },
  aufgabe: { label: 'Aufgabe', tint: 'warning' },
  analyse: { label: 'Analyse', tint: 'accent' },
  prozess: { label: 'Prozess', tint: 'accent' },
  vergleich: { label: 'Vergleich', tint: 'accent' },
};
function markerKindLabel(kind) { return (MARKER_KIND[kind] || MARKER_KIND.lernen).label; }
function markerKindStyle(kind) {
  const tint = (MARKER_KIND[kind] || MARKER_KIND.lernen).tint;
  if (tint === 'success') return { background: 'color-mix(in oklab, var(--pm-success) 16%, transparent)', color: 'var(--pm-success)' };
  if (tint === 'warning') return { background: 'color-mix(in oklab, var(--pm-star) 18%, transparent)', color: 'var(--pm-star)' };
  return { background: 'var(--pm-selected)', color: 'var(--pm-accent-text)' };
}

// Marker, die schon eine Frage/Aufgabe SIND (Vorderseite); alle anderen sind
// Aussagen und werden als Antwort vorbelegt.
const PROMPT_MARKER_KINDS = new Set(['warum', 'aufgabe', 'analyse']);

// Schnell-Marker-Typ → vorgeschlagener Artefakt-/Kartentyp in der Nachbereitung.
const MARKER_TO_KIND = {
  lernen: 'fakt',
  fakt: 'fakt',
  warum: 'verstaendnis',
  aufgabe: 'uebung',
  analyse: 'verstaendnis',
  prozess: 'prozess',
  vergleich: 'zusammenhang',
};

watch(() => store.board, () => {
  if (openSheetId.value && !openSheet.value) openSheetId.value = null;
});

function goHome() {
  router.push({ name: 'lernraum' }).catch(() => {});
}
const crumbs = computed(() => {
  const list = [{ label: 'Startseite', go: goHome, current: view.value !== 'course' || !store.activeCourse }];
  if (view.value === 'course' && store.activeCourse) list.push({ label: store.activeCourse.title, go: closeSheet, current: !openSheet.value });
  if (openSheet.value) list.push({ label: openSheet.value.title, current: true });
  return list;
});
function openCourse(id) {
  router.push({ name: 'lernraum', query: { course: String(id) } }).catch(() => {});
}
function closeSheet() {
  if (!store.activeCourseId) return goHome();
  openCourse(store.activeCourseId);
}
function openSheetView(id) {
  if (!store.activeCourseId) return;
  router.push({ name: 'lernraum', query: { course: String(store.activeCourseId), sheet: String(id) } }).catch(() => {});
}
function openFavoriteSheet(sheet) {
  if (!sheet?.id || !sheet.course_id) return;
  router.push({ name: 'lernraum', query: { course: String(sheet.course_id), sheet: String(sheet.id) } }).catch(() => {});
}

async function syncNavigationFromRoute() {
  if (!navigationReady.value) return;
  const courseId = typeof route.query.course === 'string' ? route.query.course : null;
  const sheetId = typeof route.query.sheet === 'string' ? route.query.sheet : null;

  if (!courseId) {
    view.value = 'home';
    openSheetId.value = null;
    if (learning.value) await clearLearning();
    rememberNavigation();
    return;
  }

  const course = store.courses.find((item) => String(item.id) === courseId);
  if (!course) {
    rememberNavigation();
    router.replace({ name: 'lernraum' }).catch(() => {});
    return;
  }

  view.value = 'course';
  if (String(store.activeCourseId) !== courseId) await store.selectCourse(course.id);

  if (sheetId) {
    const sheet = courseSheets.value.find((item) => String(item.id) === sheetId);
    if (!sheet) {
      rememberNavigation(course.id);
      router.replace({ name: 'lernraum', query: { course: courseId } }).catch(() => {});
      return;
    }
    const openingDifferentSheet = String(openSheetId.value) !== String(sheet.id);
    openSheetId.value = sheet.id;
    if (String(store.cardsSheetId) !== sheetId) await store.fetchCards(sheet.id);
    if (openingDifferentSheet) scheduleChartIntro(sheet.id);
  } else {
    openSheetId.value = null;
  }

  rememberNavigation(course.id, openSheetId.value);

  if (route.query.learn === '1' && !learning.value) {
    if (route.query.scope === 'sheet' && openSheetId.value) {
      startLearn(cards.value, null, 'sheet', false);
    } else {
      const lists = await Promise.all(courseSheets.value.map((sheet) => listCards(sheet.id).then((res) => res.items || []).catch(() => [])));
      startLearn(lists.flat(), null, 'course', false);
    }
  } else if (route.query.learn !== '1' && learning.value) {
    await clearLearning();
  }
}

function scheduleChartIntro(sheetId) {
  if (!sheetId || !sheetLearningRuns.value.length) return;
  chartIntroSheetId.value = null;
  nextTick(() => {
    chartIntroSheetId.value = String(sheetId);
    if (chartIntroTimer) window.clearTimeout(chartIntroTimer);
    chartIntroTimer = window.setTimeout(() => {
      chartIntroSheetId.value = null;
      chartIntroTimer = null;
    }, Math.min(1100, 520 + sheetRunChart.value.length * 65));
  });
}

function onCreateCourse() { openDialog({ kind: 'course', name: '' }); }
function editCourseTitle() {
  if (!store.activeCourse) return;
  courseTitleDraft.value = store.activeCourse.title;
  courseTitleError.value = '';
  editingCourseTitle.value = true;
  nextTick(() => courseTitleInput.value?.select());
}
function cancelCourseTitle() {
  editingCourseTitle.value = false;
  courseTitleError.value = '';
}
async function saveCourseTitle() {
  if (!editingCourseTitle.value || courseTitleBusy.value || !store.activeCourse) return;
  const title = courseTitleDraft.value.trim();
  if (!title) {
    courseTitleError.value = 'Der Kursname darf nicht leer sein.';
    nextTick(() => courseTitleInput.value?.focus());
    return;
  }
  if (title === store.activeCourse.title) {
    cancelCourseTitle();
    return;
  }
  courseTitleBusy.value = true;
  courseTitleError.value = '';
  try {
    await store.renameCourse(store.activeCourse.id, { title });
    editingCourseTitle.value = false;
  } catch (error) {
    courseTitleError.value = error?.message || 'Kursname konnte nicht gespeichert werden.';
    nextTick(() => courseTitleInput.value?.focus());
  } finally {
    courseTitleBusy.value = false;
  }
}
function onRenameCourseCard(course) {
  if (!course || courseCardTitleBusy.value) return;
  editingCourseCardId.value = course.id;
  courseCardTitleDraft.value = course.title;
  courseCardTitleError.value = '';
  focusCourseCardTitle(true);
}
function focusCourseCardTitle(select = false) {
  nextTick(() => {
    const input = document.querySelector('input[aria-label="Kursname in der Kachel"]');
    if (select) input?.select();
    else input?.focus();
  });
}
function cancelCourseCardTitle() {
  editingCourseCardId.value = null;
  courseCardTitleDraft.value = '';
  courseCardTitleError.value = '';
}
async function saveCourseCardTitle() {
  const courseId = editingCourseCardId.value;
  if (!courseId || courseCardTitleBusy.value) return;
  const course = store.courses.find((item) => item.id === courseId);
  const title = courseCardTitleDraft.value.trim();
  if (!title) {
    courseCardTitleError.value = 'Der Kursname darf nicht leer sein.';
    focusCourseCardTitle();
    return;
  }
  if (title === course?.title) {
    cancelCourseCardTitle();
    return;
  }
  courseCardTitleBusy.value = true;
  courseCardTitleError.value = '';
  try {
    await store.renameCourse(courseId, { title });
    cancelCourseCardTitle();
  } catch (error) {
    courseCardTitleError.value = error?.message || 'Kursname konnte nicht gespeichert werden.';
    focusCourseCardTitle();
  } finally {
    courseCardTitleBusy.value = false;
  }
}
async function onDeleteCourse(course) {
  if (!course || !window.confirm(`„${course.title}“ löschen?`)) return;
  deletingCourseIds.value = new Set([...deletingCourseIds.value, course.id]);
  courseCardTitleError.value = '';
  try {
    if (editingCourseCardId.value === course.id) cancelCourseCardTitle();
    await store.removeCourse(course.id);
  } catch (error) {
    courseCardTitleError.value = error?.message || 'Kurs konnte nicht gelöscht werden.';
  } finally {
    const pending = new Set(deletingCourseIds.value);
    pending.delete(course.id);
    deletingCourseIds.value = pending;
  }
}
function onCreateSheet() {
  if (!store.activeCourseId) return;
  openDialog({ kind: 'sheet', name: '' });
}
async function toggleFavorite(sheet) {
  if (!sheet || favoriteBusy.value) return;
  const activating = !sheet.is_favorite;
  if (activating) {
    favoriteAnimating.value = true;
    if (favoriteAnimTimer) window.clearTimeout(favoriteAnimTimer);
    favoriteAnimTimer = window.setTimeout(() => {
      favoriteAnimating.value = false;
      favoriteAnimTimer = null;
    }, 480);
  }
  favoriteBusy.value = true;
  try {
    await store.patchSheet(sheet.id, { is_favorite: activating });
  } finally {
    favoriteBusy.value = false;
  }
}
function onRenameSheet(sheet) {
  if (!sheet || sheetTitleBusy.value) return;
  editingSheetId.value = sheet.id;
  sheetTitleDraft.value = sheet.title;
  sheetTitleError.value = '';
  focusSheetTitle(true);
}
function focusSheetTitle(select = false) {
  nextTick(() => {
    const input = document.querySelector('input[aria-label="Lernblattname"]');
    if (select) input?.select();
    else input?.focus();
  });
}
function cancelSheetTitle() {
  editingSheetId.value = null;
  sheetTitleDraft.value = '';
  sheetTitleError.value = '';
}
async function saveSheetTitle() {
  const sheetId = editingSheetId.value;
  if (!sheetId || sheetTitleBusy.value) return;
  const sheet = courseSheets.value.find((item) => item.id === sheetId);
  const title = sheetTitleDraft.value.trim();
  if (!title) {
    sheetTitleError.value = 'Der Lernblattname darf nicht leer sein.';
    focusSheetTitle();
    return;
  }
  if (title === sheet?.title) {
    cancelSheetTitle();
    return;
  }
  sheetTitleBusy.value = true;
  sheetTitleError.value = '';
  try {
    await store.patchSheet(sheetId, { title });
    cancelSheetTitle();
  } catch (error) {
    sheetTitleError.value = error?.message || 'Lernblattname konnte nicht gespeichert werden.';
    focusSheetTitle();
  } finally {
    sheetTitleBusy.value = false;
  }
}
async function onDeleteSheet(sheet) {
  if (!window.confirm(`„${sheet.title}“ löschen?`)) return;
  deletingSheetIds.value = new Set([...deletingSheetIds.value, sheet.id]);
  try {
    if (editingSheetId.value === sheet.id) cancelSheetTitle();
    const wasOpen = openSheetId.value === sheet.id;
    await store.removeSheet(sheet.id);
    if (wasOpen) closeSheet();
  } catch (error) {
    sheetTitleError.value = error?.message || 'Lernblatt konnte nicht gelöscht werden.';
  } finally {
    const pending = new Set(deletingSheetIds.value);
    pending.delete(sheet.id);
    deletingSheetIds.value = pending;
  }
}

watch(
  () => [route.query.course, route.query.sheet, route.query.learn, route.query.scope],
  () => { void syncNavigationFromRoute(); },
);
watch([view, openSheetId], ([currentView, currentSheet]) => {
  learnStartOptionsOpen.value = false;
  if (editingCourseTitle.value && (currentView !== 'course' || currentSheet)) cancelCourseTitle();
  if (editingCourseCardId.value && currentView !== 'home') cancelCourseCardTitle();
  if (editingSheetId.value && currentView !== 'course') cancelSheetTitle();
});

function handleLearnKey(event) {
  if (!learning.value || !currentLearn.value || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
  const tag = event.target?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'BUTTON') return;
  const status = { 1: 'weak', 2: 'medium', 3: 'strong' }[event.key];
  if (currentLearnFormat.value === 'sequence') {
    const card = currentLearn.value;
    if (!card.seqChecked) {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); checkSeq(); }
      return;
    }
    if (status) { event.preventDefault(); void assess(status); }
    return;
  }
  if (!revealed.value && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    revealed.value = true;
    return;
  }
  if (!revealed.value) return;
  if (status) {
    event.preventDefault();
    void assess(status);
  }
}

const DEFAULT_KIND = 'fakt';
function onEditCard(card) {
  const items = cards.value.map((item) => ({
    cardId: item.id,
    noteId: item.source_note_id || null,
    marker: { node_pm_id: item.source_pm_id || null, snippet: '' },
    cardKind: item.kind,
    kindAiTried: true,
    kindAiBusy: false,
    kindTouched: false,
    front: item.front,
    back: item.back || '',
    steps: Array.isArray(item.payload?.steps) ? item.payload.steps.map((s) => String(s || '')) : [],
    fromNote: null,
  }));
  const index = Math.max(0, items.findIndex((item) => item.cardId === card.id));
  openDialog({ kind: 'card-edit', items, index });
}
async function onDeleteCard(card) {
  if (!window.confirm('Karte löschen?')) return;
  await store.removeCard(card.id, openSheetId.value);
}

async function onDeleteLearningRun(run) {
  if (!run || deletingRunIds.value.has(run.id)) return;
  if (!window.confirm('Diesen Lerndurchlauf löschen?')) return;
  deletingRunIds.value = new Set([...deletingRunIds.value, run.id]);
  runDeleteError.value = '';
  try {
    await store.removeLearningRun(run.id);
  } catch (error) {
    runDeleteError.value = error?.message || 'Lerndurchlauf konnte nicht gelöscht werden.';
  } finally {
    const pending = new Set(deletingRunIds.value);
    pending.delete(run.id);
    deletingRunIds.value = pending;
  }
}

// --- Nachbereitung: Warteschlange (Marker → Karte) ---------------------------
const current = computed(() => {
  const d = dialog.value;
  return d && ['queue', 'card-edit'].includes(d.kind) ? d.items[d.index] || null : null;
});
// Wäre nach dem Übernehmen kein offener Marker mehr übrig?
const lastOpen = computed(() => {
  const d = dialog.value;
  if (!d || d.kind !== 'queue') return false;
  return d.items.every((it, i) => it.status === 'done' || i === d.index);
});
// Frage ↔ Antwort tauschen (falls die Typ-Vorbelegung mal danebenlag).
function swapSides() {
  const it = current.value;
  if (!it) return;
  [it.front, it.back] = [it.back, it.front];
  if (it.fromNote === 'front') it.fromNote = 'back';
  else if (it.fromNote === 'back') it.fromNote = 'front';
}

// --- Schrittfolge-Editor (Prozess/Anleitung) ---
const currentIsSequence = computed(() => !!current.value && cardFormat(current.value.cardKind) === 'sequence');
function ensureSteps(it) { if (!Array.isArray(it.steps)) it.steps = []; return it.steps; }
function addStep(at) {
  const it = current.value; if (!it) return;
  const steps = ensureSteps(it);
  steps.splice(at ?? steps.length, 0, '');
}
function removeStep(i) {
  const it = current.value; if (!it) return;
  ensureSteps(it).splice(i, 1);
}
function moveStep(i, dir) {
  const it = current.value; if (!it) return;
  const steps = ensureSteps(it);
  const j = i + dir;
  if (j < 0 || j >= steps.length) return;
  [steps[i], steps[j]] = [steps[j], steps[i]];
}

function openQueue(group, startIndex = 0) {
  const groups = markerNoteGroups.value;
  const items = [];
  let selectedIndex = 0;
  for (const queueGroup of groups) {
    const groupStart = items.length;
    for (const m of queueGroup.markers) {
      // Frage-artige Marker (Warum/Aufgabe/Analyse) sind schon die Vorderseite;
      // Aussagen (Fakt/Prozess/…) sind die Antwort → das jeweils andere Feld bleibt leer.
      const asPrompt = PROMPT_MARKER_KINDS.has(m.kind);
      const snippet = m.snippet || '';
      const hasDraft = Boolean(m.draft_card_id);
      items.push({
        noteId: queueGroup.noteId,
        noteTitle: queueGroup.noteTitle,
        courseId: m.course_id || null,
        marker: m,
        cardKind: m.draft_kind || MARKER_TO_KIND[m.kind] || store.activeCourse?.default_artifact_type || DEFAULT_KIND,
        kindAiTried: false,
        kindAiBusy: false,
        kindTouched: false,
        front: hasDraft ? (m.draft_front || '') : (asPrompt ? snippet : ''),
        back: hasDraft ? (m.draft_back || '') : (asPrompt ? '' : snippet),
        steps: Array.isArray(m.draft_steps) ? m.draft_steps.map((s) => String(s || '')) : [],
        fromNote: asPrompt ? 'front' : 'back',
        status: 'open',
      });
    }
    if (queueGroup.noteId === group.noteId) {
      selectedIndex = groupStart + Math.min(Math.max(startIndex, 0), Math.max(queueGroup.markers.length - 1, 0));
    }
  }
  openDialog({
    kind: 'queue',
    items,
    index: selectedIndex,
  });
}

function focusEditorPrev() { const d = dialog.value; if (d && d.index > 0) { dialogError.value = ''; d.index -= 1; } }
function focusEditorNext() { const d = dialog.value; if (d && d.index < d.items.length - 1) { dialogError.value = ''; d.index += 1; } }

// Zum nächsten noch offenen Marker springen; ist keiner mehr offen → abschließen.
function advanceQueue() {
  const d = dialog.value; if (!d) return;
  for (let step = 1; step <= d.items.length; step += 1) {
    const i = (d.index + step) % d.items.length;
    if (d.items[i].status !== 'done') { d.index = i; dialogError.value = ''; return; }
  }
  finishQueue();
}

// Schließt die Warteschlange und frischt Startseite/Board einmal auf.
async function finishQueue() {
  const wasQueue = dialog.value?.kind === 'queue';
  closeDialog();
  if (wasQueue) await store.refreshAfterPromote();
}

function closeCardEditor() {
  if (dialog.value?.kind !== 'card-edit') return;
  closeDialog();
}

function closeFocusEditor() {
  if (cardEditorOpen.value) closeCardEditor();
  else void finishQueue();
}

async function saveCurrentCard() {
  const d = dialog.value;
  const it = current.value;
  if (!d || d.kind !== 'card-edit' || !it || dialogBusy.value) return;
  dialogBusy.value = true;
  dialogError.value = '';
  try {
    await store.patchCard(it.cardId, openSheetId.value, {
      kind: it.cardKind,
      front: it.front.trim(),
      back: it.back.trim() || null,
      payload: itemPayload(it),
    });
    it.front = it.front.trim();
    it.back = it.back.trim();
  } catch (err) {
    dialogError.value = err?.message || 'Änderungen konnten nicht gespeichert werden.';
  } finally {
    dialogBusy.value = false;
  }
}

// Typspezifisches Payload eines Editor-Items (nur Schrittfolgen tragen Inhalt).
function itemPayload(it) {
  if (cardFormat(it.cardKind) !== 'sequence') return {};
  return { steps: (it.steps || []).map((s) => String(s || '').trim()).filter(Boolean) };
}

async function acceptCurrent() {
  const d = dialog.value;
  if (!d || dialogBusy.value) return;
  const it = d.items[d.index];
  if (!it.courseId) { dialogError.value = 'Bitte einen Kurs wählen.'; return; }
  dialogBusy.value = true;
  try {
    const payload = {
      note_id: it.noteId,
      node_pm_id: it.marker.node_pm_id,
      kind: it.cardKind,
      front: it.front.trim(),
      back: it.back.trim() || null,
      payload: itemPayload(it),
      course_id: it.courseId,
      bind_note: false,
    };
    await store.promoteMarker(payload, false); // Auffrischen erst beim Schließen
    it.status = 'done';
    advanceQueue();
  } catch (err) {
    dialogError.value = err?.message || 'Aktion fehlgeschlagen.';
  } finally {
    dialogBusy.value = false;
  }
}

// --- Anlege-/Bearbeiten-Dialog ---
const dialog = ref(null);
const dialogError = ref('');
const dialogBusy = ref(false);
const dialogInput = ref(null);
const notePreviewTheme = ref('dark');
function toggleNotePreviewTheme() {
  notePreviewTheme.value = notePreviewTheme.value === 'dark' ? 'light' : 'dark';
}

const queueOpen = computed(() => dialog.value?.kind === 'queue');
const cardEditorOpen = computed(() => dialog.value?.kind === 'card-edit');
const focusEditorOpen = computed(() => queueOpen.value || cardEditorOpen.value);
const queueDone = computed(() => dialog.value?.items?.filter((it) => it.status === 'done').length || 0);
const editorMarkerStates = computed(() => {
  const map = {};
  for (const it of dialog.value?.items || []) {
    const pmId = it.marker?.node_pm_id;
    if (pmId && it.noteId === current.value?.noteId) map[pmId] = it.status === 'done' ? 'done' : 'open';
  }
  return map;
});
// Farbton des Fokusmodus folgt der gewählten Kartenart.
const NQ_TINTS = {
  fakt: 'oklch(0.80 0.13 150)',
  verstaendnis: 'oklch(0.80 0.10 200)',
  uebung: 'oklch(0.83 0.13 72)',
  prozess: 'oklch(0.78 0.11 265)',
  zusammenhang: 'oklch(0.79 0.11 330)',
  prozedural: 'oklch(0.78 0.05 235)',
};
const nqTint = computed(() => NQ_TINTS[current.value?.cardKind] || NQ_TINTS.verstaendnis);
const { setNightSidebar } = useSidebarAppearance();
watch(() => learning.value || focusEditorOpen.value, (open) => setNightSidebar(open), { immediate: true });
watch(focusEditorOpen, (open, wasOpen) => {
  if (open && !wasOpen) notePreviewTheme.value = 'dark';
});
const nqFront = ref(null);
const nqBack = ref(null);
const nqAiBusy = ref('');
function selectQueueKind(kind) {
  const it = current.value;
  if (!it) return;
  it.kindTouched = true;
  it.cardKind = kind;
}
// Frage/Antwort umschließen ihren Inhalt. Moderne Browser regeln das nativ über
// CSS field-sizing:content (robust, egal ob per Tastatur, KI oder Kartenwechsel
// gesetzt); nur als Fallback rechnen wir die Höhe per JS.
const SUPPORTS_FIELD_SIZING = typeof CSS !== 'undefined' && CSS.supports?.('field-sizing', 'content');
const NQ_EXTRA_HEIGHT = 24; // „ein bisschen mehr" für die Optik (nur Fallback)
function fitNqArea(el) {
  if (!el) return;
  if (SUPPORTS_FIELD_SIZING) { el.style.height = ''; return; }
  el.style.height = 'auto';
  el.style.height = `${el.scrollHeight + NQ_EXTRA_HEIGHT}px`;
}
function fitNqFront(el = nqFront.value) { fitNqArea(el); }
function fitNqBack(el = nqBack.value) { fitNqArea(el); }
function cleanQueueAiText(value, field) {
  let text = String(value || '').trim();
  text = text.replace(/^```(?:text|markdown)?\s*/i, '').replace(/\s*```$/, '').trim();
  text = text.replace(field === 'front' ? /^frage\s*:\s*/i : /^antwort\s*:\s*/i, '').trim();
  text = text.replace(/^[-*]\s+/, '').trim();
  if ((text.startsWith('„') && text.endsWith('“')) || (text.startsWith('"') && text.endsWith('"'))) {
    text = text.slice(1, -1).trim();
  }
  return text;
}
const QUEUE_KIND_FROM_AI = {
  fakt: 'fakt',
  verstandnis: 'verstaendnis',
  verstaendnis: 'verstaendnis',
  ubung: 'uebung',
  uebung: 'uebung',
  prozess: 'prozess',
  vergleich: 'zusammenhang',
  zusammenhang: 'zusammenhang',
  anleitung: 'prozedural',
  prozedural: 'prozedural',
};
function parseQueueKind(value) {
  const normalized = String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('de-DE');
  for (const [label, kind] of Object.entries(QUEUE_KIND_FROM_AI)) {
    if (new RegExp(`(?:^|[^a-z])${label}(?:$|[^a-z])`).test(normalized)) return kind;
  }
  return null;
}
async function suggestQueueKind(it, { force = false } = {}) {
  if (!it || (!force && it.kindAiTried)) return;
  it.kindAiTried = true;
  const markerText = String(it.marker?.snippet || '').trim()
    || [it.front, it.back].map((value) => String(value || '').trim()).filter(Boolean).join('\n');
  const paragraphContext = String(it.marker?.context || markerText).trim();
  if (!markerText) return;
  it.kindAiBusy = true;
  let generated = '';
  try {
    await streamNoteText({
      instruction: [
        'Ordne die markierte Passage genau einer Lernkartenart zu:',
        'Fakt = konkrete Information oder Definition;',
        'Verständnis = Erklärung, Begründung oder Warum-Zusammenhang;',
        'Übung = Aufgabe oder anzuwendendes Problem;',
        'Prozess = Ablauf oder Reihenfolge;',
        'Vergleich = Gegenüberstellung oder Beziehung;',
        'Anleitung = konkrete Handlungsanweisung.',
        'Gib ausschließlich eines dieser Wörter aus: Fakt, Verständnis, Übung, Prozess, Vergleich, Anleitung.',
      ].join(' '),
      length_instruction: 'Genau ein Wort.',
      note_context: paragraphContext,
      context_scope: 'note',
      selected_text: markerText,
      // Dokumentkontext erzwingt serverseitig immer das lokale Ollama-Modell.
      document_context: paragraphContext,
    }, {
      onEvent: (event) => {
        if (event.type === 'delta') generated += event.text || '';
      },
    });
    const suggestedKind = parseQueueKind(generated);
    if (suggestedKind && (force || !it.kindTouched)) it.cardKind = suggestedKind;
  } catch {
    // Die deterministische Marker-Zuordnung bleibt als verlässlicher Fallback bestehen.
  } finally {
    it.kindAiBusy = false;
  }
}
function generateQueueKind() {
  return suggestQueueKind(current.value, { force: true });
}
async function generateQueueField(field) {
  const it = current.value;
  const d = dialog.value;
  if (!it || !d || nqAiBusy.value) return;
  const markerText = String(it.marker?.snippet || '').trim();
  const paragraphContext = String(it.marker?.context || markerText).trim();
  const question = String(it.front || '').trim();
  const answer = String(it.back || '').trim();
  const sourceText = markerText || [question, answer].filter(Boolean).join('\n');
  const noteContext = (d.kind === 'card-edit'
    ? d.items.map((item) => [item.front, item.back].filter(Boolean).join('\n'))
    : d.items
      .filter((item) => item.noteId === it.noteId)
      .map((item) => String(item.marker?.context || item.marker?.snippet || '').trim()))
    .filter(Boolean)
    .join('\n\n')
    .slice(0, 12000);
  const type = kindLabel(it.cardKind);
  const typeGuidance = {
    fakt: 'Frage eine einzelne konkrete Information oder Definition ab. Die Antwort nennt diese präzise und ohne Abschweifung.',
    verstaendnis: 'Prüfe einen Warum-, Wie- oder Bedeutungszusammenhang. Die Antwort erklärt Ursache und Zusammenhang in eigenen Worten.',
    uebung: 'Formuliere eine konkrete Anwendungsaufgabe. Die Antwort zeigt den passenden Lösungsweg oder das überprüfbare Ergebnis.',
    prozess: 'Frage nach einem Ablauf oder einer Reihenfolge. Die Antwort gibt die wesentlichen Schritte in der richtigen Ordnung wieder.',
    zusammenhang: 'Verlange einen Vergleich oder eine Beziehung. Die Antwort benennt die entscheidenden Gemeinsamkeiten, Unterschiede oder Wechselwirkungen.',
    prozedural: 'Frage danach, wie etwas praktisch ausgeführt wird. Die Antwort formuliert eine klare, handlungsorientierte Anleitung.',
  }[it.cardKind] || 'Formuliere Frage und Antwort passend zur gewählten Lernkartenart.';
  const instruction = field === 'front'
    ? `Formuliere eine einzelne präzise Lernfrage der Art „${type}“. Verbindliche Typvorgabe: ${typeGuidance} Die passende Antwort lautet: ${answer || sourceText}. Nutze ausschließlich den bereitgestellten Kontext. Gib nur die Frage ohne Überschrift oder Erläuterung aus.`
    : `Formuliere eine knappe, vollständige Antwort auf diese Lernfrage: ${question || sourceText}. Kartenart: „${type}“. Verbindliche Typvorgabe: ${typeGuidance} Nutze ausschließlich den bereitgestellten Kontext und erfinde keine Fakten. Gib nur die Antwort ohne Überschrift oder Erläuterung aus.`;

  nqAiBusy.value = field;
  dialogError.value = '';
  let generated = '';
  try {
    await streamNoteText({
      instruction,
      length_instruction: field === 'front' ? 'Genau eine klare Frage.' : 'So kurz wie möglich, so vollständig wie nötig.',
      note_context: noteContext,
      context_scope: 'note',
      selected_text: sourceText,
      document_context: d.kind === 'card-edit' ? sourceText : paragraphContext,
    }, {
      onEvent: (event) => {
        if (event.type === 'delta') generated += event.text || '';
      },
    });
    if (current.value !== it) return;
    const text = cleanQueueAiText(generated, field);
    if (!text) throw new Error('Die KI hat keinen Text erzeugt.');
    it[field] = text;
    if (field === 'back') await nextTick(fitNqBack);
  } catch (err) {
    dialogError.value = err?.message || 'KI-Vorschlag fehlgeschlagen.';
  } finally {
    nqAiBusy.value = '';
  }
}
function parseStepsFromText(text) {
  return String(text || '')
    .replace(/^```(?:text|markdown)?\s*/i, '')
    .replace(/\s*```$/, '')
    .split('\n')
    .map((line) => line.replace(/^\s*(?:\d+[.)]|[-*•])\s*/, '').trim())
    .filter(Boolean)
    .slice(0, 30);
}
async function generateQueueSteps() {
  const it = current.value;
  const d = dialog.value;
  if (!it || !d || nqAiBusy.value) return;
  const markerText = String(it.marker?.snippet || '').trim();
  const paragraphContext = String(it.marker?.context || markerText).trim();
  const question = String(it.front || '').trim();
  const sourceText = markerText || question;
  const noteContext = (d.kind === 'card-edit'
    ? d.items.map((item) => [item.front, ...(item.steps || [])].filter(Boolean).join('\n'))
    : d.items
      .filter((item) => item.noteId === it.noteId)
      .map((item) => String(item.marker?.context || item.marker?.snippet || '').trim()))
    .filter(Boolean)
    .join('\n\n')
    .slice(0, 12000);
  const instruction = `Extrahiere aus dem Kontext die wesentlichen Schritte des Ablaufs „${question || sourceText}“ in der richtigen Reihenfolge. Gib ausschließlich eine nummerierte Liste aus – pro Zeile genau ein Schritt, knapp formuliert, ohne Einleitung, ohne Überschrift, ohne Erklärungen. Nutze nur den bereitgestellten Kontext und erfinde nichts.`;

  nqAiBusy.value = 'steps';
  dialogError.value = '';
  let generated = '';
  try {
    await streamNoteText({
      instruction,
      length_instruction: 'Drei bis acht kurze Schritte.',
      note_context: noteContext,
      context_scope: 'note',
      selected_text: sourceText,
      document_context: d.kind === 'card-edit' ? sourceText : paragraphContext,
    }, {
      onEvent: (event) => { if (event.type === 'delta') generated += event.text || ''; },
    });
    if (current.value !== it) return;
    const steps = parseStepsFromText(generated);
    if (steps.length < 2) throw new Error('Die KI hat keine verwertbaren Schritte erzeugt.');
    it.steps = steps;
  } catch (err) {
    dialogError.value = err?.message || 'KI-Vorschlag fehlgeschlagen.';
  } finally {
    nqAiBusy.value = '';
  }
}
function onSelectMarker(pmId) {
  const d = dialog.value;
  const i = d?.items?.findIndex((it) => it.noteId === current.value?.noteId && it.marker.node_pm_id === pmId);
  if (d && i >= 0) { d.index = i; dialogError.value = ''; }
}
// Fokus ins leere Feld (die Aufgabe), sobald ein anderer Marker aktiv wird.
watch(() => [focusEditorOpen.value, dialog.value?.index], async ([open]) => {
  if (!open) return;
  await nextTick();
  fitNqFront();
  fitNqBack();
  const it = current.value;
  if (queueOpen.value) void suggestQueueKind(it);
  const el = cardEditorOpen.value ? nqFront.value : (it && it.fromNote === 'front' ? nqBack.value : nqFront.value);
  try { el?.focus({ preventScroll: true }); } catch { /* Fokus ist optional */ }
});
watch(() => current.value?.front, async () => {
  if (!focusEditorOpen.value) return;
  await nextTick();
  fitNqFront();
}, { flush: 'post' });
watch(() => current.value?.back, async () => {
  if (!focusEditorOpen.value) return;
  await nextTick();
  fitNqBack();
}, { flush: 'post' });
function handleFocusEditorKey(e) {
  if (!focusEditorOpen.value) return;
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault();
    if (cardEditorOpen.value) void saveCurrentCard();
    else void acceptCurrent();
  } else if (e.key === 'Escape' && !dialogBusy.value) {
    e.preventDefault();
    closeFocusEditor();
  }
}

const cardKinds = [
  { value: 'fakt', label: 'Fakt' },
  { value: 'verstaendnis', label: 'Verständnis' },
  { value: 'uebung', label: 'Übung' },
  { value: 'prozess', label: 'Prozess' },
  { value: 'zusammenhang', label: 'Vergleich' },
  { value: 'prozedural', label: 'Anleitung' },
];
const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return '';
  if (d.kind === 'course') return 'Neuer Kurs';
  if (d.kind === 'sheet') return 'Neues Lernblatt';
  return '';
});
const dialogSubmitLabel = computed(() => 'Anlegen');
function openDialog(shape) {
  dialogError.value = '';
  dialog.value = shape;
  nextTick(() => { try { dialogInput.value?.focus(); } catch { /* Fokus ist optional */ } });
}
function closeDialog() { dialog.value = null; dialogError.value = ''; }
async function submitDialog() {
  const d = dialog.value;
  if (!d || dialogBusy.value) return;
  dialogBusy.value = true;
  try {
    if (!d.name.trim()) { dialogError.value = 'Bitte einen Namen eingeben.'; return; }
    if (d.kind === 'course') {
      const created = await store.addCourse({ title: d.name.trim() });
      openCourse(created.id);
    }
    else if (d.kind === 'sheet') await store.addSheet({ course_id: store.activeCourseId, title: d.name.trim(), scope: 'topic' });
    dialog.value = null;
  } catch (err) {
    dialogError.value = err?.message || 'Aktion fehlgeschlagen.';
  } finally {
    dialogBusy.value = false;
  }
}

onMounted(async () => {
  await Promise.all([store.fetchAllSheets(), store.fetchOpenMarkers(), store.fetchCourses()]);
  navigationReady.value = true;
  if (typeof route.query.course !== 'string' && typeof route.query.sheet !== 'string') {
    const saved = readRememberedNavigation();
    if (saved?.courseId) {
      const query = { course: saved.courseId };
      if (saved.sheetId) query.sheet = saved.sheetId;
      await router.replace({ name: 'lernraum', query });
    }
  }
  await syncNavigationFromRoute();
  window.addEventListener('keydown', handleLearnKey);
  window.addEventListener('keydown', handleFocusEditorKey);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleLearnKey);
  window.removeEventListener('keydown', handleFocusEditorKey);
  if (favoriteAnimTimer) window.clearTimeout(favoriteAnimTimer);
  if (learnProgressPulseTimer) window.clearTimeout(learnProgressPulseTimer);
  if (progressFeedbackTimer) window.clearTimeout(progressFeedbackTimer);
  if (chartIntroTimer) window.clearTimeout(chartIntroTimer);
  setNightSidebar(false);
});
</script>

<style>
.lernraum-panel {
  --pm-font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  --pm-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
  --pm-bg: #ffffff;
  --pm-surface-card: #ffffff;
  --pm-surface-reader: oklch(0.968 0.006 210);
  --pm-border: oklch(0.900 0.008 210);
  --pm-text: oklch(0.200 0.015 220);
  --pm-text-muted: oklch(0.475 0.015 220);
  --pm-accent: oklch(0.475 0.095 205);
  --pm-accent-text: oklch(0.400 0.090 205);
  --pm-on-accent: #ffffff;
  --pm-selected: oklch(0.948 0.026 205);
  --pm-chip-bg: oklch(0.945 0.008 210);
  --pm-chip-text: oklch(0.320 0.015 220);
  --pm-chip-count: oklch(0.560 0.014 220);
  --pm-track: oklch(0.930 0.008 210);
  --pm-star: oklch(0.630 0.130 72);
  --pm-success: oklch(0.490 0.100 150);
  --pm-danger: oklch(0.520 0.150 27);
  position: relative;
  min-width: 0; height: 100%; min-height: 0; display: flex; flex-direction: column;
  overflow: hidden; background: var(--pm-surface-reader); color: var(--pm-text); font-family: var(--pm-font-sans);
}
:root[data-theme="dark"] .lernraum-panel {
  --pm-bg: oklch(0.275 0.014 222);
  --pm-surface-card: oklch(0.345 0.012 222);
  --pm-surface-reader: oklch(0.250 0.014 222);
  --pm-border: oklch(0.395 0.014 222);
  --pm-text: oklch(0.965 0.005 220);
  --pm-text-muted: oklch(0.760 0.014 220);
  --pm-accent: oklch(0.760 0.105 200);
  --pm-accent-text: oklch(0.845 0.090 200);
  --pm-on-accent: oklch(0.200 0.030 200);
  --pm-selected: oklch(0.375 0.050 205);
  --pm-chip-bg: oklch(0.395 0.014 222);
  --pm-chip-text: oklch(0.945 0.006 220);
  --pm-chip-count: oklch(0.775 0.014 220);
  --pm-track: oklch(0.375 0.014 222);
  --pm-star: oklch(0.800 0.130 72);
  --pm-success: oklch(0.760 0.105 150);
  --pm-danger: oklch(0.720 0.140 27);
}

/* Buttons */
.lernraum-panel .lr-btn { border: 0; cursor: pointer; font-family: var(--pm-font-sans); border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; }
.lernraum-panel .lr-btn--primary { background: var(--pm-accent); color: var(--pm-on-accent); font-weight: 620; }
.lernraum-panel .lr-btn--primary:hover:not([disabled]) { filter: brightness(1.06); }
.lernraum-panel .lr-btn--secondary { background: var(--pm-bg); border: 1px solid var(--pm-border); color: var(--pm-text); }
.lernraum-panel .lr-btn--secondary:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-btn--ghost { background: transparent; border: 1px solid var(--pm-border); color: var(--pm-text-muted); }
.lernraum-panel .lr-btn--ghost:hover { background: var(--pm-surface-reader); color: var(--pm-text); }
.lernraum-panel .lr-btn--danger-text { color: var(--pm-danger); }
.lernraum-panel .lr-btn--sm { height: 30px; padding: 0 13px; font-size: 12.5px; }
.lernraum-panel .lr-btn--md { height: 36px; padding: 0 18px; font-size: 13.5px; }
.lernraum-panel .lr-btn[disabled] { opacity: .45; cursor: default; }

/* Titelblöcke */
.lernraum-panel .lr-title-block { display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-title { font: 660 24px/1.2 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-subtitle { font-size: 13px; color: var(--pm-text-muted); }

/* Startseite */
.lernraum-panel .lr-home-head { flex: none; display: flex; align-items: center; gap: 16px; padding: 22px 40px 16px; background: var(--pm-bg); border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-home-head .lr-btn { margin-left: auto; }
.lernraum-panel .lr-home-body { flex: 1; min-height: 0; overflow: auto; padding: 26px 40px 32px; display: flex; flex-direction: column; gap: 30px; }
.lernraum-panel .lr-section { display: flex; flex-direction: column; gap: 14px; }
.lernraum-panel .lr-section-head { display: flex; align-items: baseline; gap: 12px; }
.lernraum-panel .lr-overline { font: 620 11.5px/1.4 var(--pm-font-sans); letter-spacing: .09em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-section-meta { font-size: 12.5px; color: var(--pm-text-muted); }

.lernraum-panel .lr-nb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px; }
.lernraum-panel .lr-nb-card { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); padding: 18px 20px; display: flex; flex-direction: column; gap: 11px; }
.lernraum-panel .lr-nb-top { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-nb-course { font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-nb-count { margin-left: auto; font-size: 11.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-nb-title { font: 620 15.5px/1.3 var(--pm-font-sans); letter-spacing: -.015em; text-wrap: pretty; }
.lernraum-panel .lr-nb-metaline { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-progress { display: flex; gap: 4px; margin-top: 2px; }
.lernraum-panel .lr-progress-seg { flex: 1; height: 4px; border-radius: 2px; background: var(--pm-track); }
.lernraum-panel .lr-progress-seg--on { background: var(--pm-accent); }
.lernraum-panel .lr-nb-actions { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.lernraum-panel .lr-nb-later { font-size: 12px; color: var(--pm-text-muted); cursor: default; }

.lernraum-panel .lr-nb-empty { border: 1px dashed var(--pm-border); border-radius: 14px; padding: 22px; }
.lernraum-panel .lr-nb-empty p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-nb-empty .lr-nb-empty-hint { margin-top: 6px; font-size: 12.5px; color: var(--pm-text-muted); line-height: 1.55; }

/* Nachbereitungs-Eingang: markierte Notizzeilen, nach Notiz gruppiert */
.lernraum-panel .lr-nb-list { display: flex; flex-direction: column; gap: 14px; }
.lernraum-panel .lr-nb-note { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); overflow: hidden; }
.lernraum-panel .lr-nb-note-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 11px 16px; border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-nb-note-title { font: 620 14px/1.3 var(--pm-font-sans); letter-spacing: -.01em; }
.lernraum-panel .lr-nb-assign { margin-left: auto; font-size: 11.5px; color: var(--pm-accent-text); background: var(--pm-selected); padding: 2px 9px; border-radius: 20px; }
.lernraum-panel .lr-nb-assign--none { color: var(--pm-text-muted); background: var(--pm-chip-bg); }
.lernraum-panel .lr-nb-note-cta { flex: none; }
.lernraum-panel .lr-marker-rows { list-style: none; margin: 0; padding: 0; }
.lernraum-panel .lr-marker-row { display: flex; align-items: center; gap: 12px; padding: 11px 16px; border-top: 1px solid var(--pm-border); cursor: pointer; }
.lernraum-panel .lr-marker-row:first-child { border-top: 0; }
.lernraum-panel .lr-marker-row:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-marker-kind { flex: none; display: inline-flex; align-items: center; height: 19px; padding: 0 8px; border-radius: 20px; font: 620 10.5px/1 var(--pm-font-sans); letter-spacing: .05em; text-transform: uppercase; }
.lernraum-panel .lr-marker-snippet { flex: 1; min-width: 0; font: 400 13.5px/1.5 var(--pm-font-sans); color: var(--pm-text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.lernraum-panel .lr-marker-go { flex: none; color: var(--pm-text-muted); font-size: 18px; line-height: 1; }

/* Nachbereiten im Fokus: Notiz im Kontext links, Karte rechts. */
.lernraum-panel .lr-nq { overflow: hidden; }
.lernraum-panel .lr-nq-head { flex: none; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px; padding: 16px clamp(20px, 3vw, 36px) 12px; }
.lernraum-panel .lr-learn-head { position: relative; grid-template-columns: 1fr auto 1fr; }
.lernraum-panel .lr-learning-focus--exit-warning .lr-learn-head { z-index: 101; }
.lernraum-panel .lr-learn-head > .lr-nq-title,
.lernraum-panel .lr-learn-head > .lr-learn-progress-ring { transition: opacity .18s ease, filter .18s ease; }
.lernraum-panel .lr-learning-focus--exit-warning .lr-learn-head > .lr-nq-title,
.lernraum-panel .lr-learning-focus--exit-warning .lr-learn-head > .lr-learn-progress-ring { opacity: .38; filter: saturate(.3); }
.lernraum-panel .lr-nq-title { min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 2px; text-align: center; }
.lernraum-panel .lr-nq-title strong { max-width: 100%; overflow: hidden; font: 660 16px/1.25 var(--pm-font-sans); text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-nq-title span { color: var(--pm-text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.lernraum-panel .lr-nq-nav { display: flex; gap: 6px; }
.lernraum-panel .lr-nq-arrow { display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border: 1px solid var(--pm-border); border-radius: 50%; background: var(--pm-surface-card); color: var(--pm-text-muted); cursor: pointer; transition: background .15s, color .15s; }
.lernraum-panel .lr-nq-arrow svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.lernraum-panel .lr-nq-arrow:hover:not(:disabled) { background: var(--pm-selected); color: var(--pm-accent-text); }
.lernraum-panel .lr-nq-arrow:disabled { opacity: .35; cursor: default; }
.lernraum-panel .lr-learn-progress-ring { position: relative; justify-self: end; display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; background: conic-gradient(var(--pm-accent) var(--learn-progress), var(--pm-track) 0); color: var(--pm-text); font: 650 10.5px/1 var(--pm-font-mono); }
.lernraum-panel .lr-learn-progress-ring::before { content: ''; position: absolute; inset: 4px; border-radius: inherit; background: var(--pm-bg); }
.lernraum-panel .lr-learn-progress-ring > span { position: relative; z-index: 1; }
.lernraum-panel .lr-learn-progress-ring--pulse { animation: lr-learn-progress-bounce .62s cubic-bezier(.34, 1.56, .64, 1) both; }
@keyframes lr-learn-progress-bounce {
  0% { transform: scale(1); filter: brightness(1); box-shadow: 0 0 0 0 color-mix(in oklab, var(--pm-accent) 52%, transparent); }
  32% { transform: scale(1.28); filter: brightness(1.32); box-shadow: 0 0 0 7px color-mix(in oklab, var(--pm-accent) 22%, transparent); }
  58% { transform: scale(.92); filter: brightness(1.08); box-shadow: 0 0 0 11px transparent; }
  78% { transform: scale(1.08); filter: brightness(1.12); }
  100% { transform: scale(1); filter: brightness(1); box-shadow: 0 0 0 0 transparent; }
}
.lernraum-panel .lr-nq-body { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(360px, 1fr); border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-nq-body--solo { grid-template-columns: minmax(360px, 760px); justify-content: center; }
.lernraum-panel .lr-nq-source { min-width: 0; min-height: 0; overflow: hidden; border-right: 1px solid var(--pm-border); background: var(--pm-surface-card); }
.lernraum-panel .lr-nq-work { min-width: 0; min-height: 0; overflow: auto; display: flex; flex-direction: column; gap: 14px; padding: 28px clamp(20px, 3vw, 40px) 32px; }
.lernraum-panel .lr-nq-body--solo .lr-nq-work { width: 100%; }
.lernraum-panel .lr-nq-field { display: flex; flex-direction: column; gap: 7px; }
.lernraum-panel .lr-nq-field--editor { min-height: 0; }
/* Beide Boxen umschließen ihren Inhalt (Auto-Grow) – plus etwas Luft. */
.lernraum-panel .lr-nq-field--question { flex: 0 0 auto; }
.lernraum-panel .lr-nq-field--answer { flex: 0 0 auto; }
.lernraum-panel .lr-nq-label-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.lernraum-panel .lr-nq-label { display: flex; align-items: center; gap: 8px; font: 650 13px/1.2 var(--pm-font-sans); color: var(--pm-text); }
.lernraum-panel .lr-nq-kind-ai-status { color: var(--nq-tint); font-size: 10.5px; font-weight: 560; }
.lernraum-panel .lr-nq-opt { color: var(--pm-text-muted); font-size: 11.5px; font-weight: 400; }
.lernraum-panel .lr-nq-ai { flex: none; display: inline-flex; align-items: center; gap: 5px; height: 25px; padding: 0 9px; border: 1px solid color-mix(in oklab, var(--nq-tint) 48%, var(--pm-border)); border-radius: 99px; background: color-mix(in oklab, var(--nq-tint) 10%, transparent); color: var(--nq-tint); font: 650 11px/1 var(--pm-font-sans); cursor: pointer; transition: background .15s, border-color .15s, opacity .15s; }
.lernraum-panel .lr-nq-ai:hover:not(:disabled) { border-color: var(--nq-tint); background: color-mix(in oklab, var(--nq-tint) 18%, transparent); }
.lernraum-panel .lr-nq-ai:focus-visible { outline: 2px solid var(--nq-tint); outline-offset: 2px; }
.lernraum-panel .lr-nq-ai:disabled { cursor: wait; opacity: .65; }
.lernraum-panel .lr-nq-area { flex: 1; min-height: 0; font-size: 15px; line-height: 1.55; }
/* Umschließt den Inhalt (field-sizing), mindestens 2 Zeilen, plus etwas Luft
   unten (padding-bottom) „für die Optik". */
.lernraum-panel .lr-nq-field--question .lr-nq-area,
.lernraum-panel .lr-nq-field--answer .lr-nq-area { flex: none; field-sizing: content; min-height: 64px; padding-bottom: 20px; overflow-y: hidden; resize: none; }
.lernraum-panel .lr-nq-swap { align-self: center; display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border: 1px solid var(--pm-border); border-radius: 99px; background: transparent; color: var(--pm-text-muted); font: 560 12px/1 var(--pm-font-sans); cursor: pointer; transition: color .15s, border-color .15s, background .15s; }
.lernraum-panel .lr-nq-swap:hover { border-color: var(--pm-accent); background: var(--pm-selected); color: var(--pm-accent-text); }
.lernraum-panel .lr-nq-meta { display: flex; flex-direction: column; gap: 20px; margin-bottom: 6px; }
.lernraum-panel .lr-nq-sub { display: inline-flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-nq-title .lr-nq-course { color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-nq-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: auto; padding-top: 18px; }
.lernraum-panel .lr-nq-error { margin-right: auto; color: var(--pm-danger); font-size: 12.5px; }
/* Lern- und Nachbereiten-Fokusmodus: gemeinsame „Nacht“-Palette, unabhängig vom App-Theme.
   Die Notiz liegt beim Nachbereiten als helles Blatt darauf; --nq-tint färbt dort Akzente nach Kartenart. */
:root:root .lernraum-panel.lernraum-panel--nq {
  --pm-bg: oklch(0.205 0.030 250);
  --pm-surface-card: oklch(0.245 0.032 250);
  --pm-surface-reader: oklch(0.165 0.028 252);
  --pm-border: oklch(0.335 0.034 250);
  --pm-text: oklch(0.955 0.008 235);
  --pm-text-muted: oklch(0.760 0.022 240);
  --pm-accent: oklch(0.80 0.10 200);
  --pm-accent-text: oklch(0.80 0.10 200);
  --pm-on-accent: oklch(0.180 0.035 250);
  --pm-selected: color-mix(in oklab, oklch(0.80 0.10 200) 20%, transparent);
  --pm-chip-bg: oklch(0.300 0.034 250);
  --pm-track: oklch(0.300 0.034 250);
  --pm-danger: oklch(0.740 0.140 27);
  background: radial-gradient(120% 90% at 20% 0%, oklch(0.215 0.045 255) 0%, oklch(0.165 0.028 252) 60%);
}
.lernraum-panel .lr-nq { --nq-tint: oklch(0.80 0.10 200); --pm-accent: var(--nq-tint); --pm-accent-text: var(--nq-tint); --pm-selected: color-mix(in oklab, var(--nq-tint) 20%, transparent); }
:root[data-theme="dark"] .lernraum-panel.lernraum-panel--nq {
  --pm-bg: oklch(0.275 0.014 222);
  --pm-surface-card: oklch(0.345 0.012 222);
  --pm-surface-reader: oklch(0.250 0.014 222);
  --pm-border: oklch(0.395 0.014 222);
  --pm-text: oklch(0.965 0.005 220);
  --pm-text-muted: oklch(0.760 0.014 220);
  --pm-accent: oklch(0.760 0.105 200);
  --pm-accent-text: oklch(0.845 0.090 200);
  --pm-on-accent: oklch(0.200 0.030 200);
  --pm-selected: oklch(0.375 0.050 205);
  --pm-chip-bg: oklch(0.395 0.014 222);
  --pm-track: oklch(0.375 0.014 222);
  --pm-danger: oklch(0.720 0.140 27);
  background: var(--pm-surface-reader);
}
:root[data-theme="dark"] .lernraum-panel .lr-nq {
  --nq-tint: oklch(0.760 0.105 200) !important;
  --pm-accent: oklch(0.760 0.105 200);
  --pm-accent-text: oklch(0.845 0.090 200);
  --pm-selected: oklch(0.375 0.050 205);
}
.lernraum-panel .lr-nq-body { border-top-color: var(--pm-border); }
.lernraum-panel .lr-nq-source { position: relative; display: flex; padding: 22px clamp(16px, 2.5vw, 32px); border-right-color: var(--pm-border); background: transparent; }
.lernraum-panel .lr-nq-paper {
  flex: 1; min-width: 0; min-height: 0; overflow: hidden; border-radius: 16px; color: var(--pm-text);
  box-shadow: 0 24px 60px rgba(0, 0, 0, .35), 0 0 0 1px rgba(255, 255, 255, .05);
  transition: background .2s, color .2s;
}
.lernraum-panel .lr-nq-paper--light { --pm-text: oklch(0.205 0.018 235); --pm-muted: oklch(0.470 0.018 235); --pm-text-muted: oklch(0.470 0.018 235); --pm-accent: color-mix(in oklab, var(--nq-tint) 52%, black); --pm-accent-strong: var(--pm-accent); background: oklch(0.985 0.004 95); }
.lernraum-panel .lr-nq-paper--dark { --pm-text: oklch(0.94 0.008 235); --pm-muted: oklch(0.76 0.020 240); --pm-text-muted: oklch(0.76 0.020 240); --pm-divider: oklch(0.42 0.030 250); --pm-content-surface: oklch(0.225 0.028 252); --pm-app-surface: oklch(0.205 0.026 252); --pm-surface-soft: oklch(0.30 0.028 250); --pm-viewer-surface: oklch(0.215 0.028 252); --pm-accent: var(--nq-tint); --pm-accent-strong: var(--nq-tint); background: oklch(0.265 0.030 250); box-shadow: 0 24px 60px rgba(0, 0, 0, .42), 0 0 0 1px oklch(0.43 0.032 250); }
:root[data-theme="dark"] .lernraum-panel .lr-nq-paper--dark {
  --pm-text: #f0f4f6;
  --pm-muted: #a5b2b7;
  --pm-text-muted: #a5b2b7;
  --pm-divider: #3d484d;
  --pm-content-surface: #283134;
  --pm-app-surface: #20292d;
  --pm-surface-soft: #333b3e;
  --pm-viewer-surface: #20292d;
  --pm-accent: oklch(0.760 0.105 200);
  --pm-accent-strong: oklch(0.845 0.090 200);
  background: #283134;
  box-shadow: 0 12px 30px rgba(0, 0, 0, .24), 0 0 0 1px #3d484d;
}
:root[data-theme="dark"] .lernraum-panel .lr-nq-paper--dark .note-preview--dark {
  --pm-text: #f0f4f6;
  --pm-muted: #a5b2b7;
  --pm-text-muted: #a5b2b7;
  --pm-divider: #3d484d;
  --pm-content-surface: #283134;
  --pm-app-surface: #20292d;
  --pm-surface-soft: #333b3e;
  --pm-viewer-surface: #20292d;
  --pm-accent-strong: #80dee3;
  background: #283134;
  color: #f0f4f6;
}
.lernraum-panel .lr-nq-paper .note-preview--compact .note-preview__sheet { padding-top: 32px; }
.lernraum-panel .lr-nq-note-theme-toggle { position: absolute; top: 34px; right: clamp(28px, 4vw, 48px); z-index: 2; display: grid; place-items: center; width: 34px; height: 34px; padding: 0; border: 1px solid var(--pm-border); border-radius: 10px; background: color-mix(in oklab, var(--pm-surface-card) 88%, transparent); color: var(--pm-text-muted); cursor: pointer; backdrop-filter: blur(8px); transition: border-color .15s, background .15s, color .15s; }
.lernraum-panel .lr-nq-note-theme-toggle:hover { border-color: var(--nq-tint); background: var(--pm-selected); color: var(--nq-tint); }
.lernraum-panel .lr-nq-note-theme-toggle:focus-visible { outline: 2px solid var(--nq-tint); outline-offset: 2px; }
.lernraum-panel .lr-nq-work { background: transparent; }
.lernraum-panel .lr-nq .lr-btn--primary { box-shadow: 0 0 22px color-mix(in oklab, var(--nq-tint) 35%, transparent); transition: background .3s, box-shadow .3s; }
.lernraum-panel .lr-action-button.v-btn {
  height: 38px;
  min-width: 0;
  padding-inline: 17px;
  border-radius: 10px;
  font: 620 13.5px/1 var(--pm-font-sans);
  letter-spacing: 0;
  text-transform: none;
}
.lernraum-panel .lr-nq-submit.v-btn {
  background: var(--nq-tint);
  color: var(--pm-on-accent);
  box-shadow: 0 0 22px color-mix(in oklab, var(--nq-tint) 35%, transparent);
  transition: background-color .18s, box-shadow .18s;
}
.lernraum-panel .lr-nq-submit.v-btn:hover:not(.v-btn--disabled) {
  background: color-mix(in oklab, var(--nq-tint) 88%, white) !important;
  box-shadow: 0 0 28px color-mix(in oklab, var(--nq-tint) 45%, transparent);
}
.lernraum-panel .lr-nq .lr-kind-opt--on { background: color-mix(in oklab, var(--nq-tint) 22%, transparent); color: var(--nq-tint); }
.lernraum-panel .lr-nq .lr-kind-opt--on:hover { border-color: transparent; background: color-mix(in oklab, var(--nq-tint) 30%, transparent); color: var(--nq-tint); }
.lernraum-panel .lr-nq .lr-field:focus { border-color: var(--nq-tint); box-shadow: 0 0 0 3px color-mix(in oklab, var(--nq-tint) 24%, transparent); }
.lernraum-panel .lr-nq .lr-btn--ghost:hover { background: var(--pm-chip-bg); }
:root[data-theme="dark"] .lernraum-panel .lr-nq .lr-btn--primary,
:root[data-theme="dark"] .lernraum-panel .lr-nq-submit.v-btn,
:root[data-theme="dark"] .lernraum-panel .lr-nq-submit.v-btn:hover:not(.v-btn--disabled) {
  box-shadow: none;
}
@media (prefers-reduced-motion: reduce) { .lernraum-panel .lr-nq * { transition: none !important; } }
@media (max-width: 900px) {
  .lernraum-panel .lr-nq-body { grid-template-columns: 1fr; grid-template-rows: minmax(120px, 34%) minmax(0, 1fr); }
  .lernraum-panel .lr-nq-body--solo { grid-template-rows: minmax(0, 1fr); }
  .lernraum-panel .lr-nq-source { border-right: 0; border-bottom: 1px solid var(--pm-border); }
}

.lernraum-panel .lr-course-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.lernraum-panel .lr-course-chip { height: 34px; display: inline-flex; align-items: center; gap: 8px; padding: 0 15px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-surface-card); color: var(--pm-text); font: 520 13.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-course-chip:hover { border-color: var(--pm-accent); }
.lernraum-panel .lr-course-chip-count { font-size: 12px; color: var(--pm-chip-count); }
.lernraum-panel .lr-course-chip--add { color: var(--pm-text-muted); border-style: dashed; }

/* Kopfzeile der Kursansicht */
.lernraum-panel .lr-chead { flex: none; padding: 18px 28px 14px; background: var(--pm-bg); border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-chead-back { background: 0; border: 0; padding: 0; margin-bottom: 10px; color: var(--pm-text-muted); font: 520 13px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-chead-back:hover { color: var(--pm-text); }
.lernraum-panel .lr-chead-main { display: flex; align-items: flex-end; gap: 16px; }
.lernraum-panel .lr-chead-titlewrap { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.lernraum-panel .lr-chead-switch { position: relative; }
.lernraum-panel .lr-chead-title { display: inline-flex; align-items: center; gap: 8px; background: 0; border: 0; padding: 0; color: var(--pm-text); font: 660 24px/1.2 var(--pm-font-sans); letter-spacing: -.02em; cursor: pointer; }
.lernraum-panel .lr-chead-chevron { font-size: 15px; color: var(--pm-text-muted); transition: transform .15s; }
.lernraum-panel .lr-chead-chevron--open { transform: rotate(180deg); }
.lernraum-panel .lr-chead-sub { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-cswitch-backdrop { position: fixed; inset: 0; z-index: 18; }
.lernraum-panel .lr-cswitch { position: absolute; top: calc(100% + 6px); left: 0; z-index: 19; min-width: 220px; padding: 6px; border: 1px solid var(--pm-border); border-radius: 12px; background: var(--pm-surface-card); box-shadow: 0 12px 32px rgba(0,0,0,.18); display: flex; flex-direction: column; gap: 2px; }
.lernraum-panel .lr-cswitch-item { text-align: left; height: 34px; padding: 0 12px; border: 0; border-radius: 8px; background: transparent; color: var(--pm-text); font: 520 13.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-cswitch-item:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-cswitch-item--on { background: var(--pm-selected); color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-cswitch-item--add { color: var(--pm-text-muted); border-top: 1px solid var(--pm-border); border-radius: 0; margin-top: 4px; padding-top: 10px; height: auto; padding-bottom: 6px; }
.lernraum-panel .lr-chead .lr-modetabs { margin-left: auto; }

/* Kurs-Kopf + Board */
.lernraum-panel .lr-header { flex: none; display: flex; align-items: center; gap: 16px; padding: 20px 28px 16px; }
.lernraum-panel .lr-header .lr-btn--primary { margin-left: auto; }
.lernraum-panel .lr-board { flex: 1; min-height: 0; overflow: auto; padding: 4px 28px 28px; }
.lernraum-panel .lr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 16px; }
.lernraum-panel .lr-card { display: flex; flex-direction: column; gap: 12px; padding: 16px; min-height: 132px; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); text-align: left; color: var(--pm-text); font-family: var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-card:hover { border-color: var(--pm-accent); box-shadow: 0 2px 10px rgba(0,0,0,.05); }
.lernraum-panel .lr-card--faded { opacity: .55; }
.lernraum-panel .lr-card--add { align-items: center; justify-content: center; gap: 6px; border-style: dashed; color: var(--pm-text-muted); font-size: 13px; text-align: center; }
.lernraum-panel .lr-card--add:hover { background: var(--pm-bg); color: var(--pm-accent-text); border-color: var(--pm-accent); box-shadow: none; }
.lernraum-panel .lr-add-plus { font-size: 22px; line-height: 1; }
.lernraum-panel .lr-card-status { display: flex; align-items: center; gap: 6px; }
.lernraum-panel .lr-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.lernraum-panel .lr-status-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .07em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-card-title { font: 620 16px/1.3 var(--pm-font-sans); letter-spacing: -.01em; text-wrap: pretty; flex: 1; }
.lernraum-panel .lr-card-foot { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.lernraum-panel .lr-card-count { font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-card-session { font-size: 11.5px; color: var(--pm-chip-text); background: var(--pm-chip-bg); padding: 2px 8px; border-radius: 20px; }

/* Lernblatt-Seite */
.lernraum-panel .lr-sheet-view { flex: 1; min-height: 0; overflow: auto; padding: 18px 28px 32px; }
.lernraum-panel .lr-back { background: 0; border: 0; padding: 6px 0; color: var(--pm-text-muted); font: 520 13px/1 var(--pm-font-sans); cursor: pointer; margin-bottom: 12px; }
.lernraum-panel .lr-back:hover { color: var(--pm-text); }
.lernraum-panel .lr-sheet-card { max-width: 760px; display: flex; flex-direction: column; gap: 22px; }
.lernraum-panel .lr-sheet-head { display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-sheet-title { margin: 0; font: 660 26px/1.2 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-sheet-meta { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-cards-panel { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); overflow: hidden; }
.lernraum-panel .lr-cards-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--pm-border); }
.lernraum-panel .lr-cards-title { font: 620 14px/1.3 var(--pm-font-sans); }
.lernraum-panel .lr-cards-empty { padding: 28px 18px; text-align: center; }
.lernraum-panel .lr-cards-empty p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-cards-empty .lr-cards-hint { margin-top: 6px; margin-bottom: 14px; font-size: 12.5px; color: var(--pm-text-muted); }
.lernraum-panel .lr-cards-num { color: var(--pm-text-muted); font-weight: 520; }
.lernraum-panel .lr-cards-head-actions { display: flex; gap: 8px; }

/* Karten-Liste */
.lernraum-panel .lr-card-list { display: flex; flex-direction: column; }
.lernraum-panel .lr-card-row { display: flex; gap: 12px; padding: 14px 18px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-card-row:first-child { border-top: 0; }
.lernraum-panel .lr-card-row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.lernraum-panel .lr-card-row-top { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-card-row-idx { font-size: 11.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-kind-chip { display: inline-flex; align-items: center; height: 19px; padding: 0 8px; border-radius: 20px; font: 620 10.5px/1 var(--pm-font-sans); letter-spacing: .05em; text-transform: uppercase; }
.lernraum-panel .lr-kind-chip--lg { height: 24px; padding: 0 11px; font-size: 12px; }
.lernraum-panel .lr-card-front { font: 520 14px/1.5 var(--pm-font-sans); color: var(--pm-text); }
.lernraum-panel .lr-card-back { font-size: 13px; line-height: 1.5; color: var(--pm-text-muted); }
.lernraum-panel .lr-card-side--empty { font-style: italic; opacity: .7; }
.lernraum-panel .lr-card-row-actions { display: flex; gap: 4px; align-items: flex-start; }
.lernraum-panel .lr-icon-btn { width: 26px; height: 26px; border: 0; border-radius: 6px; background: transparent; color: var(--pm-text-muted); cursor: pointer; font-size: 13px; line-height: 1; }
.lernraum-panel .lr-icon-btn:hover { background: var(--pm-surface-reader); color: var(--pm-text); }
.lernraum-panel .lr-icon-btn--danger:hover { color: var(--pm-danger); }
.lernraum-panel .lr-icon-btn:disabled { cursor: wait; opacity: .45; }

/* Lernmodus-Overlay */
.lernraum-panel .lr-learn-overlay { position: absolute; inset: 0; z-index: 15; background: var(--pm-surface-reader); overflow: auto; padding: 22px 28px 32px; display: flex; flex-direction: column; }
.lernraum-panel .lr-learn-top { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.lernraum-panel .lr-learn-progress { font-size: 12.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-learn-card { max-width: 640px; width: 100%; margin: 8px auto 0; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); padding: 28px 30px; display: flex; flex-direction: column; gap: 18px; }
.lernraum-panel .lr-learn-card .lr-kind-chip { align-self: flex-start; }
.lernraum-panel .lr-learn-front { font: 620 20px/1.4 var(--pm-font-sans); letter-spacing: -.01em; color: var(--pm-text); text-wrap: pretty; }
.lernraum-panel .lr-learn-back { border-top: 1px solid var(--pm-border); padding-top: 16px; display: flex; flex-direction: column; gap: 6px; }
.lernraum-panel .lr-learn-question-label,
.lernraum-panel .lr-learn-back-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .08em; text-transform: uppercase; color: var(--pm-accent-text); }
.lernraum-panel .lr-learn-question-label { margin-bottom: 6px; }
.lernraum-panel .lr-learn-back-text { font: 400 16px/1.6 var(--pm-font-sans); color: var(--pm-text); text-wrap: pretty; }
.lernraum-panel .lr-learn-actions { display: flex; gap: 10px; margin-top: 4px; }
.lernraum-panel .lr-assess { flex: 1; height: 42px; border-radius: 10px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text); font: 620 13.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-assess--weak:hover { border-color: var(--pm-danger); color: var(--pm-danger); background: color-mix(in oklab, var(--pm-danger) 8%, transparent); }
.lernraum-panel .lr-assess--medium:hover { border-color: var(--pm-star); color: var(--pm-star); background: color-mix(in oklab, var(--pm-star) 10%, transparent); }
.lernraum-panel .lr-assess--strong:hover { border-color: var(--pm-success); color: var(--pm-success); background: color-mix(in oklab, var(--pm-success) 10%, transparent); }
.lernraum-panel .lr-assess--weak.lr-assess--selected { border-color: var(--pm-danger); background: color-mix(in oklab, var(--pm-danger) 16%, transparent); color: var(--pm-danger); }
.lernraum-panel .lr-assess--medium.lr-assess--selected { border-color: var(--pm-star); background: color-mix(in oklab, var(--pm-star) 18%, transparent); color: var(--pm-star); }
.lernraum-panel .lr-assess--strong.lr-assess--selected { border-color: var(--pm-success); background: color-mix(in oklab, var(--pm-success) 18%, transparent); color: var(--pm-success); }
.lernraum-panel .lr-learn-selfhint { font-size: 12px; color: var(--pm-text-muted); text-align: center; }
.lernraum-panel .lr-learn-done { max-width: 640px; width: 100%; margin: 40px auto 0; text-align: center; display: flex; flex-direction: column; gap: 16px; align-items: center; }
.lernraum-panel .lr-learn-done-title { font: 660 20px/1.25 var(--pm-font-sans); }

/* Startseite: Nachbereitungs-Karten */
.lernraum-panel .lr-nb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.lernraum-panel .lr-nb-card { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); padding: 16px 18px; display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-nb-card-top { display: flex; align-items: baseline; gap: 8px; }
.lernraum-panel .lr-nb-card-course { font-size: 12.5px; color: var(--pm-text-muted); }
.lernraum-panel .lr-nb-card-count { margin-left: auto; font-size: 11.5px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); }
.lernraum-panel .lr-nb-card-title { font: 620 16px/1.3 var(--pm-font-sans); letter-spacing: -.015em; text-wrap: pretty; }
.lernraum-panel .lr-nb-card-meta { font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-nb-actions { display: flex; align-items: center; gap: 12px; margin-top: 4px; }
.lernraum-panel .lr-nb-later { font-size: 12.5px; color: var(--pm-text-muted); cursor: pointer; }
.lernraum-panel .lr-nb-later:hover { color: var(--pm-text); }

/* Startseite: Lernstand pro Kurs */
.lernraum-panel .lr-course-board { border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); overflow: hidden; }
.lernraum-panel .lr-crow { border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-crow:first-child { border-top: 0; }
.lernraum-panel .lr-crow--open { background: color-mix(in oklab, var(--pm-accent) 5%, var(--pm-surface-card)); }
.lernraum-panel .lr-crow-head { display: flex; align-items: center; gap: 16px; padding: 16px 18px; cursor: pointer; }
.lernraum-panel .lr-crow-head:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-crow--open .lr-crow-head:hover { background: transparent; }
.lernraum-panel .lr-crow-caret { flex: none; color: var(--pm-text-muted); font-size: 11px; transition: transform .15s; }
.lernraum-panel .lr-crow-caret--open { transform: rotate(90deg); }
.lernraum-panel .lr-crow-titleblock { flex: 0 0 200px; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.lernraum-panel .lr-crow-title { font: 620 16px/1.25 var(--pm-font-sans); letter-spacing: -.01em; }
.lernraum-panel .lr-crow-sub { font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-crow-barwrap { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.lernraum-panel .lr-bar { position: relative; display: flex; flex-direction: row; justify-content: flex-start; direction: ltr; height: 8px; border-radius: 5px; overflow: hidden; background: var(--pm-track); }
.lernraum-panel .lr-bar--empty { opacity: .6; }
.lernraum-panel .lr-bar-seg { flex: none; height: 100%; }
.lernraum-panel .lr-bar--updated,
.lernraum-panel .lr-progress-band--updated { animation: lr-progress-settle .46s cubic-bezier(.22, 1, .36, 1); }
.lernraum-panel .lr-bar--updated .lr-bar-seg,
.lernraum-panel .lr-progress-band--updated .lr-progress-band-segment { transition: width .42s cubic-bezier(.22, 1, .36, 1); }
@keyframes lr-progress-settle { 0% { transform: scaleY(.84); opacity: .58; } 68% { transform: scaleY(1.08); opacity: 1; } 100% { transform: scaleY(1); } }
.lernraum-panel .lr-bar-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11.5px; color: var(--pm-text-muted); }
.lernraum-panel .lr-crow-right { flex: 0 0 92px; display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.lernraum-panel .lr-crow-pct { font: 660 18px/1 var(--pm-font-sans); }
.lernraum-panel .lr-crow-dash { color: var(--pm-text-muted); }
.lernraum-panel .lr-crow-links { display: flex; gap: 10px; }
.lernraum-panel .lr-link { background: 0; border: 0; padding: 0; color: var(--pm-accent-text); font: 520 13px/1.3 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-link:hover { text-decoration: underline; }

/* Startseite: aufgeklappter Kurs */
.lernraum-panel .lr-crow-body { padding: 4px 18px 20px 45px; }
.lernraum-panel .lr-crow-explain { max-width: 560px; }
.lernraum-panel .lr-crow-explain p { margin: 0 0 12px; font-size: 13.5px; line-height: 1.55; color: var(--pm-text-muted); }
.lernraum-panel .lr-crow-explain-actions { display: flex; align-items: center; gap: 14px; }
.lernraum-panel .lr-crow-tabs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.lernraum-panel .lr-crow-tabs-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .07em; text-transform: uppercase; color: var(--pm-text-muted); margin-right: 2px; }
.lernraum-panel .lr-crow-tab { height: 28px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-crow-tab--on { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-crow-tabs-meta { margin-left: auto; font-size: 12px; color: var(--pm-text-muted); }
.lernraum-panel .lr-clist { display: flex; flex-direction: column; }
.lernraum-panel .lr-crow-card { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-crow-card:first-child { border-top: 0; }
.lernraum-panel .lr-cstatus-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.lernraum-panel .lr-ckind { flex: 0 0 86px; font: 620 10.5px/1.4 var(--pm-font-sans); letter-spacing: .06em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-cfront { flex: 1; min-width: 0; font-size: 14px; color: var(--pm-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-cstatus { flex: 0 0 auto; font-size: 12.5px; }
.lernraum-panel .lr-cuben { flex: 0 0 auto; }
.lernraum-panel .lr-crow-loading { font-size: 13px; color: var(--pm-text-muted); padding: 10px 0; }
.lernraum-panel .lr-clist-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; }

/* Startseite: großer Leerzustand (2b) */
.lernraum-panel .lr-empty-hero { max-width: 500px; text-align: center; display: flex; flex-direction: column; gap: 14px; align-items: center; }
.lernraum-panel .lr-empty-eyebrow { font: 620 11.5px/1.4 var(--pm-font-sans); letter-spacing: .09em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-empty-inline-cta { margin-top: 12px; align-self: flex-start; }

/* Kursübersicht */
.lernraum-panel .lr-header--course { padding-bottom: 8px; }
.lernraum-panel .lr-modetabs { margin-left: auto; display: inline-flex; gap: 2px; padding: 3px; border-radius: 10px; background: var(--pm-chip-bg); }
.lernraum-panel .lr-modetab { height: 30px; padding: 0 14px; border: 0; border-radius: 8px; background: transparent; color: var(--pm-text-muted); font: 560 13px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-modetab:hover:not([disabled]) { color: var(--pm-text); }
.lernraum-panel .lr-modetab--on { background: var(--pm-bg); color: var(--pm-text); font-weight: 620; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.lernraum-panel .lr-modetab[disabled] { opacity: .4; cursor: default; }
/* Leuchttisch-Karten */
.lernraum-panel .lr-lt-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.lernraum-panel .lr-lt-card { display: flex; flex-direction: column; gap: 10px; padding: 16px 18px; min-height: 150px; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); text-align: left; color: var(--pm-text); font-family: var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-lt-card:hover { border-color: var(--pm-accent); box-shadow: 0 2px 10px rgba(0,0,0,.05); }
.lernraum-panel .lr-lt-card--faded { opacity: .55; }
.lernraum-panel .lr-lt-status { display: flex; align-items: center; gap: 6px; }
.lernraum-panel .lr-lt-title { font: 620 16px/1.3 var(--pm-font-sans); letter-spacing: -.01em; text-wrap: pretty; flex: 1; }
.lernraum-panel .lr-lt-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-lt-chip { font: 520 11.5px/1 var(--pm-font-sans); color: var(--pm-chip-text); background: var(--pm-chip-bg); padding: 5px 9px; border-radius: 7px; }
.lernraum-panel .lr-lt-source { font: 400 11.5px/1.4 var(--pm-font-mono); color: var(--pm-text-muted); text-wrap: pretty; }
.lernraum-panel .lr-lt-card--add { align-items: center; justify-content: center; text-align: center; border-style: dashed; color: var(--pm-text-muted); font-size: 12.5px; min-height: 150px; }
.lernraum-panel .lr-lt-card--add:hover { background: var(--pm-bg); color: var(--pm-accent-text); border-color: var(--pm-accent); box-shadow: none; }

.lernraum-panel .lr-sheet-foot { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; flex-wrap: wrap; padding-top: 16px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-foot-status { display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-foot-label { font: 620 11px/1.4 var(--pm-font-sans); letter-spacing: .07em; text-transform: uppercase; color: var(--pm-text-muted); }
.lernraum-panel .lr-status-picker { display: flex; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-status-chip { height: 30px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-bg); color: var(--pm-text-muted); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-status-chip:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-status-chip--active { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-foot-actions { display: flex; gap: 8px; }

/* Leerzustände */
.lernraum-panel .lr-empty { flex: 1; min-height: 60vh; display: flex; align-items: center; justify-content: center; padding: 40px; }
.lernraum-panel .lr-empty-visual { position: relative; width: 250px; height: 154px; margin-bottom: 10px; }
.lernraum-panel .lr-empty-visual::before { content: ''; position: absolute; inset: -38px -62px -30px; border-radius: 50%; background: radial-gradient(ellipse at center, color-mix(in oklab, var(--pm-surface-card) 82%, transparent) 0%, color-mix(in oklab, var(--pm-surface-card) 42%, transparent) 52%, transparent 76%); pointer-events: none; }
.lernraum-panel .lr-empty-card { --lr-empty-transform: translate3d(0, 0, 0); position: absolute; bottom: 8px; z-index: 1; box-sizing: border-box; width: 88px; height: 112px; display: flex; flex-direction: column; align-items: stretch; gap: 8px; padding: 13px 12px; border: 1px solid color-mix(in oklab, var(--pm-text) 20%, var(--pm-border)); border-radius: 10px; background: color-mix(in oklab, var(--pm-surface-card) 92%, var(--pm-accent) 8%); color: var(--pm-accent-text); box-shadow: 0 14px 30px color-mix(in oklab, #000 18%, transparent); transform: var(--lr-empty-transform); transform-origin: bottom center; animation: lr-empty-card-in .48s cubic-bezier(.2,.82,.24,1) both; }
.lernraum-panel .lr-empty-card i { display: grid; place-items: center; width: 27px; height: 27px; border-radius: 50%; background: color-mix(in oklab, var(--pm-accent) 18%, transparent); font: 700 15px/1 var(--pm-font-sans); font-style: normal; }
.lernraum-panel .lr-empty-card b { display: block; width: 100%; height: 5px; border-radius: 99px; background: color-mix(in oklab, var(--pm-text) 22%, var(--pm-border)); }
.lernraum-panel .lr-empty-card b:nth-of-type(2) { width: 76%; }
.lernraum-panel .lr-empty-card b:nth-of-type(3) { width: 90%; }
.lernraum-panel .lr-empty-card--left { --lr-empty-transform: translate3d(22px, 7px, 0) rotate(-9deg); left: 4px; height: 96px; opacity: .82; animation-delay: 45ms; }
.lernraum-panel .lr-empty-card--right { --lr-empty-transform: translate3d(-22px, 8px, 0) rotate(9deg); right: 3px; height: 94px; opacity: .82; animation-delay: 90ms; }
.lernraum-panel .lr-empty-card--front { --lr-empty-transform: translate3d(0, -10px, 0); left: 81px; z-index: 2; width: 92px; height: 126px; animation-delay: 135ms; }
.lernraum-panel .lr-empty-plus { position: absolute; right: 15px; bottom: 0; z-index: 4; display: grid; place-items: center; width: 42px; height: 42px; border: 4px solid var(--pm-bg); border-radius: 50%; background: var(--pm-accent); color: var(--pm-on-accent); box-shadow: 0 7px 18px color-mix(in oklab, var(--pm-accent) 30%, transparent); animation: lr-empty-plus-in .42s .2s cubic-bezier(.2,.82,.24,1) both; }
.lernraum-panel .lr-empty-title { margin: 0; font: 680 21px/1.25 var(--pm-font-sans); letter-spacing: -.018em; }
.lernraum-panel .lr-empty-body { max-width: 440px; font-size: 14px; line-height: 1.65; color: color-mix(in oklab, var(--pm-text) 68%, var(--pm-text-muted)); }
.lernraum-panel .lr-empty-action { display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 42px; margin-top: 8px; padding: 0 20px; border: 1px solid color-mix(in oklab, var(--pm-accent) 62%, var(--pm-border)); border-radius: 10px; background: color-mix(in oklab, var(--pm-accent) 10%, transparent); color: var(--pm-accent-text); font: 650 14px/1 var(--pm-font-sans); cursor: pointer; transition: border-color .16s, background .16s, transform .16s; }
.lernraum-panel .lr-empty-action:hover { border-color: var(--pm-accent); background: color-mix(in oklab, var(--pm-accent) 17%, transparent); transform: translateY(-1px); }
.lernraum-panel .lr-empty-action:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }
@keyframes lr-empty-card-in { from { opacity: 0; transform: translate3d(0, 14px, 0) scale(.92); } to { transform: var(--lr-empty-transform); } }
@keyframes lr-empty-plus-in { from { opacity: 0; transform: scale(.55) rotate(-18deg); } to { opacity: 1; transform: scale(1) rotate(0); } }
.lernraum-panel .lr-empty-inline { padding: 24px 0; }
.lernraum-panel .lr-empty-inline p { margin: 0; font-size: 14px; color: var(--pm-text); }
.lernraum-panel .lr-empty-inline .lr-empty-inline-hint { margin-top: 5px; font-size: 12.5px; color: var(--pm-text-muted); }

/* Dialog */
.lernraum-panel .lr-modal-scrim { position: absolute; inset: 0; z-index: 20; background: color-mix(in oklab, #000 42%, transparent); display: flex; align-items: center; justify-content: center; padding: 24px; }
.lernraum-panel .lr-modal { width: 100%; max-width: 480px; max-height: 100%; overflow: auto; background: var(--pm-bg); border: 1px solid var(--pm-border); border-radius: 16px; box-shadow: 0 16px 48px rgba(0,0,0,.28); padding: 22px 24px 20px; display: flex; flex-direction: column; gap: 12px; }
.lernraum-panel .lr-modal-title { font: 660 18px/1.25 var(--pm-font-sans); letter-spacing: -.015em; margin-bottom: 2px; }
.lernraum-panel .lr-field-label { font: 620 11.5px/1.4 var(--pm-font-sans); letter-spacing: .06em; text-transform: uppercase; color: var(--pm-text-muted); margin-top: 4px; }
.lernraum-panel .lr-field-opt { text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--pm-text-muted); opacity: .85; }
.lernraum-panel .lr-field { width: 100%; border: 1px solid var(--pm-border); border-radius: 9px; background: var(--pm-surface-card); color: var(--pm-text); font: 400 14px/1.5 var(--pm-font-sans); padding: 9px 11px; outline: none; }
.lernraum-panel .lr-field:focus { border-color: var(--pm-accent); box-shadow: 0 0 0 3px var(--pm-selected); }
.lernraum-panel .lr-field--area { resize: vertical; min-height: 60px; }
.lernraum-panel .lr-kind-picker { display: flex; flex-wrap: wrap; gap: 6px; }
.lernraum-panel .lr-kind-opt { height: 30px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--pm-border); background: var(--pm-surface-card); color: var(--pm-text-muted); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-kind-opt:hover { background: var(--pm-surface-reader); }
.lernraum-panel .lr-kind-opt--on { background: var(--pm-selected); border-color: transparent; color: var(--pm-accent-text); font-weight: 620; }
.lernraum-panel .lr-field-error { font-size: 12.5px; color: var(--pm-danger); }
.lernraum-panel .lr-modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }

/* Kursansicht: ruhiger – je Abschnitt eine Überschrift, Trennlinien statt Kicker. */

.lernraum-panel .lr-head { --lr-prog-w: 220px; position: relative; flex: none; }
.lernraum-panel .lr-crumbs { flex: none; display: flex; align-items: flex-start; gap: 2px; height: 42px; padding: 16px calc(clamp(24px, 4vw, 52px) + var(--lr-prog-w) + 24px) 0 clamp(24px, 4vw, 52px); background: var(--pm-surface-card); font-size: 12.5px; white-space: nowrap; overflow: hidden; }
.lernraum-panel .lr-crumb { min-width: 0; max-width: 260px; overflow: hidden; padding: 4px 8px; border: 0; border-radius: 7px; background: transparent; color: var(--pm-text-muted); font: 520 12.5px/1.2 var(--pm-font-sans); text-overflow: ellipsis; cursor: pointer; transition: background .15s, color .15s; }
.lernraum-panel .lr-crumbs > :first-child { margin-left: -8px; }
.lernraum-panel .lr-crumb:hover { background: var(--pm-selected); color: var(--pm-accent-text); }
.lernraum-panel .lr-crumb:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.lernraum-panel .lr-crumb--current { color: var(--pm-text); font-weight: 640; cursor: default; }
.lernraum-panel .lr-crumb--current:hover { background: transparent; color: var(--pm-text); }
.lernraum-panel .lr-crumb-sep { flex: none; display: grid; place-items: center; width: 14px; height: 23px; color: var(--pm-text-muted); opacity: .6; }
.lernraum-panel .lr-crumb-sep svg { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.lernraum-panel .lr-scroll { flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column; }
.lernraum-panel .lr-pagehead { position: relative; z-index: 1; flex: none; display: flex; flex-direction: column; gap: 14px; padding: 0 calc(clamp(24px, 4vw, 52px) + var(--lr-prog-w) + 24px) 20px clamp(24px, 4vw, 52px); border-bottom: 1px solid var(--pm-border); background: var(--pm-surface-card); }
.v-theme--dark .lernraum-panel .lr-crumbs,
.v-theme--dark .lernraum-panel .lr-pagehead {
  background: var(--pm-bg);
}
.lernraum-panel .lr-pagehead-main { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.lernraum-panel .lr-title-block { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-title { max-width: 100%; margin: 0; overflow: hidden; font-size: clamp(24px, 2.6vw, 30px); line-height: 1.15; font-weight: 690; letter-spacing: -.03em; text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-title-edit { display: block; max-width: 100%; overflow: hidden; border: 0; padding: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; text-align: left; text-overflow: ellipsis; white-space: nowrap; cursor: text; }
.lernraum-panel .lr-title-edit > span { display: none; }
.lernraum-panel .lr-title-edit:hover { color: var(--pm-accent-text); }
.lernraum-panel .lr-title-input { width: 100%; max-width: 100%; border: 0; padding: 0; outline: 0; background: transparent; color: inherit; font: inherit; letter-spacing: inherit; }
.lernraum-panel .lr-title-input:disabled { opacity: .65; }
.lernraum-panel .lr-title-error { color: var(--pm-danger); font-size: 11.5px; }
.lernraum-panel .lr-subtitle { margin: 0; overflow: hidden; max-width: 100%; font-size: 12px; line-height: 1.3; text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-btn--md { min-height: 38px; padding-inline: 17px; }
.lernraum-panel .lr-btn--primary { box-shadow: 0 1px 2px color-mix(in oklab, var(--pm-accent) 30%, transparent); }

.lernraum-panel .lr-header-progress { position: absolute; z-index: 2; top: 50%; right: clamp(24px, 4vw, 52px); display: flex; flex-direction: column; gap: 9px; width: var(--lr-prog-w); transform: translateY(-50%); }
.lernraum-panel .lr-head-actions { position: absolute; z-index: 2; top: 50%; right: clamp(24px, 4vw, 52px); display: flex; align-items: center; gap: 10px; transform: translateY(-50%); }
.lernraum-panel .lr-head-action.v-btn { position: static; transform: none; background: var(--pm-accent); color: var(--pm-on-accent); box-shadow: 0 1px 2px color-mix(in oklab, var(--pm-accent) 30%, transparent); transition: filter .18s, box-shadow .18s; }
.lernraum-panel .lr-head-action.v-btn:hover:not(.v-btn--disabled) { filter: brightness(1.06); box-shadow: 0 3px 8px color-mix(in oklab, var(--pm-accent) 26%, transparent); }
.lernraum-panel .lr-head-action.v-btn.v-btn--disabled { background: color-mix(in oklab, var(--pm-text-muted) 18%, var(--pm-surface-card)); color: var(--pm-text-muted); box-shadow: none; opacity: .62; filter: saturate(.25); }
.lernraum-panel .lr-header-progress-label { flex: none; text-align: right; color: var(--pm-text-muted); font-size: 12px; line-height: 1; white-space: nowrap; }
.lernraum-panel .lr-header-progress-label strong { color: var(--pm-text); font-size: 14px; font-weight: 700; letter-spacing: -.01em; }
.lernraum-panel .lr-progress-band { position: relative; display: flex; flex-direction: row; justify-content: flex-start; direction: ltr; flex: none; width: 100%; height: 12px; overflow: hidden; border-radius: 99px; background: var(--pm-track); box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--pm-border) 70%, transparent); }
.lernraum-panel .lr-progress-band-segment { flex: none; min-width: 0; }
@media (prefers-reduced-motion: reduce) {
  .lernraum-panel .lr-bar::after,
  .lernraum-panel .lr-progress-band::after { display: none; }
  .lernraum-panel .lr-bar--updated .lr-bar-seg,
  .lernraum-panel .lr-progress-band--updated .lr-progress-band-segment { transition: none; }
}

.lernraum-panel .lr-page {
  flex: none;
  padding: 30px clamp(24px, 4vw, 52px) 54px;
  display: flex;
  flex-direction: column;
  gap: 38px;
}
.lernraum-panel .lr-section { gap: 17px; }
.lernraum-panel .lr-section-head { align-items: flex-end; justify-content: space-between; gap: 24px; }
.lernraum-panel .lr-section-head > div:first-child { display: flex; flex-direction: column; gap: 4px; }
.lernraum-panel .lr-section-head h2,
.lernraum-panel .lr-cards-head h2 { margin: 0; font: 660 19px/1.25 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-overline { color: var(--pm-accent-text); }

.lernraum-panel .lr-task-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(235px, 1fr)); gap: 14px; align-items: stretch; }
.lernraum-panel .lr-task { grid-column: span 2; display: flex; align-items: center; gap: 14px; min-height: 86px; padding: 14px 16px; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); cursor: pointer; transition: border-color .16s, transform .16s, box-shadow .16s; }
.lernraum-panel .lr-task:hover { transform: translateY(-2px); border-color: color-mix(in oklab, var(--pm-accent) 55%, var(--pm-border)); box-shadow: 0 10px 28px rgba(20, 45, 50, .08); }
.lernraum-panel .lr-task:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }
.lernraum-panel .lr-task-icon { flex: none; display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--pm-selected); color: var(--pm-accent-text); font-size: 17px; }
.lernraum-panel .lr-task-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.lernraum-panel .lr-task-copy > span { color: var(--pm-text-muted); font-size: 12.5px; }
.lernraum-panel .lr-task-copy > strong { display: block; overflow: hidden; width: 100%; max-width: 100%; color: var(--pm-text); font-size: 14px; font-weight: 610; text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-task-preview { display: -webkit-box; overflow: hidden; margin: 5px 0 3px; color: var(--pm-text-muted); font-size: 12.5px; line-height: 1.45; text-wrap: pretty; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.lernraum-panel .lr-task-copy > small { color: var(--pm-text-muted); font-size: 12px; }
.lernraum-panel .lr-task > .lr-btn { flex: none; }
.lernraum-panel .lr-task-action { border-color: color-mix(in oklab, var(--pm-accent) 55%, var(--pm-border)); background: color-mix(in oklab, var(--pm-accent) 10%, var(--pm-surface-card)); color: var(--pm-accent-text); font-weight: 650; }
.lernraum-panel .lr-task-action:hover { border-color: var(--pm-accent); background: color-mix(in oklab, var(--pm-accent) 18%, var(--pm-surface-card)); }

.lernraum-panel .lr-course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(235px, 1fr)); gap: 14px; }
.lernraum-panel .lr-course-card { min-height: 196px; padding: 19px; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); color: var(--pm-text); font-family: var(--pm-font-sans); text-align: left; cursor: pointer; transition: border-color .16s, transform .16s, box-shadow .16s; }
.lernraum-panel .lr-course-card:hover { transform: translateY(-2px); border-color: color-mix(in oklab, var(--pm-accent) 55%, var(--pm-border)); box-shadow: 0 10px 28px rgba(20, 45, 50, .08); }
.lernraum-panel .lr-course-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 22px; }
.lernraum-panel .lr-course-monogram { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; background: var(--pm-selected); color: var(--pm-accent-text); font-size: 12px; font-weight: 740; letter-spacing: .04em; }
.lernraum-panel .lr-course-name { margin-bottom: 5px; font-size: 17px; line-height: 1.25; font-weight: 660; letter-spacing: -.015em; }
.lernraum-panel .lr-course-meta { color: var(--pm-text-muted); font-size: 12.5px; }
.lernraum-panel .lr-course-progress { display: flex; flex-direction: column; gap: 7px; margin-top: 24px; color: var(--pm-text-muted); font-size: 11.5px; }
.lernraum-panel .lr-course-card--add { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; border-style: dashed; color: var(--pm-text-muted); text-align: center; }
.lernraum-panel .lr-course-add-icon { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid var(--pm-border); border-radius: 50%; color: var(--pm-accent-text); font-size: 22px; font-weight: 300; }
.lernraum-panel .lr-course-card--add strong { color: var(--pm-text-muted); font-size: 14px; font-weight: 560; }
.lernraum-panel .lr-course-card--add small { max-width: 210px; color: var(--pm-text-muted); font-size: 11.5px; line-height: 1.45; text-wrap: balance; }
.lernraum-panel .lr-sheet-add strong { color: var(--pm-text-muted); font-size: 14px; font-weight: 560; }
.lernraum-panel .lr-sheet-add small { max-width: 210px; color: var(--pm-text-muted); font-size: 11.5px; line-height: 1.45; text-wrap: balance; }
.lernraum-panel .lr-sheet-add--empty { border-color: color-mix(in oklab, var(--pm-accent) 55%, var(--pm-border)); background: color-mix(in oklab, var(--pm-accent) 5%, var(--pm-surface-card)); }
.lernraum-panel .lr-sheet-add--empty .lr-course-add-icon { width: 44px; height: 44px; border-color: color-mix(in oklab, var(--pm-accent) 62%, var(--pm-border)); background: var(--pm-selected); font-size: 25px; }
.lernraum-panel .lr-sheet-add--empty strong { color: var(--pm-text); font-size: 15px; font-weight: 660; }
.lernraum-panel .lr-sheet-add--empty:hover { border-color: var(--pm-accent); background: color-mix(in oklab, var(--pm-accent) 10%, var(--pm-surface-card)); }

.lernraum-panel .lr-course-overview { display: flex; align-items: center; gap: 28px; padding: 22px 24px; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); }
.lernraum-panel .lr-overview-stat { flex: none; display: flex; flex-direction: column; gap: 3px; min-width: 120px; }
.lernraum-panel .lr-overview-stat strong { font-size: 30px; line-height: 1; font-weight: 690; letter-spacing: -.04em; }
.lernraum-panel .lr-overview-stat span { color: var(--pm-text-muted); font-size: 12px; }
.lernraum-panel .lr-overview-progress { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.lernraum-panel .lr-bar--large { height: 10px; }
.lernraum-panel .lr-bar-key { display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--pm-text-muted); font-size: 11.5px; }
.lernraum-panel .lr-result-dot { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: var(--pm-border); }
.lernraum-panel .lr-result-dot--strong { background: var(--pm-success); }
.lernraum-panel .lr-result-dot--medium { background: var(--pm-star); }
.lernraum-panel .lr-result-dot--weak { background: var(--pm-danger); }
.lernraum-panel .lr-sheet-grid { grid-template-columns: repeat(auto-fill, minmax(235px, 1fr)); grid-auto-rows: 1fr; gap: 14px; }
.lernraum-panel .lr-sheet-grid > * { height: 100%; }
.lernraum-panel .lr-run-list { overflow: hidden; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); }
.lernraum-panel .lr-run-row { position: relative; display: grid; grid-template-columns: 72px minmax(0, 1fr) auto; align-items: center; gap: 18px; padding: 14px 18px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-run-row:first-child { border-top: 0; }
.lernraum-panel .lr-run-delete { position: absolute; top: 8px; right: 8px; display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 50%; padding: 0; background: transparent; color: var(--pm-text-muted); font: 400 18px/1 var(--pm-font-sans); cursor: pointer; transition: background .15s, color .15s; }
.lernraum-panel .lr-run-delete:hover:not(:disabled) { background: color-mix(in oklab, var(--pm-danger) 12%, transparent); color: var(--pm-danger); }
.lernraum-panel .lr-run-delete:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.lernraum-panel .lr-run-delete:disabled { cursor: wait; opacity: .45; }
.lernraum-panel .lr-run-error { margin: -4px 0 0; color: var(--pm-danger); font-size: 12px; line-height: 1.4; }
.lernraum-panel .lr-run-date { display: flex; flex-direction: column; gap: 2px; color: var(--pm-text-muted); font-size: 11.5px; }
.lernraum-panel .lr-run-date strong { color: var(--pm-text); font-size: 12.5px; font-weight: 650; }
.lernraum-panel .lr-run-main { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-run-main strong { overflow: hidden; font-size: 14px; font-weight: 640; text-overflow: ellipsis; white-space: nowrap; }
.lernraum-panel .lr-run-main span { color: var(--pm-text-muted); font-size: 12px; }
.lernraum-panel .lr-run-results { display: flex; align-items: center; gap: 12px; color: var(--pm-text-muted); font: 600 12px/1 var(--pm-font-mono); }
.lernraum-panel .lr-run-result { display: inline-flex; align-items: center; gap: 5px; }
.lernraum-panel .lr-run-result i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.lernraum-panel .lr-run-result--weak { color: var(--pm-danger); }
.lernraum-panel .lr-run-result--medium { color: var(--pm-star); }
.lernraum-panel .lr-run-result--strong { color: var(--pm-success); }
.lernraum-panel .lr-sheet-tile { position: relative; display: flex; flex-direction: column; }
.lernraum-panel .lr-sheet-tile:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }
.lernraum-panel .lr-favorite-sheet-card { border-color: color-mix(in oklab, var(--pm-star) 30%, var(--pm-border)); }
.lernraum-panel .lr-favorite-sheet-star { color: var(--pm-star); font-size: 18px; line-height: 1; }
.lernraum-panel .lr-favorite-sheet-course { margin-bottom: 5px; color: var(--pm-text-muted); font-size: 12px; font-weight: 560; }
.lernraum-panel .lr-sheet-tile-tools { position: absolute; top: 14px; right: 14px; display: flex; align-items: center; gap: 2px; padding: 3px; border-radius: 8px; background: var(--pm-surface-card); opacity: 0; transition: opacity .15s; }
.lernraum-panel .lr-sheet-tile:hover .lr-sheet-tile-tools,
.lernraum-panel .lr-sheet-tile:focus-within .lr-sheet-tile-tools { opacity: 1; }
@media (hover: none) {
  .lernraum-panel .lr-sheet-tile-tools { opacity: 1; }
}
.lernraum-panel .lr-sheet-title-input { width: 100%; margin-bottom: 5px; border: 0; padding: 0; outline: 0; background: transparent; color: var(--pm-text); font: 660 17px/1.25 var(--pm-font-sans); letter-spacing: -.015em; }
.lernraum-panel .lr-sheet-title-input:disabled { opacity: .65; }
.lernraum-panel .lr-sheet-tile-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: auto; padding-top: 18px; }
.lernraum-panel .lr-empty-inline { display: flex; flex-direction: column; align-items: flex-start; gap: 7px; padding: 26px; border: 1px dashed var(--pm-border); border-radius: 14px; background: color-mix(in oklab, var(--pm-surface-card) 70%, transparent); }
.lernraum-panel .lr-empty-inline > span { margin-bottom: 8px; color: var(--pm-text-muted); font-size: 12.5px; }

.lernraum-panel .lr-sheet-page { width: 100%; max-width: 1280px; margin: 0 auto; }
.lernraum-panel .lr-link--danger { color: var(--pm-danger); }
.lernraum-panel .lr-cards-panel { border-radius: 16px; }
.lernraum-panel .lr-cards-head { padding: 18px 20px; }
.lernraum-panel .lr-cards-head > div { display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-card-row { align-items: flex-start; gap: 16px; padding: 17px 20px; }
.lernraum-panel .lr-card-row-idx { flex: none; width: 24px; padding-top: 3px; }
.lernraum-panel .lr-card-front { font-size: 14.5px; font-weight: 590; }
.lernraum-panel .lr-cards-empty { display: flex; flex-direction: column; align-items: center; gap: 9px; padding: 46px 20px; }
.lernraum-panel .lr-cards-empty > span { max-width: 420px; margin-bottom: 4px; color: var(--pm-text-muted); font-size: 12.5px; }
.lernraum-panel .lr-sheet-settings { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding-top: 2px; }

.lernraum-panel .lr-empty-icon { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; background: var(--pm-selected); color: var(--pm-accent-text); font-size: 27px; }

.lernraum-panel--focus { background: color-mix(in oklab, var(--pm-surface-reader) 82%, var(--pm-bg)); }
.lernraum-panel .lr-focus { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: auto; }
.lernraum-panel .lr-learning-focus { animation: lr-learning-surface-in .42s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-learning-focus .lr-learn-head { animation: lr-learning-header-in .38s cubic-bezier(.22, 1, .36, 1) .05s both; }
.lernraum-panel .lr-learning-focus .lr-focus-card,
.lernraum-panel .lr-learning-focus .lr-learn-done { animation: lr-learning-card-in .52s cubic-bezier(.16, 1, .3, 1) .12s both; }
@keyframes lr-learning-surface-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes lr-learning-header-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes lr-learning-card-in {
  from { opacity: 0; transform: translateY(24px) scale(.965); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.lernraum-panel .lr-focus-exit { justify-self: start; display: inline-flex; align-items: center; gap: 8px; height: 34px; padding: 0 14px; border: 1px solid var(--pm-border); border-radius: 99px; background: transparent; color: var(--pm-text-muted); font: 560 13px/1 var(--pm-font-sans); cursor: pointer; transition: color .15s, border-color .15s, background .15s; }
.lernraum-panel .lr-focus-exit:hover { border-color: var(--pm-text-muted); background: var(--pm-chip-bg); color: var(--pm-text); }
.lernraum-panel .lr-focus-exit:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.lernraum-panel .lr-learn-exit-backdrop { position: fixed; inset: 0; z-index: 100; width: 100%; height: 100%; padding: 0; border: 0; background: color-mix(in oklab, var(--pm-bg) 58%, transparent); backdrop-filter: saturate(.35) brightness(.72); cursor: default; }
.lernraum-panel .lr-learn-exit-wrap { position: relative; justify-self: start; z-index: 102; }
.lernraum-panel .lr-learn-exit-warning { position: absolute; top: calc(100% + 12px); left: 0; z-index: 103; width: min(310px, calc(100vw - 40px)); padding: 15px 16px 13px; border: 1px solid color-mix(in oklab, var(--pm-border) 78%, var(--pm-text-muted)); border-radius: 12px; background: var(--pm-surface-card); color: var(--pm-text); box-shadow: 0 12px 30px color-mix(in oklab, #000 32%, transparent); }
.lernraum-panel .lr-learn-exit-warning::before { content: ''; position: absolute; bottom: 100%; left: 24px; width: 12px; height: 12px; border-top: 1px solid color-mix(in oklab, var(--pm-border) 78%, var(--pm-text-muted)); border-left: 1px solid color-mix(in oklab, var(--pm-border) 78%, var(--pm-text-muted)); background: var(--pm-surface-card); transform: translateY(6px) rotate(45deg); }
.lernraum-panel .lr-learn-exit-warning strong { display: block; font: 650 13.5px/1.3 var(--pm-font-sans); }
.lernraum-panel .lr-learn-exit-warning p { margin: 6px 0 2px; font: 450 12.5px/1.45 var(--pm-font-sans); color: var(--pm-text); }
.lernraum-panel .lr-learn-exit-warning > span { display: block; font: 430 11.5px/1.45 var(--pm-font-sans); color: var(--pm-text-muted); }
.lernraum-panel .lr-learn-exit-actions { display: flex; justify-content: flex-end; gap: 7px; margin-top: 12px; }
.lernraum-panel .lr-learn-exit-actions button { height: 29px; padding: 0 10px; border-radius: 8px; font: 600 11.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-learn-exit-cancel { border: 0; background: transparent; color: var(--pm-text-muted); }
.lernraum-panel .lr-learn-exit-cancel:hover { background: var(--pm-chip-bg); color: var(--pm-text); }
.lernraum-panel .lr-learn-exit-confirm { border: 1px solid color-mix(in oklab, var(--pm-danger, #d85d55) 65%, var(--pm-border)); background: color-mix(in oklab, var(--pm-danger, #d85d55) 13%, var(--pm-surface-card)); color: var(--pm-danger, #d85d55); }
.lernraum-panel .lr-learn-exit-confirm:hover { background: color-mix(in oklab, var(--pm-danger, #d85d55) 22%, var(--pm-surface-card)); }
.lernraum-panel .lr-learn-exit-actions button:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.lr-exit-warning-enter-active,
.lr-exit-warning-leave-active { transition: opacity .16s ease, transform .18s cubic-bezier(.22, 1, .36, 1); transform-origin: 28px top; }
.lr-exit-warning-enter-from,
.lr-exit-warning-leave-to { opacity: 0; transform: translateY(-5px) scale(.97); }
.lr-exit-backdrop-enter-active,
.lr-exit-backdrop-leave-active { transition: opacity .18s ease; }
.lr-exit-backdrop-enter-from,
.lr-exit-backdrop-leave-to { opacity: 0; }
.lernraum-panel .lr-focus-stage { position: relative; isolation: isolate; flex: 1; display: grid; place-items: center; overflow: hidden; padding: 34px 24px 64px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-confetti { position: absolute; z-index: 1; inset: 0; overflow: hidden; pointer-events: none; }
.lernraum-panel .lr-confetti i { position: absolute; top: -24px; left: var(--confetti-x); width: var(--confetti-size); height: calc(var(--confetti-size) * .58); border-radius: 2px; background: var(--confetti-color); opacity: 0; transform-origin: center; will-change: transform, opacity; animation: lr-confetti-fall var(--confetti-duration) var(--confetti-delay) linear both; }
.lernraum-panel .lr-confetti i:nth-child(3n) { height: var(--confetti-size); border-radius: 50%; }
.lernraum-panel .lr-confetti i:nth-child(4n) { width: calc(var(--confetti-size) * .48); height: calc(var(--confetti-size) * 1.35); }
.lernraum-panel .lr-focus-card { width: fit-content; min-width: min(100%, 360px); max-width: min(100%, 720px); perspective: 1400px; interpolate-size: allow-keywords; transition: width .34s cubic-bezier(.2,.72,.2,1); }
.lernraum-panel .lr-focus-card-inner { position: relative; width: 100%; transform-style: preserve-3d; transition: transform .76s cubic-bezier(.34,1.24,.64,1); }
.lernraum-panel .lr-focus-card--revealed .lr-focus-card-inner { transform: rotateY(180deg); }
.lernraum-panel .lr-focus-card-face { position: absolute; top: 0; left: 0; width: 100%; min-width: 0; display: flex; flex-direction: column; padding: clamp(26px, 3vw, 34px) clamp(28px, 5vw, 50px); border: 1px solid var(--pm-border); border-radius: 22px; background: var(--pm-surface-card); box-shadow: 0 18px 60px rgba(0, 0, 0, .24); backface-visibility: hidden; -webkit-backface-visibility: hidden; }
.lernraum-panel .lr-focus-card-face--front { position: relative; width: auto; min-height: 300px; overflow: hidden; }
.lernraum-panel .lr-focus-card-face--back { transform: rotateY(180deg); }
.lernraum-panel .lr-focus-card--revealed .lr-focus-card-face--front { position: absolute; width: 100%; }
.lernraum-panel .lr-focus-card--revealed .lr-focus-card-face--back { position: relative; width: auto; }
.lernraum-panel .lr-focus-card-meta { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; color: var(--pm-text-muted); font-family: var(--pm-font-mono); font-size: 11.5px; }
.lernraum-panel .lr-focus-card-meta .lr-kind-chip { color: #fff !important; }
.lernraum-panel .lr-learn-answered { --lr-assessment-color: var(--pm-success); position: absolute; z-index: 2; top: 25px; right: -47px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: 172px; height: 32px; background: var(--lr-assessment-color); color: #fff; font: 700 11px/1 var(--pm-font-sans); letter-spacing: .045em; text-transform: uppercase; transform: rotate(45deg); transform-origin: center; }
.lernraum-panel .lr-learn-answered--weak { --lr-assessment-color: var(--pm-danger); top: 34px; right: -67px; width: 230px; }
.lernraum-panel .lr-learn-answered--medium { --lr-assessment-color: var(--pm-star); top: 29px; right: -55px; width: 194px; color: oklch(0.20 0.035 75); }
.lernraum-panel .lr-learn-answered--strong { --lr-assessment-color: var(--pm-success); }
.lernraum-panel .lr-focus-card--revealed .lr-learn-answered { opacity: 0; visibility: hidden; }
.lernraum-panel .lr-learn-flip-back { display: inline-flex; align-items: center; gap: 6px; padding: 3px 0; border: 0; background: transparent; color: var(--pm-text-muted); font: 560 12.5px/1.3 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-learn-flip-back:hover { color: var(--pm-text); }
.lernraum-panel .lr-learn-flip-back:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; border-radius: 3px; }
.lernraum-panel .lr-focus-card .lr-learn-front { font-size: clamp(21px, 3vw, 28px); line-height: 1.4; font-weight: 620; }
.lernraum-panel .lr-focus-card .lr-learn-back { margin-top: 32px; padding-top: 24px; }
.lernraum-panel .lr-focus-card .lr-learn-actions { margin-top: auto; padding-top: 40px; }
.lernraum-panel .lr-learn-assessment { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--pm-border); }
.lernraum-panel .lr-focus-card-face--back .lr-learn-actions { margin-top: 12px; padding-top: 0; }
.lernraum-panel .lr-btn--learn { width: 100%; min-height: 48px; font-size: 14px; }
.lernraum-panel .lr-learn-hint-link { align-self: flex-start; display: inline-flex; align-items: center; gap: 6px; min-width: 124px; margin-top: 12px; padding: 2px 0; border: 0; background: transparent; color: var(--pm-text-muted); font: 560 12.5px/1.3 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-learn-hint-link:hover:not([disabled]) { color: var(--pm-accent-text); }
.lernraum-panel .lr-learn-hint-link:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; border-radius: 3px; }
.lernraum-panel .lr-learn-hint-link[disabled] { cursor: wait; opacity: .65; }
.lernraum-panel .lr-learn-hint-shell { display: grid; width: 100%; min-width: 0; grid-template-rows: 1fr; margin-top: 6px; transition: grid-template-rows .34s cubic-bezier(.22,1,.36,1), margin-top .34s cubic-bezier(.22,1,.36,1), opacity .24s ease, transform .34s cubic-bezier(.22,1,.36,1); }
.lernraum-panel .lr-learn-hint-shell > .lr-learn-hint { min-height: 0; overflow: hidden; }
.lernraum-panel .lr-learn-hint-reveal-enter-from,
.lernraum-panel .lr-learn-hint-reveal-leave-to { grid-template-rows: 0fr; margin-top: 0; opacity: 0; transform: translateY(-6px); }
.lernraum-panel .lr-learn-hint-reveal-leave-active { transition-duration: .24s; }
.lernraum-panel .lr-learn-hint { width: 100%; min-width: 0; contain: inline-size; padding: 14px 16px 15px; border-radius: 12px; background: color-mix(in oklab, var(--pm-accent) 11%, transparent); color: var(--pm-text); overflow-wrap: anywhere; }
.lernraum-panel .lr-learn-hint p { margin: 0; font-size: 14px; line-height: 1.55; }
.lernraum-panel .lr-learn-hint .lr-learn-hint-error { color: var(--pm-danger); }
.lernraum-panel .lr-learn-card-nav { display: flex; justify-content: center; gap: 10px; margin-top: 16px; }
.lernraum-panel .lr-learn-card-nav .lr-nq-arrow {
  width: 40px;
  border-color: color-mix(in oklab, var(--pm-text-muted) 58%, var(--pm-border));
  border-radius: 99px;
  background: color-mix(in oklab, var(--pm-surface-card) 84%, var(--pm-text) 16%);
  color: var(--pm-text);
  box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--pm-text) 7%, transparent);
}
.lernraum-panel .lr-learn-card-nav .lr-nq-arrow svg { stroke-width: 2.35; }
.lernraum-panel .lr-learn-card-nav .lr-nq-arrow:hover:not(:disabled) {
  border-color: var(--pm-accent);
  background: var(--pm-selected);
  color: var(--pm-accent-text);
}
.lernraum-panel .lr-learn-card-nav .lr-nq-arrow:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }
.lernraum-panel .lr-learn-card-nav .lr-nq-arrow:disabled {
  border-color: color-mix(in oklab, var(--pm-text-muted) 38%, var(--pm-border));
  background: color-mix(in oklab, var(--pm-surface-card) 92%, var(--pm-text) 8%);
  color: var(--pm-text-muted);
  opacity: .58;
}
.lernraum-panel .lr-assess { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 48px; }
.lernraum-panel .lr-assess kbd { display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 5px; border: 1px solid var(--pm-border); border-radius: 5px; background: var(--pm-surface-reader); color: var(--pm-text-muted); font: 500 10px/1 var(--pm-font-mono); }
.lernraum-panel .lr-learn-selfhint { margin: 0; }
.lernraum-panel .lr-learn-done { position: relative; z-index: 2; max-width: 680px; margin: 0; padding: 38px clamp(28px, 5vw, 64px) 34px; gap: 14px; overflow: hidden; border: 1px solid var(--pm-border); border-radius: 22px; background: color-mix(in oklab, var(--pm-surface-card) 88%, transparent); box-shadow: 0 18px 60px rgba(0, 0, 0, .24); backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px); }
.lernraum-panel .lr-learn-done p { margin: -5px 0 7px; color: var(--pm-text-muted); font-size: 13px; }
.lernraum-panel .lr-done-orbit { position: relative; display: grid; place-items: center; width: 158px; height: 158px; margin-bottom: 6px; }
.lernraum-panel .lr-learn-done .lr-done-orbit { animation: lr-done-orbit-pop .62s cubic-bezier(.34, 1.56, .64, 1) .2s both; }
.lernraum-panel .lr-learn-done .lr-learn-done-title { animation: lr-done-item-in .42s cubic-bezier(.22, 1, .36, 1) .34s both; }
.lernraum-panel .lr-learn-done > p { animation: lr-done-item-in .42s cubic-bezier(.22, 1, .36, 1) .42s both; }
.lernraum-panel .lr-learn-done .lr-done-results { animation: lr-done-item-in .42s cubic-bezier(.22, 1, .36, 1) .5s both; }
.lernraum-panel .lr-learn-done .lr-done-actions { animation: lr-done-item-in .42s cubic-bezier(.22, 1, .36, 1) .64s both; }
.lernraum-panel .lr-done-orbit svg { position: absolute; inset: 0; width: 100%; height: 100%; transform: rotate(-90deg); overflow: visible; }
.lernraum-panel .lr-done-orbit circle { fill: none; stroke-width: 7; }
.lernraum-panel .lr-done-orbit-track { stroke: var(--pm-track); }
.lernraum-panel .lr-done-orbit-value { stroke: var(--pm-accent); stroke-linecap: round; stroke-dasharray: 100; stroke-dashoffset: var(--done-offset); animation: lr-done-ring-fill .9s cubic-bezier(.22, 1, .36, 1) .18s both; }
.lernraum-panel .lr-done-orbit-copy { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.lernraum-panel .lr-done-orbit-copy strong { font: 710 31px/1 var(--pm-font-sans); letter-spacing: -.04em; color: var(--pm-text); }
.lernraum-panel .lr-done-orbit-copy span { color: var(--pm-text-muted); font: 560 10.5px/1 var(--pm-font-sans); letter-spacing: .04em; text-transform: uppercase; }
.lernraum-panel .lr-learn-done-title { font-size: 23px; }
.lernraum-panel .lr-done-results { display: flex; flex-direction: column; width: min(100%, 400px); gap: 11px; margin: 3px 0 7px; color: var(--pm-text-muted); font-size: 12.5px; }
.lernraum-panel .lr-done-result-label { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 8px; margin-bottom: 5px; }
.lernraum-panel .lr-done-result-label .lr-result-dot { margin: 0; }
.lernraum-panel .lr-done-result-label span { text-align: left; }
.lernraum-panel .lr-done-result-label strong { color: var(--pm-text); font-variant-numeric: tabular-nums; }
.lernraum-panel .lr-done-result-track { height: 7px; overflow: hidden; border-radius: 99px; background: var(--pm-track); }
.lernraum-panel .lr-done-result-track i { display: block; height: 100%; min-width: 0; border-radius: inherit; transform-origin: left; animation: lr-done-bar-grow .72s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-done-result-row--strong .lr-done-result-track i { background: var(--pm-success); animation-delay: .4s; }
.lernraum-panel .lr-done-result-row--medium .lr-done-result-track i { background: var(--pm-star); animation-delay: .5s; }
.lernraum-panel .lr-done-result-row--weak .lr-done-result-track i { background: var(--pm-danger); animation-delay: .6s; }
.lernraum-panel .lr-done-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 8px 14px; margin-top: 5px; }
.lernraum-panel .lr-done-restart { height: 38px; padding: 0 11px; border: 0; background: transparent; color: var(--pm-text-muted); font: 600 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-done-restart:hover { color: var(--pm-text); }
.lernraum-panel .lr-done-restart:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; border-radius: 7px; }
@keyframes lr-done-ring-fill { from { stroke-dashoffset: 100; } to { stroke-dashoffset: var(--done-offset); } }
@keyframes lr-done-bar-grow { from { transform: scaleX(0); opacity: .25; } to { transform: scaleX(1); opacity: 1; } }
@keyframes lr-done-orbit-pop { from { opacity: 0; transform: scale(.68) rotate(-8deg); } 70% { opacity: 1; transform: scale(1.06) rotate(2deg); } to { opacity: 1; transform: scale(1) rotate(0); } }
@keyframes lr-done-item-in { from { opacity: 0; transform: translateY(9px); } to { opacity: 1; transform: translateY(0); } }
@keyframes lr-confetti-fall {
  0% { opacity: 0; transform: translate3d(0, -28px, 0) rotate(0deg) rotateY(0deg); }
  5% { opacity: 1; }
  16% { transform: translate3d(var(--confetti-sway), 12vh, 0) rotate(75deg) rotateY(135deg); }
  32% { transform: translate3d(var(--confetti-sway-back), 29vh, 0) rotate(185deg) rotateY(280deg); }
  49% { transform: translate3d(var(--confetti-sway), 48vh, 0) rotate(310deg) rotateY(430deg); }
  66% { transform: translate3d(var(--confetti-sway-back), 68vh, 0) rotate(440deg) rotateY(590deg); }
  83% { opacity: 1; transform: translate3d(var(--confetti-sway), 88vh, 0) rotate(570deg) rotateY(760deg); }
  100% { opacity: 0; transform: translate3d(var(--confetti-drift), calc(100vh + 70px), 0) rotate(var(--confetti-rotate)) rotateY(900deg); }
}

/* Lernblatt: reduziert auf Status, Hauptaktion und die Karten selbst. */
.lernraum-panel .lr-sheet-page { gap: 38px; }
.lernraum-panel .lr-sheet-column { min-width: 0; display: flex; flex-direction: column; gap: 17px; }
.lernraum-panel .lr-sheet-column-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; min-height: 46px; }
.lernraum-panel .lr-sheet-column-head > div { display: flex; flex-direction: column; gap: 4px; }
.lernraum-panel .lr-sheet-column-head h2 { margin: 0; font: 660 19px/1.25 var(--pm-font-sans); letter-spacing: -.02em; }
.lernraum-panel .lr-sheet-column-head--sticky { position: sticky; z-index: 5; top: 0; }
.lernraum-panel .lr-sheet-progress { min-width: 0; display: flex; flex-direction: column; gap: 17px; }
.lernraum-panel .lr-progress-label-toggle { display: inline-flex; align-items: center; align-self: flex-start; gap: 8px; padding: 0; border: 0; background: transparent; color: var(--pm-accent-text); cursor: pointer; }
.lernraum-panel .lr-progress-label-toggle:hover { color: var(--pm-text); }
.lernraum-panel .lr-progress-label-toggle:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; border-radius: 3px; }
.lernraum-panel .lr-progress-label-toggle svg { width: 17px; height: 17px; fill: currentColor; transition: transform .24s cubic-bezier(.22, 1, .36, 1); }
.lernraum-panel .lr-progress-label-toggle[aria-expanded="false"] svg { transform: rotate(-90deg); }
.lernraum-panel .lr-progress-content { display: flex; min-width: 0; flex-direction: column; gap: 17px; }
.lr-progress-reveal-enter-active,
.lr-progress-reveal-leave-active { transition: opacity .2s ease, transform .24s cubic-bezier(.22, 1, .36, 1); }
.lr-progress-reveal-enter-from,
.lr-progress-reveal-leave-to { opacity: 0; transform: translateY(-8px); }
.lernraum-panel .lr-progress-chart-card { overflow: hidden; border: 1px solid var(--pm-border); border-radius: 18px; background: var(--pm-surface-card); }
.lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-summary,
.lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-scroll { animation: lr-chart-intro .32s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-progress-chart-summary { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 20px 24px 10px; }
.lernraum-panel .lr-progress-chart-summary > div:first-child { display: flex; flex-direction: column; gap: 3px; }
.lernraum-panel .lr-progress-chart-summary strong { color: var(--pm-text); font-size: 28px; line-height: 1; letter-spacing: -.04em; }
.lernraum-panel .lr-progress-chart-summary > div:first-child span { color: var(--pm-text-muted); font-size: 12px; }
.lernraum-panel .lr-progress-chart-legend { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px 16px; color: var(--pm-text-muted); font-size: 11.5px; }
.lernraum-panel .lr-progress-chart-legend span { display: inline-flex; align-items: center; white-space: nowrap; }
.lernraum-panel .lr-chart-line-key { width: 18px; height: 2px; margin-right: 6px; border-radius: 99px; background: var(--pm-accent); box-shadow: 5px 0 0 -1px var(--pm-surface-card), 5px 0 0 1px var(--pm-accent); }
.lernraum-panel .lr-progress-chart-scroll { overflow-x: auto; padding: 0 14px 4px; scrollbar-width: thin; }
.lernraum-panel .lr-progress-chart { display: block; min-width: 100%; height: 180px; overflow: visible; }
.lernraum-panel .lr-chart-grid line { stroke: var(--pm-border); stroke-width: 1; stroke-dasharray: 3 6; }
.lernraum-panel .lr-chart-grid text { fill: var(--pm-text-muted); font: 10px var(--pm-font-mono); }
.lernraum-panel .lr-chart-bar-bg { fill: var(--pm-track); }
.lernraum-panel .lr-chart-bar { transform-box: fill-box; transform-origin: center bottom; transition: opacity .15s; }
.lernraum-panel .lr-chart-run--intro .lr-chart-bar { animation: lr-chart-bar-intro .42s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-chart-run--fresh .lr-chart-bar { animation: lr-chart-bar-rise .58s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-chart-bar--strong { fill: var(--pm-success); }
.lernraum-panel .lr-chart-bar--medium { fill: var(--pm-star); }
.lernraum-panel .lr-chart-bar--weak { fill: var(--pm-danger); }
.lernraum-panel .lr-chart-run--paused .lr-chart-bar { opacity: .42; }
.lernraum-panel .lr-chart-run--paused .lr-chart-bar-bg { stroke: var(--pm-text-muted); stroke-width: 1; stroke-dasharray: 4 4; }
.lernraum-panel .lr-chart-run:focus { outline: none; }
.lernraum-panel .lr-chart-run:focus .lr-chart-bar-bg { stroke: var(--pm-accent); stroke-width: 2; }
.lernraum-panel .lr-chart-date { fill: var(--pm-text); font: 600 10.5px var(--pm-font-sans); }
.lernraum-panel .lr-chart-time { fill: var(--pm-text-muted); font: 10px var(--pm-font-mono); }
.lernraum-panel .lr-chart-score-line { fill: none; stroke: var(--pm-accent); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
.lernraum-panel .lr-progress-chart-card--intro .lr-chart-score-line { stroke-dasharray: 1; stroke-dashoffset: 1; animation: lr-chart-line-draw .56s cubic-bezier(.22, 1, .36, 1) .12s both; }
.lernraum-panel .lr-chart-score-point { fill: var(--pm-surface-card); stroke: var(--pm-accent); stroke-width: 3; vector-effect: non-scaling-stroke; transform-box: fill-box; transform-origin: center; }
.lernraum-panel .lr-progress-chart-card--intro .lr-chart-score-point { animation: lr-chart-point-in .32s cubic-bezier(.22, 1, .36, 1) both; }
.lernraum-panel .lr-chart-score-point--fresh { animation: lr-chart-point-pop .5s cubic-bezier(.34, 1.56, .64, 1) both; }
@keyframes lr-chart-bar-intro { from { opacity: .2; transform: scaleY(.72); } to { opacity: 1; transform: scaleY(1); } }
@keyframes lr-chart-bar-rise { from { opacity: .16; transform: scaleY(.04); } 72% { opacity: 1; transform: scaleY(1.045); } to { opacity: 1; transform: scaleY(1); } }
@keyframes lr-chart-line-draw { to { stroke-dashoffset: 0; } }
@keyframes lr-chart-point-in { from { opacity: 0; transform: scale(.35); } to { opacity: 1; transform: scale(1); } }
@keyframes lr-chart-point-pop { from { transform: scale(.55); } 65% { transform: scale(1.45); } to { transform: scale(1); } }
@keyframes lr-chart-intro { from { opacity: .58; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.lernraum-panel .lr-course-page--empty { flex: 1; min-height: 0; }
.lernraum-panel .lr-course-empty-page { flex: 1; min-height: 0; display: grid; place-items: center; }
.lernraum-panel .lr-sheet-page--empty { flex: 1; min-height: 0; }
.lernraum-panel .lr-sheet-empty-page { flex: 1; min-height: 0; display: grid; place-items: center; }
.lernraum-panel .lr-history-empty { padding: 22px 20px; border: 1px dashed var(--pm-border); border-radius: 14px; background: color-mix(in oklab, var(--pm-surface-card) 70%, transparent); }
.lernraum-panel .lr-history-empty span { color: var(--pm-text); font-size: 13.5px; font-weight: 620; }
.lernraum-panel .lr-history-empty p { margin: 6px 0 0; color: var(--pm-text-muted); font-size: 12.5px; line-height: 1.5; }
.lernraum-panel .lr-favorite-toggle { display: inline-flex; align-items: center; gap: 7px; height: 32px; padding: 0 12px; border: 0; border-radius: 99px; background: transparent; color: var(--pm-text-muted); font: 560 12px/1 var(--pm-font-sans); cursor: pointer; transition: background .15s, color .15s; }
.lernraum-panel .lr-favorite-toggle:hover { background: transparent; color: var(--pm-text); }
.lernraum-panel .lr-favorite-toggle:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.lernraum-panel .lr-favorite-toggle:disabled { cursor: default; }
.lernraum-panel .lr-favorite-toggle--on { background: transparent; color: var(--pm-star); }
.lernraum-panel .lr-favorite-icon-wrap { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; }
.lernraum-panel .lr-favorite-icon-wrap--pop { animation: lr-fav-star-pop 420ms cubic-bezier(.34, 1.56, .64, 1); }
.lernraum-panel .lr-favorite-icon-wrap--pop::after { content: ''; position: absolute; top: 50%; left: 50%; box-sizing: border-box; width: 26px; height: 26px; border: 2px solid var(--pm-star); border-radius: 999px; pointer-events: none; animation: lr-fav-star-ring 480ms ease-out forwards; }
.lernraum-panel .lr-favorite-icon { position: relative; z-index: 1; font-size: 16px; line-height: 1; }
.lernraum-panel .lr-head-actions .lr-favorite-toggle { height: 38px; }
@keyframes lr-fav-star-pop { 0% { transform: scale(1); } 35% { transform: scale(1.32); } 60% { transform: scale(.94); } 100% { transform: scale(1); } }
@keyframes lr-fav-star-ring { 0% { transform: translate(-50%, -50%) scale(.5); opacity: .55; } 100% { transform: translate(-50%, -50%) scale(1.8); opacity: 0; } }
.pm-no-animations .lernraum-panel .lr-favorite-icon-wrap--pop,
.pm-no-animations .lernraum-panel .lr-favorite-icon-wrap--pop::after { animation: none; }
@media (prefers-reduced-motion: reduce) {
  .lernraum-panel .lr-favorite-icon-wrap--pop,
  .lernraum-panel .lr-favorite-icon-wrap--pop::after { animation: none; }
}
.lernraum-panel .lr-cards-list { display: flex; flex-direction: column; gap: 12px; }
.lernraum-panel .lr-cards-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); grid-auto-rows: 1fr; gap: 12px; }
.lernraum-panel .lr-cards-grid .lr-card-row { height: 150px; overflow: hidden; }
.lernraum-panel .lr-cards-grid .lr-card-row-main { min-height: 0; overflow: hidden; }
.lernraum-panel .lr-cards-grid .lr-card-front,
.lernraum-panel .lr-cards-grid .lr-card-back { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; }
.lernraum-panel .lr-cards-grid .lr-card-front { -webkit-line-clamp: 2; }
.lernraum-panel .lr-cards-grid .lr-card-back { -webkit-line-clamp: 3; }
.lernraum-panel .lr-cards-list .lr-card-row { gap: 16px; padding: 18px 20px; border: 1px solid var(--pm-border); border-radius: 14px; background: var(--pm-surface-card); cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.lernraum-panel .lr-cards-list .lr-card-row:hover,
.lernraum-panel .lr-cards-list .lr-card-row:focus-within { border-color: color-mix(in oklab, var(--pm-accent) 45%, var(--pm-border)); }
.lernraum-panel .lr-cards-list .lr-card-row:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; box-shadow: 0 4px 18px color-mix(in oklab, var(--pm-accent) 12%, transparent); }
.lernraum-panel .lr-card-kind { font: 640 10.5px/1 var(--pm-font-sans); letter-spacing: .08em; text-transform: uppercase; }
.lernraum-panel .lr-cards-list .lr-card-front { font-size: 15.5px; font-weight: 650; }
.lernraum-panel .lr-cards-list .lr-card-back { font-size: 13.5px; line-height: 1.6; color: color-mix(in oklab, var(--pm-text) 72%, var(--pm-bg)); }
.lernraum-panel .lr-cards-list .lr-card-row-actions { opacity: 0; transition: opacity .15s; }
.lernraum-panel .lr-cards-list .lr-card-row:hover .lr-card-row-actions,
.lernraum-panel .lr-cards-list .lr-card-row:focus-within .lr-card-row-actions { opacity: 1; }
@media (hover: none) { .lernraum-panel .lr-cards-list .lr-card-row-actions { opacity: 1; } }

@media (max-width: 760px) {
  .lernraum-panel .lr-page { padding: 25px 18px 40px; gap: 32px; }
  .lernraum-panel .lr-section-head { align-items: flex-start; flex-direction: column; gap: 7px; }
  .lernraum-panel .lr-section-meta { margin-left: 0; }
  .lernraum-panel .lr-course-overview { align-items: flex-start; flex-direction: column; }
  .lernraum-panel .lr-overview-progress { width: 100%; }
  .lernraum-panel .lr-sheet-settings { align-items: flex-start; flex-direction: column; }
  .lernraum-panel .lr-focus-stage { padding: 18px 14px 36px; }
  .lernraum-panel .lr-focus-card-face { padding: 26px 22px; }
  .lernraum-panel .lr-focus-card-face--front { min-height: 280px; }
  .lernraum-panel .lr-focus-card .lr-learn-actions { flex-direction: column; }
  .lernraum-panel .lr-run-row { grid-template-columns: 60px minmax(0, 1fr); gap: 12px; }
  .lernraum-panel .lr-run-results { grid-column: 2; }
  .lernraum-panel .lr-progress-chart-summary { align-items: flex-start; flex-direction: column; padding: 18px 18px 8px; }
  .lernraum-panel .lr-progress-chart-legend { justify-content: flex-start; }
  .lernraum-panel .lr-progress-chart-scroll { padding-inline: 4px; }
}

@media (max-width: 1050px) {
  .lernraum-panel .lr-cards-grid { grid-template-columns: minmax(0, 1fr); }
}

@media (prefers-reduced-motion: reduce) {
  .lernraum-panel .lr-progress-label-toggle svg,
  .lr-progress-reveal-enter-active,
  .lr-progress-reveal-leave-active { transition: none; }
  .lernraum-panel .lr-chart-bar,
  .lernraum-panel .lr-chart-score-line,
  .lernraum-panel .lr-chart-score-point,
  .lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-summary,
  .lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-scroll { animation: none; }
  .lernraum-panel .lr-bar--updated,
  .lernraum-panel .lr-progress-band--updated { animation: none; }
  .lernraum-panel .lr-confetti { display: none; }
  .lernraum-panel .lr-learning-focus,
  .lernraum-panel .lr-learning-focus .lr-learn-head,
  .lernraum-panel .lr-learning-focus .lr-focus-card,
  .lernraum-panel .lr-learning-focus .lr-learn-done,
  .lernraum-panel .lr-learning-focus .lr-learn-progress-ring,
  .lernraum-panel .lr-learn-done .lr-done-orbit,
  .lernraum-panel .lr-learn-done .lr-done-orbit-value,
  .lernraum-panel .lr-learn-done .lr-learn-done-title,
  .lernraum-panel .lr-learn-done > p,
  .lernraum-panel .lr-learn-done .lr-done-results,
  .lernraum-panel .lr-learn-done .lr-done-actions,
  .lernraum-panel .lr-learn-done .lr-done-result-track i { animation: none; }
  .lernraum-panel .lr-learn-hint-shell { transition: none; }
  .lernraum-panel .lr-focus-card,
  .lernraum-panel .lr-focus-card-inner { transition: none; }
}

.pm-no-animations .lernraum-panel .lr-learning-focus,
.pm-no-animations .lernraum-panel .lr-learning-focus .lr-learn-head,
.pm-no-animations .lernraum-panel .lr-learning-focus .lr-focus-card,
.pm-no-animations .lernraum-panel .lr-learning-focus .lr-learn-done,
.pm-no-animations .lernraum-panel .lr-learning-focus .lr-learn-progress-ring,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-done-orbit,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-done-orbit-value,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-learn-done-title,
.pm-no-animations .lernraum-panel .lr-learn-done > p,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-done-results,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-done-actions,
.pm-no-animations .lernraum-panel .lr-learn-done .lr-done-result-track i { animation: none; }
.pm-no-animations .lernraum-panel .lr-confetti { display: none; }
.pm-no-animations .lernraum-panel .lr-progress-label-toggle svg,
.pm-no-animations .lr-progress-reveal-enter-active,
.pm-no-animations .lr-progress-reveal-leave-active { transition: none; }
.pm-no-animations .lernraum-panel .lr-chart-bar,
.pm-no-animations .lernraum-panel .lr-chart-score-line,
.pm-no-animations .lernraum-panel .lr-chart-score-point,
.pm-no-animations .lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-summary,
.pm-no-animations .lernraum-panel .lr-progress-chart-card--intro .lr-progress-chart-scroll { animation: none; }
.pm-no-animations .lernraum-panel .lr-bar--updated,
.pm-no-animations .lernraum-panel .lr-progress-band--updated { animation: none; }
.pm-no-animations .lernraum-panel .lr-learn-hint-shell { transition: none; }

@media (max-width: 500px) {
  .lernraum-panel .lr-course-grid,
  .lernraum-panel .lr-sheet-grid,
  .lernraum-panel .lr-task-list { grid-template-columns: 1fr; }
  .lernraum-panel .lr-task { grid-column: span 1; align-items: flex-start; }
  .lernraum-panel .lr-task > .lr-btn { align-self: center; }
}

/* Schrittfolge – Editor in der Nachbereitung */
.lernraum-panel .lr-nq-steps { display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-steps-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.lernraum-panel .lr-steps-row { display: flex; align-items: center; gap: 8px; }
.lernraum-panel .lr-steps-num { flex: none; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font: 620 11px/1 var(--pm-font-mono); color: var(--pm-accent-text); background: var(--pm-selected); }
.lernraum-panel .lr-steps-input { flex: 1; min-width: 0; }
.lernraum-panel .lr-steps-move, .lernraum-panel .lr-steps-del { flex: none; width: 28px; height: 28px; border: 1px solid var(--pm-border); border-radius: 7px; background: var(--pm-bg); color: var(--pm-text-muted); cursor: pointer; font-size: 13px; line-height: 1; }
.lernraum-panel .lr-steps-move:hover:not(:disabled), .lernraum-panel .lr-steps-del:hover { color: var(--pm-text); background: var(--pm-surface-reader); }
.lernraum-panel .lr-steps-move:disabled { opacity: .4; cursor: default; }
.lernraum-panel .lr-steps-del:hover { color: var(--pm-danger); border-color: var(--pm-danger); }
.lernraum-panel .lr-steps-add { align-self: flex-start; height: 30px; padding: 0 12px; border: 1px dashed var(--pm-border); border-radius: 8px; background: transparent; color: var(--pm-text-muted); font: 520 12.5px/1 var(--pm-font-sans); cursor: pointer; }
.lernraum-panel .lr-steps-add:hover { color: var(--pm-accent-text); border-color: var(--pm-accent); }
.lernraum-panel .lr-steps-hint { margin: 2px 0 0; font-size: 11.5px; color: var(--pm-text-muted); }

/* Schrittfolge – Lernmodus (Reihenfolge ordnen) */
.lernraum-panel .lr-focus-card--seq { width: min(640px, 100%); max-width: 640px; padding: 28px 30px; border: 1px solid var(--pm-border); border-radius: 16px; background: var(--pm-surface-card); display: flex; flex-direction: column; gap: 16px; }
.lernraum-panel .lr-seq-instruction { margin: 0; font-size: 13px; color: var(--pm-text-muted); }
.lernraum-panel .lr-seq-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.lernraum-panel .lr-seq-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--pm-border); border-radius: 10px; background: var(--pm-bg); }
.lernraum-panel .lr-seq-pos { flex: none; width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font: 620 12px/1 var(--pm-font-mono); color: var(--pm-text-muted); background: var(--pm-chip-bg); }
.lernraum-panel .lr-seq-text { flex: 1; min-width: 0; font: 500 14.5px/1.45 var(--pm-font-sans); color: var(--pm-text); }
.lernraum-panel .lr-seq-hintpos { flex: none; font: 620 11px/1 var(--pm-font-mono); color: var(--pm-success); }
.lernraum-panel .lr-seq-moves { flex: none; display: flex; gap: 4px; }
.lernraum-panel .lr-seq-move { width: 30px; height: 30px; border: 1px solid var(--pm-border); border-radius: 7px; background: var(--pm-surface-card); color: var(--pm-text-muted); cursor: pointer; font-size: 14px; line-height: 1; }
.lernraum-panel .lr-seq-move:hover:not(:disabled) { color: var(--pm-accent-text); border-color: var(--pm-accent); }
.lernraum-panel .lr-seq-move:disabled { opacity: .35; cursor: default; }
.lernraum-panel .lr-seq-item--ok { border-color: color-mix(in oklab, var(--pm-success) 55%, var(--pm-border)); background: color-mix(in oklab, var(--pm-success) 9%, var(--pm-bg)); }
.lernraum-panel .lr-seq-item--ok .lr-seq-pos { color: var(--pm-on-accent); background: var(--pm-success); }
.lernraum-panel .lr-seq-item--bad { border-color: color-mix(in oklab, var(--pm-danger) 45%, var(--pm-border)); background: color-mix(in oklab, var(--pm-danger) 8%, var(--pm-bg)); }
.lernraum-panel .lr-seq-item--bad .lr-seq-pos { color: var(--pm-on-accent); background: var(--pm-danger); }
</style>

<style scoped>
/* Match the exit popover backdrop on the teleported Vuetify menu. */
:global(.lr-learn-start-overlay .v-overlay__scrim) {
  opacity: 1;
  background: color-mix(in oklab, var(--pm-bg) 58%, transparent);
  backdrop-filter: saturate(.35) brightness(.72);
}
.lr-learn-start-panel { overflow: visible; }
 .lernraum-panel .lr-learn-start-options { position: relative; top: auto; left: auto; margin-top: 6px; width: min(360px, calc(100vw - 32px)); padding: 20px; border-radius: 16px; }
.lernraum-panel .lr-learn-start-options::before { left: auto; right: 24px; }
.lr-start-heading { display: flex; align-items: center; gap: 12px; }
.lr-start-heading-icon { display: grid; place-items: center; flex: none; width: 38px; height: 38px; border-radius: 12px; background: color-mix(in oklab, var(--pm-accent) 12%, var(--pm-surface-card)); color: var(--pm-accent-text); }
.lernraum-panel .lr-start-heading strong { font-size: 16px; }
.lernraum-panel .lr-start-heading p { margin: 4px 0 0; font-size: 12px; color: var(--pm-text-muted); }
.lr-learn-start-options fieldset { border: 0; padding: 0; margin: 20px 0 0; min-width: 0; }
.lr-learn-start-options legend { margin-bottom: 9px; font-size: 11px; font-weight: 600; color: var(--pm-text-muted); }
.lr-start-choice { display: flex; align-items: center; gap: 12px; padding: 12px; margin-bottom: 7px; border: 1px solid var(--pm-border); border-radius: 10px; cursor: pointer; transition: background .15s, border-color .15s; }
.lr-start-choice:hover { background: var(--pm-chip-bg); }
.lr-start-choice--selected { border-color: var(--pm-accent); background: color-mix(in oklab, var(--pm-accent) 9%, var(--pm-surface-card)); }
.lr-start-choice:focus-within { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.lr-start-choice input { accent-color: var(--pm-accent); flex: none; width: 16px; height: 16px; }
.lr-start-choice span { display: flex; flex-direction: column; gap: 4px; }
.lr-start-choice b { font-size: 13px; font-weight: 600; }
.lr-start-choice small { font-size: 11.5px; line-height: 1.4; color: var(--pm-text-muted); }
.lr-start-footer { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--pm-border); }
.lr-start-footer > span { font-size: 11px; color: var(--pm-text-muted); }
.lr-start-submit { display: flex; justify-content: center; align-items: center; gap: 9px; width: 100%; min-height: 40px; padding: 9px 14px; border: 0; border-radius: 10px; background: var(--pm-accent); color: var(--pm-on-accent); font: 600 13px/1.3 var(--pm-font-sans); cursor: pointer; }
.lr-start-submit:hover { filter: brightness(1.06); }
.lr-start-submit:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 3px; }

.lernraum-panel .lr-learn-exit-options { width: min(360px, calc(100vw - 40px)); padding: 20px; border-radius: 16px; }
.lr-exit-summary { margin-top: 18px; padding: 13px 14px; border: 1px solid var(--pm-border); border-radius: 10px; background: var(--pm-chip-bg); }
.lr-exit-remaining { display: block; font-size: 13px; font-weight: 600; }
.lernraum-panel .lr-exit-summary p { margin: 5px 0 0; color: var(--pm-text-muted); font-size: 12px; }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-actions { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--pm-border); gap: 9px; }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-actions button { flex: none; height: auto; min-height: 40px; padding: 10px 12px; border-radius: 10px; font-size: 13px; }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-cancel { flex: 1; background: var(--pm-accent); color: var(--pm-on-accent); }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-cancel:hover { filter: brightness(1.06); }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-confirm { border: 0; background: transparent; color: var(--pm-text-muted); font-weight: 500; }
.lernraum-panel .lr-learn-exit-options .lr-learn-exit-confirm:hover { background: var(--pm-chip-bg); color: var(--pm-danger, #d85d55); }
</style>
