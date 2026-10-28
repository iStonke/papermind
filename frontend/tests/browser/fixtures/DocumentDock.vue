<template>
  <div :class="['papermind-app', `v-theme--${theme}`]" :data-theme="theme">
    <div class="dock-demo" :style="{ width: `${width}px`, height: `${height}px` }">
      <DocumentPreviewLayout class="panel-right__preview panel-right__preview--card-drawer" show-drawer floating-card
        :is-open="open" :content-key="documentKey" body-id="demo-details" :style="{ '--preview-drawer-scrim-rgb': theme === 'dark' ? '26, 35, 38' : '255, 255, 255' }">
        <template #viewer>
          <div class="demo-paper"><small>NORDLICHT · WEITERBILDUNG</small><h1>Teilnahmebestätigung</h1><p>Workshop · Gestaltung und Kommunikation</p><hr /><p>Hiermit bestätigen wir die Teilnahme am Seminar.</p><div class="demo-lines" /></div>
        </template>
        <template #drawer-header>
          <div :class="['details-drawer__header', open ? 'details-drawer__header--expanded' : 'details-drawer__header--collapsed']" @click="open = !open">
            <div class="details-drawer__inner"><div class="details-command-bar">
              <div class="details-command-bar__left"><div class="details-drawer__title-row"><div class="details-drawer__title-wrap">
                <div class="details-drawer__eyebrow"><div class="details-drawer__eyebrow-inner"><span>Dokumentdetails</span><MetadataSaveIndicator :saving="saving" :error="error" :document-key="documentKey" /></div></div>
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
        <template #drawer-body>
          <div class="details-drawer__body"><div class="details-drawer__inner pm-drawer-body">
            <div class="details-drawer__section-heading">Metadaten</div>
            <DocumentMetadataFields :name="form.name" :date="form.date" :category="form.category" :correspondent="form.correspondent" :note="form.note"
              :categories="['Seminar', 'Rechnung']" :correspondents="[{ title: 'Nordlicht Akademie', value: 'nordlicht' }]"
              @update:name="form.name = $event" @update:date="form.date = $event" @update:category="form.category = $event" @update:correspondent="form.correspondent = $event" @update:note="form.note = $event">
              <template #tags><div style="padding:8px 0"><v-chip size="small">Weiterbildung</v-chip> <v-chip size="small">Gestaltung</v-chip></div></template>
            </DocumentMetadataFields>
            <div style="height:160px;padding-top:24px;color:var(--pm-muted)">Verknüpfte Notizen</div>
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
const open = ref(false), saving = ref(false), error = ref(false);
const documentKey = ref('document-a'), title = ref('Teilnahmebestätigung · Gestaltungsseminar');
const theme = ref('dark'), width = ref(850), height = ref(720);
const activeTheme = useTheme();
watch(theme, value => { activeTheme.global.name.value = value; });
const form = reactive({ name: 'Teilnahmebestätigung · Gestaltungsseminar', date: '28.10.2026', category: 'Seminar', correspondent: 'nordlicht', note: 'Unterlagen für die nächste Weiterbildung aufbewahren.' });
defineExpose({ open, saving, error, documentKey, title, form, theme, width, height });
</script>
<style scoped>
.papermind-app { min-height:100vh; padding:36px; background:var(--pm-app-bg, #182326); color:var(--pm-text); font-family:Arial,sans-serif; }
.dock-demo { --details-header-title-size:1.18rem; max-width:100%; margin:auto; border-radius:18px; overflow:hidden; border:1px solid var(--pm-divider); }
.demo-paper { width:75%; height:900px; flex-shrink:0; margin:48px auto; padding:50px; background:#fffefa; color:#303f44; box-shadow:0 5px 20px #0002; }
.demo-paper small { color:#647777; letter-spacing:2px; }
.demo-paper h1 { font-size:28px; margin-top:40px; }
.demo-paper p { font-size:13px; margin:24px 0; }
.demo-paper hr { border:0;border-top:1px solid #ccc; }
.demo-lines { margin-top:36px;height:180px;background:repeating-linear-gradient(transparent 0 20px,#dde3e2 20px 22px); }
</style>
