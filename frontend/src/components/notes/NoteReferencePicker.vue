<template>
  <div
    v-if="editor && picker.open && filteredPicker.length"
    class="pm-float pm-slash pm-picker"
    :style="picker.style"
    role="listbox"
    :aria-label="pickerHint()"
  >
    <div class="pm-slash__hint">{{ pickerHint() }}</div>
    <button
      v-for="(it, i) in filteredPicker"
      :key="it.type + ':' + it.id"
      type="button"
      class="pm-slash__item"
      :class="{ 'is-active': i === picker.index }"
      role="option"
      :aria-selected="i === picker.index"
      @mousemove="picker.index = i"
      @mousedown.prevent="pickItem(it)"
    >
      <span class="pm-slash__chip">{{ pickerChip(it) }}</span>
      <span class="pm-slash__text">
        <span class="pm-slash__label">{{ it.label }}</span>
        <span class="pm-slash__desc">{{ it.hint }}</span>
      </span>
    </button>
  </div>
</template>

<script setup>
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  picker,
  filteredPicker,
  pickerHint,
  pickerChip,
  pickItem,
} = props.controller;
</script>

<style scoped src="./styles/slashMenu.css"></style>
<style scoped src="./styles/floating.css"></style>
