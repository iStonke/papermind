<!--
  RecentImportsWidget — zuletzt importierte Dokumente als Thumbnail-Kacheln.
  Klick öffnet das Dokument, „Alle anzeigen" springt in die Import-Ansicht.
-->
<template>
  <div class="dash-recent">
    <div class="dash-recent__head">
      <h2 class="dash-card__title">Zuletzt importiert</h2>
      <button type="button" class="dash-link" @click="actions.showAllRecent()">Alle anzeigen</button>
    </div>
    <div v-if="overview.recent.length" class="dash-recent__grid">
      <button
        v-for="doc in overview.recent"
        :key="doc.id"
        type="button"
        class="dash-card dash-doc"
        @click="actions.openDocument(doc.id)"
      >
        <span class="dash-doc__thumb">
          <img
            v-if="!thumbError[doc.id]"
            :src="thumbUrl(doc.id)"
            alt=""
            loading="lazy"
            @error="thumbError[doc.id] = true"
          />
          <v-icon v-else size="20">mdi-file-outline</v-icon>
        </span>
        <span class="dash-doc__text">
          <span class="dash-doc__title">{{ doc.title }}</span>
          <span class="dash-doc__corr">{{ doc.correspondent || 'Ohne Korrespondent' }}</span>
          <span class="dash-doc__date">{{ formatDate(doc.date) }}</span>
        </span>
      </button>
    </div>
    <p v-else class="dash-card__empty">Noch keine Dokumente vorhanden.</p>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { documentThumbnailUrl } from '../../api/documents.js';
import { formatDate, useDashboardActions } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);
const actions = useDashboardActions();

const thumbError = reactive({});
const thumbUrl = (id) => documentThumbnailUrl(id);
</script>
