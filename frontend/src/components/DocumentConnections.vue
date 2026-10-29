<template>
  <RelatedDocumentsSection :document-id="documentId" :match-key="matchKey" :in-trash="inTrash" :show-suffix="showSuffix"
    :enabled="active" @open-document="$emit('open-document', $event)" />
  <DocumentNotesSection :document-id="documentId" :reload-key="reloadKey" :creating="creating"
    @open-note="$emit('open-note', $event)" @new-note="$emit('new-note')" />
  <DocumentLearnHighlightsSection show-empty :document-id="documentId" :reload-key="reloadKey"
    @open-highlight="$emit('open-highlight', $event)" />
</template>
<script setup>
import RelatedDocumentsSection from './RelatedDocumentsSection.vue';
import DocumentNotesSection from './notes/DocumentNotesSection.vue';
import DocumentLearnHighlightsSection from './notes/DocumentLearnHighlightsSection.vue';
defineProps({ documentId: String, matchKey: String, active: Boolean, inTrash: Boolean, showSuffix: Boolean, reloadKey: Number, creating: Boolean });
defineEmits(['open-document', 'open-note', 'new-note', 'open-highlight']);
</script>
