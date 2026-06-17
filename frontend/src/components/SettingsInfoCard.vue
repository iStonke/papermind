<template>
  <div class="settings-info-card">
    <div class="settings-info-card__badge">
      <slot name="badge">
        <v-icon size="34">{{ icon }}</v-icon>
      </slot>
    </div>
    <div class="settings-info-card__text">
      <div class="settings-info-card__title">{{ title }}</div>
      <div v-if="subtitle || $slots.subtitle" class="settings-info-card__sub">
        <slot name="subtitle">{{ subtitle }}</slot>
      </div>
    </div>
    <div v-if="$slots.actions" class="settings-info-card__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
/**
 * Einheitliche Info-/Hero-Karte für die Einstellungs-Bereiche
 * (Backup, Bedienung, System …): Icon-Badge + Titel + Subtitle, optional
 * mit Aktion rechts (#actions). Gleicher Abstand oben und unten.
 */
defineProps({
  icon: { type: String, default: '' },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
});
</script>

<style scoped>
.settings-info-card {
  /* Bleibt beim Scrollen oben kleben; der Inhalt läuft darunter durch. */
  position: sticky;
  top: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 14px;
  /* Gleicher Ruhe-Abstand oben/unten: oben = Panel-Top-Padding (12px,
     Badge sitzt am Kartenrand), unten = margin-bottom (12px). */
  margin: 0 0 12px;
  padding-bottom: 14px;
  /* Muss zur angehobenen Dialogfläche passen (BaseDialog nutzt surface-2). */
  background: rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  /* Deckt den Panel-Innenabstand oberhalb der Karte ab, damit beim Scrollen
     kein Inhalt darüber durchscheint. */
  box-shadow: 0 -16px 0 rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
}
.settings-info-card__badge {
  width: 48px;
  height: 48px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
  flex-shrink: 0;
}
.settings-info-card__text {
  flex: 1;
  min-width: 0;
}
.settings-info-card__title {
  font-size: 1.05rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.settings-info-card__sub {
  font-size: 0.8rem;
  opacity: 0.7;
}
.settings-info-card__actions {
  flex-shrink: 0;
}
</style>
