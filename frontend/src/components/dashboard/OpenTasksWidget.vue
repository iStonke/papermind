<!--
  OpenTasksWidget — offene Aufgaben (taskItem) über alle Notizen. Klick öffnet
  die zugehörige Notiz im Notizbereich über den bestehenden Navigationskanal
  (pm-note:navigate), auf den DocumentsWorkspace hört. Neutrale Checklisten
  (checkListItem) erscheinen hier bewusst NICHT – siehe note_task/extract_note_tasks.
-->
<template>
  <article class="dash-card dash-tasks">
    <div class="dash-tasks__head">
      <h2 class="dash-card__title">Offene Aufgaben</h2>
      <span v-if="overview.open_tasks_total" class="dash-tasks__count">{{ formatInt(overview.open_tasks_total) }}</span>
    </div>
    <ul v-if="overview.open_tasks.length" class="dash-tasks__list">
      <li v-for="(task, i) in overview.open_tasks" :key="`${task.note_id}-${i}`">
        <button
          type="button"
          class="dash-tasks__row"
          :class="{ 'is-overdue': task.overdue }"
          @click="openTaskNote(task.note_id)"
        >
          <v-icon size="16" class="dash-tasks__check">mdi-checkbox-blank-circle-outline</v-icon>
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
      </li>
    </ul>
    <p v-else class="dash-card__empty">Keine offenen Aufgaben in deinen Notizen.</p>
  </article>
</template>

<script setup>
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatDate, formatInt } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);

// Öffnet die zur Aufgabe gehörende Notiz im Notizbereich (bestehender Kanal,
// den auch Notiz-Chips/Rückverweise nutzen; DocumentsWorkspace hört darauf).
function openTaskNote(noteId) {
  if (!noteId) return;
  window.dispatchEvent(new CustomEvent('pm-note:navigate', { detail: { type: 'note', id: noteId } }));
}
</script>
