<template>
  <RelatedDocumentsSection :document-id="documentId" :match-key="matchKey" :in-trash="inTrash" :show-suffix="showSuffix"
    :enabled="active" :preferences="preferences" @loading-change="pending.related = $event" @open-document="$emit('open-document', $event)" />
  <DocumentNotesSection :document-id="documentId" :reload-key="reloadKey" :creating="creating"
    @loading-change="pending.notes = $event" @open-note="$emit('open-note', $event)" @new-note="$emit('new-note')" />
  <DocumentLearnHighlightsSection show-empty :document-id="documentId" :reload-key="reloadKey"
    @loading-change="pending.highlights = $event" @open-highlight="$emit('open-highlight', $event)" />
</template>
<script setup>
import { reactive, watch } from 'vue';
import RelatedDocumentsSection from './RelatedDocumentsSection.vue';
import DocumentNotesSection from './notes/DocumentNotesSection.vue';
import DocumentLearnHighlightsSection from './notes/DocumentLearnHighlightsSection.vue';
const props = defineProps({ documentId: String, matchKey: String, active: Boolean, inTrash: Boolean, showSuffix: Boolean, reloadKey: Number, creating: Boolean, preferences: Object });
const emit = defineEmits(['open-document', 'open-note', 'new-note', 'open-highlight', 'loading-change']);
const pending = reactive({ related: true, notes: true, highlights: true });
watch(() => [props.documentId, Object.values(pending).some(Boolean)], ([documentId, loading]) => {
  emit('loading-change', { documentId, loading });
}, { immediate: true, flush: 'post' });
</script>
