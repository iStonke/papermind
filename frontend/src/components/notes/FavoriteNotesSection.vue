<!--
  FavoriteNotesSection — zeigt favorisierte Notizen als eigenen Abschnitt im
  globalen Favoriten-Bereich (über den favorisierten Dokumenten). Klick öffnet
  die Notiz im Notizbereich; der Stern entfernt sie aus den Favoriten.
-->
<template>
  <section v-if="favoriteNotes.length" class="fav-notes" aria-label="Favorisierte Notizen">
    <header class="fav-notes__head">
      <v-icon size="15" class="fav-notes__head-icon">mdi-note-text-outline</v-icon>
      <span class="fav-notes__title">Favoriten-Notizen</span>
      <span class="fav-notes__count">{{ favoriteNotes.length }}</span>
    </header>

    <ul class="fav-notes__list">
      <li
        v-for="note in favoriteNotes"
        :key="note.id"
        class="fav-notes__card"
        role="button"
        tabindex="0"
        @click="$emit('open-note', note.id)"
        @keydown.enter="$emit('open-note', note.id)"
      >
        <button
          type="button"
          class="fav-notes__star"
          :aria-label="`„${note.title?.trim() || 'Ohne Titel'}“ aus Favoriten entfernen`"
          title="Aus Favoriten entfernen"
          @click.stop="unfavorite(note)"
        >
          <v-icon size="16">mdi-star</v-icon>
        </button>
        <div class="fav-notes__card-title" :class="{ 'is-untitled': !note.title?.trim() }">
          {{ note.title?.trim() || 'Ohne Titel' }}
        </div>
        <p class="fav-notes__card-snippet">{{ note.preview?.trim() || 'Leer' }}</p>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, watch } from 'vue';
import { useNotesStore } from '../../stores/notes.js';

const props = defineProps({
  // Nur laden, wenn der Favoriten-Bereich aktiv ist (spart unnötige Abrufe).
  active: { type: Boolean, default: false },
});

defineEmits(['open-note']);

const notesStore = useNotesStore();
const favoriteNotes = computed(() => notesStore.favoriteNotes);

watch(
  () => props.active,
  (isActive) => {
    if (isActive) notesStore.fetchFavorites().catch(() => {});
  },
  { immediate: true },
);

async function unfavorite(note) {
  try {
    await notesStore.setFavorite(note.id, false);
  } catch {
    // Fehler bleibt still; der optimistische Zustand wird im Store zurückgerollt.
  }
}
</script>

<style scoped>
.fav-notes {
  flex: none;
  padding: 12px 16px 6px;
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
}
.fav-notes__head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.fav-notes__head-icon { color: var(--pm-star, #f5b301); }
.fav-notes__title {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pm-muted, #64748b);
}
.fav-notes__count {
  min-width: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-star, #f5b301) 18%, transparent);
  color: color-mix(in srgb, var(--pm-star, #f5b301) 82%, var(--pm-text, #0f172a));
  font-size: 0.68rem;
  font-weight: 700;
  text-align: center;
}
.fav-notes__list {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 8px;
  margin: 0;
  list-style: none;
  scrollbar-width: thin;
}
.fav-notes__card {
  position: relative;
  flex: 0 0 200px;
  max-width: 200px;
  min-height: 78px;
  padding: 9px 11px 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px;
  background: var(--pm-content-surface, #fff);
  box-shadow: 0 3px 10px rgba(27, 43, 48, 0.09);
  cursor: pointer;
  transition: box-shadow 130ms ease, border-color 130ms ease;
}
.fav-notes__card:hover {
  border-color: color-mix(in srgb, var(--pm-text, #1b2b30) 22%, var(--pm-divider, #d8dfe1));
  box-shadow: 0 4px 14px rgba(27, 43, 48, 0.12);
}
.fav-notes__star {
  position: absolute;
  top: 6px;
  right: 6px;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-star, #f5b301);
  cursor: pointer;
  opacity: 0.9;
  transition: opacity 120ms ease, background 120ms ease;
}
.fav-notes__star:hover { opacity: 1; background: color-mix(in srgb, var(--pm-star, #f5b301) 14%, transparent); }
.fav-notes__card-title {
  padding-right: 22px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--pm-text, #0e181b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fav-notes__card-title.is-untitled { color: var(--pm-muted, #8a969b); font-style: italic; font-weight: 500; }
.fav-notes__card-snippet {
  margin: 4px 0 0;
  font-size: 0.74rem;
  line-height: 1.35;
  color: var(--pm-muted, #64748b);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
