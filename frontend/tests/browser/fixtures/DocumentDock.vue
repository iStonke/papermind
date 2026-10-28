<template>
  <div :class="['papermind-app', `v-theme--${theme}`]" :data-theme="theme">
    <div class="dock-demo" :style="{ width: `${width}px`, height: `${height}px` }">
      <DocumentPreviewLayout class="panel-right__preview panel-right__preview--details-panel" show-drawer
        :is-open="open" :content-key="documentKey" :section-key="activeTab" body-id="demo-details">
        <template #viewer>
          <PdfPreview ref="preview" src="/__details-test.pdf" fit-page enable-reader />
        </template>
        <template #drawer-header>
          <div :class="['details-drawer__header', open ? 'details-drawer__header--expanded' : 'details-drawer__header--collapsed']" @click="open = !open">
            <div class="details-drawer__inner"><div class="details-command-bar">
              <div class="details-command-bar__left"><div class="details-drawer__title-row"><div class="details-drawer__title-wrap">
                <div class="details-drawer__eyebrow"><div class="details-drawer__eyebrow-inner"><MetadataSaveIndicator :saving="saving" :error="error" :document-key="documentKey" /></div></div>
                <div class="details-drawer__subtitle">{{ title }}</div>
                <div class="details-drawer__meta-line"><span>Seminar</span><span class="details-drawer__meta-dot" /><span>Nordlicht Akademie</span><span class="details-drawer__meta-dot" /><span>28.10.2026</span></div>
              </div></div></div>
              <div class="details-command-bar__right" @click.stop>
                <v-btn icon="mdi-dots-vertical" variant="text" size="small" class="details-action-btn details-action-btn--quiet" aria-label="Weitere Aktionen" />
                <v-btn icon="mdi-chevron-up" variant="text" size="small" class="details-action-btn details-action-btn--quiet details-chevron-btn" :class="{ 'details-chevron-btn--expanded': open }" aria-label="Dokumentdetails umschalten" :aria-expanded="open" aria-controls="demo-details" @click="open = !open" />
              </div>
            </div></div>
          </div>
        </template>
        <template #drawer-tabs><DocumentDetailsTabs :tabs="tabs" :active-tab="activeTab" :is-open="open" panel-id="demo-details" @select="selectTab" /></template>
        <template #drawer-body>
          <div class="details-drawer__body"><div class="details-drawer__inner pm-drawer-body">
            <section v-show="activeTab === 'metadata'" id="demo-details-metadata" role="tabpanel" aria-labelledby="demo-details-tab-metadata" class="details-tab-panel" tabindex="0">
            <DocumentMetadataFields :field-keys="['name', 'date', 'category', 'correspondent', 'tags']" :name="form.name" :date="form.date" :category="form.category" :correspondent="form.correspondent" :note="form.note"
              :categories="['Seminar', 'Rechnung']" :correspondents="[{ title: 'Nordlicht Akademie', value: 'nordlicht' }]"
              @update:name="form.name = $event" @update:date="form.date = $event" @update:category="form.category = $event" @update:correspondent="form.correspondent = $event" @update:note="form.note = $event">
              <template #tags><div style="padding:8px 0"><v-chip size="small">Weiterbildung</v-chip> <v-chip size="small">Gestaltung</v-chip></div></template>
            </DocumentMetadataFields>
            </section>
            <section v-show="activeTab === 'related'" id="demo-details-related" role="tabpanel" aria-labelledby="demo-details-tab-related" class="details-tab-panel" tabindex="0">
              <RelatedDocumentsSection :document-id="documentKey" :match-key="String(matchRevision)" :enabled="open && activeTab === 'related'"
                @open-document="lastRelatedDocument = $event; documentKey = $event" />
            </section>
            <section v-show="activeTab === 'notes'" id="demo-details-notes" role="tabpanel" aria-labelledby="demo-details-tab-notes" class="details-tab-panel" tabindex="0">
              <DocumentMetadataFields :field-keys="['note']" :note="form.note" @update:note="form.note = $event" />
              <DocumentNotesSection :document-id="documentKey" :reload-key="notesRevision" />
            </section>
            <section v-show="activeTab === 'highlights'" id="demo-details-highlights" role="tabpanel" aria-labelledby="demo-details-tab-highlights" class="details-tab-panel" tabindex="0">
              <DocumentLearnHighlightsSection show-empty :document-id="documentKey" />
            </section>
            <section v-show="activeTab === 'retention'" id="demo-details-retention" role="tabpanel" aria-labelledby="demo-details-tab-retention" class="details-tab-panel" tabindex="0">
              <div class="details-drawer__section-heading">Aufbewahrung</div>
              <RetentionStatusBar embedded />
            </section>
          </div></div>
        </template>
      </DocumentPreviewLayout>
    </div>
  </div>
</template>
<script setup>
import { reactive, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import DocumentPreviewLayout from '../../../src/components/DocumentPreviewLayout.vue';
import DocumentMetadataFields from '../../../src/components/DocumentMetadataFields.vue';
import MetadataSaveIndicator from '../../../src/components/MetadataSaveIndicator.vue';
import PdfPreview from '../../../src/components/PdfPreview.vue';
import DocumentDetailsTabs from '../../../src/components/DocumentDetailsTabs.vue';
import RelatedDocumentsSection from '../../../src/components/RelatedDocumentsSection.vue';
import DocumentNotesSection from '../../../src/components/notes/DocumentNotesSection.vue';
import DocumentLearnHighlightsSection from '../../../src/components/notes/DocumentLearnHighlightsSection.vue';
import RetentionStatusBar from '../../../src/components/RetentionStatusBar.vue';
const preview = ref(null);
const activeTab = ref('metadata'), notesRevision = ref(0), matchRevision = ref(0), lastRelatedDocument = ref('');
const tabs = [{ id: 'metadata', label: 'Metadaten' }, { id: 'related', label: 'Ähnliche Dokumente' }, { id: 'notes', label: 'Notizen' }, { id: 'highlights', label: 'Lernmarkierungen' }, { id: 'retention', label: 'Aufbewahrung' }];
function selectTab(id) { activeTab.value = id; preview.value?.resetZoom(); open.value = true; }
const open = ref(false), saving = ref(false), error = ref(false);
const documentKey = ref('document-a'), title = ref('Teilnahmebestätigung · Gestaltungsseminar');
const theme = ref('dark'), width = ref(850), height = ref(720);
const activeTheme = useTheme();
watch(theme, value => { activeTheme.global.name.value = value; });
const form = reactive({ name: 'Teilnahmebestätigung · Gestaltungsseminar', date: '28.10.2026', category: 'Seminar', correspondent: 'nordlicht', note: 'Unterlagen für die nächste Weiterbildung aufbewahren.' });
watch(open, value => { if (value) preview.value?.resetZoom(); });
defineExpose({ activeTab, notesRevision, matchRevision, lastRelatedDocument, preview, open, saving, error, documentKey, title, form, theme, width, height });
</script>
<style scoped>
.papermind-app { min-height:100vh; padding:36px; background:var(--pm-app-bg, #182326); color:var(--pm-text); font-family:Arial,sans-serif; }
.dock-demo { --details-header-title-size:1.18rem; max-width:100%; margin:auto; border-radius:18px; overflow:hidden; border:1px solid var(--pm-divider); }
</style>
