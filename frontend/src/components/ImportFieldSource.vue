<template>
  <v-menu v-if="proposal" v-model="open" :close-on-content-click="false" location="bottom end" :max-width="320" transition="fade-transition">
    <template #activator="{ props: activator }">
      <span class="isd-source-target"><button v-bind="activator" type="button" class="isd-source-trigger" :disabled="disabled"
        :aria-label="`KI-Vorschlag für ${label} anzeigen`"><span class="pm-metadata-ai-chip v-chip"><v-icon size="11">mdi-creation</v-icon>KI<span class="isd-source-dot" aria-hidden="true" /></span></button></span>
    </template>
    <div class="isd-field-proposal" role="dialog" :aria-label="`KI-Vorschlag für ${label}`" @keydown.enter.stop>
      <strong>{{ label }}</strong><p>{{ text }}</p>
      <div class="isd-field-proposal__actions">
        <v-btn size="small" variant="text" :disabled="disabled" @click="emit('dismiss'); open = false">Verwerfen</v-btn>
        <v-btn size="small" variant="tonal" color="primary" :disabled="disabled" @click="emit('accept'); open = false">{{ create ? 'Korrespondenten anlegen' : 'Übernehmen' }}</v-btn>
      </div>
    </div>
  </v-menu>
  <v-chip v-else-if="source" class="pm-metadata-ai-chip" size="x-small" variant="flat" rounded="pill" :ripple="false" title="Von der KI erkannt" aria-label="Von der KI erkannt">
    <v-icon start size="11" aria-hidden="true">mdi-creation</v-icon>KI
  </v-chip>
</template>
<script setup>
import { ref } from 'vue';
defineProps({ source: [String, Boolean], proposal: Object, label: String, text: String, disabled: Boolean, create: Boolean });
const emit = defineEmits(['accept', 'dismiss']);
const open = ref(false);
</script>
<style scoped>
.isd-source-target { position:relative; display:inline-flex; justify-content:flex-end; height:20px; min-width:44px; }
.isd-source-trigger { display:inline-flex; align-items:center; padding:0; border:0; background:none; cursor:pointer; border-radius:14px; }
.isd-source-trigger:focus-visible { outline:2px solid rgb(var(--v-theme-primary)); outline-offset:3px; }
.pm-metadata-ai-chip.v-chip { height:18px; padding:0 6px; gap:3px; border:1px solid rgba(var(--v-theme-on-surface),.1); border-radius:999px; background:rgba(var(--v-theme-on-surface),.025); color:var(--pm-muted); font-size:10px; font-weight:500; }
.isd-source-dot { width:4px; height:4px; border-radius:50%; background:currentColor; }
.isd-field-proposal { padding:16px; background:rgb(var(--v-theme-surface)); color:rgb(var(--v-theme-on-surface)); border:1px solid var(--pm-divider); border-radius:12px; font-size:13px; }
.isd-field-proposal p { margin:8px 0 16px; white-space:pre-wrap; overflow-wrap:anywhere; max-height:240px; overflow:auto; }
.isd-field-proposal__actions { display:flex; justify-content:flex-end; gap:6px; flex-wrap:wrap; }
@media (any-pointer:coarse) { .isd-source-trigger { position:absolute; right:0; top:-12px; justify-content:center; min-width:44px; min-height:44px; } .isd-field-proposal__actions .v-btn { min-height:44px; } }
</style>
