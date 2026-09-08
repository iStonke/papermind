<!--
  OpenTasksWidget — offene Aufgaben (taskItem) über alle Notizen.

  - Die Checkbox hakt die Aufgabe DIREKT in der Notiz ab (POST …/tasks/toggle):
    der erledigt-Status landet im ProseMirror-JSON, die Notiz zeigt denselben
    Zustand. Erledigte Aufgaben verschwinden danach aus dieser Liste.
  - Ein Klick auf den Aufgabentext springt zur Notiz (pm-note:navigate, auf das
    DocumentsWorkspace hört). Das Abhaken allein springt NICHT (getrennte
    Interaktionsflächen: Checkbox vs. Textbereich).

  Neutrale Checklisten (checkListItem) erscheinen hier bewusst NICHT –
  siehe note_task/extract_note_tasks.
-->
<template>
  <article class="dash-card dash-tasks">
    <div class="dash-tasks__head">
      <h2 class="dash-card__title">Offene Aufgaben</h2>
      <span v-if="openCount" class="dash-tasks__count">{{ formatInt(openCount) }}</span>
    </div>
    <ul v-if="visibleTasks.length" class="dash-tasks__list">
      <li v-for="task in visibleTasks" :key="taskKey(task)">
        <div class="dash-tasks__row" :class="{ 'is-overdue': task.overdue }">
          <input
            type="checkbox"
            class="dash-tasks__check"
            :aria-label="`Aufgabe „${task.text}“ als erledigt markieren`"
            :disabled="pending.has(taskKey(task))"
            @change="markDone(task)"
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
    </ul>
    <p v-else class="dash-card__empty">Keine offenen Aufgaben in deinen Notizen.</p>
  </article>
</template>

<script setup>
import { computed, reactive } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { toggleNoteTask } from '../../api/notes.js';
import { formatDate, formatInt } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);

// Optimistisch abgehakte Aufgaben, die noch aus der Liste laufen sollen, bevor
// die Übersicht neu geladen ist. `pending` sperrt zusätzlich die Checkbox.
const removed = reactive(new Set());
const pending = reactive(new Set());

const taskKey = (task) => `${task.note_id}:${task.position}`;

const visibleTasks = computed(() =>
  (overview.value.open_tasks || []).filter((t) => !removed.has(taskKey(t)))
);
const openCount = computed(() =>
  Math.max(0, Number(overview.value.open_tasks_total || 0) - removed.size)
);

// Öffnet die zur Aufgabe gehörende Notiz im Notizbereich (bestehender Kanal,
// den auch Notiz-Chips/Rückverweise nutzen; DocumentsWorkspace hört darauf).
function openTaskNote(noteId) {
  if (!noteId) return;
  window.dispatchEvent(new CustomEvent('pm-note:navigate', { detail: { type: 'note', id: noteId } }));
}

async function markDone(task) {
  const key = taskKey(task);
  if (pending.has(key)) return;
  pending.add(key);
  removed.add(key); // optimistisch ausblenden
  try {
    await toggleNoteTask(task.note_id, task.position, true);
    // Übersicht neu laden, damit note_task/Zähler serverseitig stimmen; die
    // erledigte Aufgabe fällt dabei ohnehin aus open_tasks heraus.
    await dashboardStore.fetchOverview();
    removed.delete(key); // Serverstand ist jetzt maßgeblich
  } catch (err) {
    removed.delete(key); // Fehlschlag: Aufgabe wieder einblenden
    console.warn('Aufgabe konnte nicht abgehakt werden:', err);
  } finally {
    pending.delete(key);
  }
}
</script>
