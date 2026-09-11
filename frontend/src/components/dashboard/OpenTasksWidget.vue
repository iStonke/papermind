<!--
  OpenTasksWidget — Aufgaben (taskItem) über alle Notizen.

  - Die Checkbox hakt die Aufgabe DIREKT in der Notiz ab/auf (POST …/tasks/toggle):
    der Status landet im ProseMirror-JSON, die Notiz zeigt denselben Zustand.
  - Erledigte Aufgaben verschwinden NICHT, sondern bleiben durchgestrichen und
    wandern (animiert) nach unten. Es bleiben höchstens 5 erledigte bestehen
    (ältere fallen weg); der Server liefert sie entsprechend gekappt.
  - Ein Klick auf den Aufgabentext springt zur Notiz (pm-note:navigate). Das
    Abhaken allein springt NICHT (getrennte Flächen: Checkbox vs. Textbereich).

  Neutrale Checklisten (checkListItem) erscheinen hier bewusst NICHT –
  siehe note_task/extract_note_tasks.
-->
<template>
  <article class="dash-card dash-tasks">
    <div class="dash-tasks__head">
      <h2 class="dash-card__title">Offene Aufgaben</h2>
      <span v-if="overview.open_tasks_total" class="dash-tasks__count">{{ formatInt(overview.open_tasks_total) }}</span>
    </div>
    <TransitionGroup
      v-if="displayTasks.length"
      tag="ul"
      name="dashtask"
      class="dash-tasks__list"
    >
      <li v-for="(task, index) in displayTasks" :key="taskKey(task)">
        <div
          class="dash-tasks__row"
          :class="{
            'is-overdue': task.overdue,
            'is-done': task.done,
            'is-intro': introActive,
          }"
          :style="introActive ? { animationDelay: `${index * 50}ms` } : undefined"
        >
          <input
            type="checkbox"
            class="dash-tasks__check"
            :checked="task.done"
            :aria-label="task.done ? `Aufgabe „${task.text}“ wieder offen setzen` : `Aufgabe „${task.text}“ als erledigt markieren`"
            :disabled="pending.has(taskKey(task))"
            @change="toggle(task)"
          />
          <button type="button" class="dash-tasks__open" @click="openTaskNote(task.note_id)">
            <span class="dash-tasks__text">{{ task.text }}</span>
            <span class="dash-tasks__aside">
              <span class="dash-tasks__note">{{ task.note_title }}</span>
              <span
                v-if="task.due_date"
                class="dash-tasks__due"
                :class="{ 'is-overdue': task.overdue }"
              >
                <v-icon size="12">mdi-calendar-clock</v-icon>
                {{ task.overdue ? 'überfällig · ' : '' }}{{ formatDate(task.due_date) }}
              </span>
            </span>
          </button>
        </div>
      </li>
    </TransitionGroup>
    <p v-else class="dash-card__empty">Keine offenen Aufgaben in deinen Notizen.</p>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { useNotesStore } from '../../stores/notes.js';
import { formatDate, formatInt } from './dashboardShared.js';
import './dashboard.css';

const MAX_DONE = 5;

const dashboardStore = useDashboardStore();
const notesStore = useNotesStore();
const { overview } = storeToRefs(dashboardStore);

// Läuft gerade ein Toggle-Request (sperrt die Checkbox); merkt sich zusätzlich
// die Reihenfolge des Abhakens (höher = zuletzt), damit die zuletzt erledigte
// Aufgabe ganz oben landet, auch vor dem Neuladen der Übersicht.
const pending = reactive(new Set());
const doneSeq = reactive(new Map());
let seqCounter = 0;
const introActive = ref(false);
let introStarted = false;
let introTimer = null;

const taskKey = (task) => `${task.note_id}:${task.position}`;

// Anzeige: offene oben (Serverreihenfolge); darunter die erledigten (zuletzt
// abgehakt zuerst, dann Serverreihenfolge), gekappt auf MAX_DONE.
const displayTasks = computed(() => {
  const list = (overview.value.open_tasks || []).map((t, i) => ({ t, i }));
  const open = list.filter((x) => !x.t.done);
  const done = list.filter((x) => x.t.done);
  done.sort((a, b) => {
    const sa = doneSeq.get(taskKey(a.t)) ?? -1;
    const sb = doneSeq.get(taskKey(b.t)) ?? -1;
    return sb - sa || a.i - b.i;
  });
  return [...open, ...done.slice(0, MAX_DONE)].map((x) => x.t);
});

// Pro Mount genau einmal starten. So wird die Staffelung beim Öffnen der
// Übersicht abgespielt, aber nicht bei späteren Store-Updates oder beim Abhaken.
watch(
  () => displayTasks.value.length,
  (count) => {
    if (!count || introStarted) return;
    introStarted = true;
    introActive.value = true;
    introTimer = window.setTimeout(() => {
      introActive.value = false;
      introTimer = null;
    }, 340 + Math.max(0, count - 1) * 50);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (introTimer !== null) window.clearTimeout(introTimer);
});

// Öffnet die zur Aufgabe gehörende Notiz im Notizbereich (bestehender Kanal,
// den auch Notiz-Chips/Rückverweise nutzen; DocumentsWorkspace hört darauf).
function openTaskNote(noteId) {
  if (!noteId) return;
  window.dispatchEvent(new CustomEvent('pm-note:navigate', { detail: { type: 'note', id: noteId } }));
}

async function toggle(task) {
  const key = taskKey(task);
  if (pending.has(key)) return;
  const newDone = !task.done;
  pending.add(key);
  // Optimistisch: Status am Store-Item setzen (löst die Umsortierung + Animation
  // aus). Beim Abhaken die Sequenz-Nr. erhöhen → oberste der Erledigten (direkt
  // unter den offenen Aufgaben).
  task.done = newDone;
  if (newDone) doneSeq.set(key, ++seqCounter);
  else doneSeq.delete(key);
  try {
    // Der Notes-Store übernimmt die vollständige Serverantwort. Damit sieht
    // der Editor beim anschließenden Öffnen sofort denselben Aufgabenstatus.
    await notesStore.toggleTask(task.note_id, task.position, newDone);
    // Serverstand nachziehen (Zähler, gekappte Erledigten-Liste, Wahrheit = Notiz).
    await dashboardStore.fetchOverview();
  } catch (err) {
    task.done = !newDone; // Fehlschlag: zurücksetzen
    if (newDone) doneSeq.delete(key);
    console.warn('Aufgabe konnte nicht umgeschaltet werden:', err);
  } finally {
    pending.delete(key);
  }
}
</script>
