<template>
  <form
    v-if="editor && linkEditor.open"
    class="pm-float pm-link-editor"
    :style="linkEditor.style"
    aria-label="Hyperlink bearbeiten"
    @submit.prevent="applyLink"
    @mousedown.stop
  >
    <div class="pm-link-editor__head">
      <span><v-icon size="17">mdi-link-variant</v-icon> Hyperlink</span>
      <kbd>⌘K</kbd>
    </div>
    <div class="pm-link-editor__input-row">
      <input
        ref="linkInputEl"
        v-model="linkEditor.href"
        type="text"
        inputmode="url"
        autocomplete="url"
        spellcheck="false"
        placeholder="https://… oder name@domain.de"
        :aria-invalid="linkEditor.error ? 'true' : undefined"
        @input="linkEditor.error = ''; linkEditor.copied = false"
        @keydown.esc.prevent="closeLinkEditor(true)"
      />
      <button type="submit" class="pm-link-editor__save" aria-label="Hyperlink übernehmen">
        <v-icon size="18">mdi-check</v-icon>
      </button>
    </div>
    <div v-if="linkEditor.error" class="pm-link-editor__error" role="alert">{{ linkEditor.error }}</div>
    <div v-if="linkEditor.existing" class="pm-link-editor__actions">
      <button type="button" @click="openLinkTarget">
        <v-icon size="17">mdi-open-in-new</v-icon><span>Öffnen</span>
      </button>
      <button type="button" @click="copyLinkTarget">
        <v-icon size="17">mdi-content-copy</v-icon><span>{{ linkEditor.copied ? 'Kopiert' : 'Kopieren' }}</span>
      </button>
      <button type="button" class="is-danger" @click="removeLink">
        <v-icon size="17">mdi-link-off</v-icon><span>Entfernen</span>
      </button>
    </div>
  </form>
</template>

<script setup>
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  linkEditor,
  linkInputEl,
  closeLinkEditor,
  applyLink,
  removeLink,
  openLinkTarget,
  copyLinkTarget,
} = props.controller;
</script>

<style scoped src="./styles/linkMenu.css"></style>
<style scoped src="./styles/floating.css"></style>
