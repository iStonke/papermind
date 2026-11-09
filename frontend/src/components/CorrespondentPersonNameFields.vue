<template>
  <div class="person-name-fields">
    <v-text-field
      v-model="firstName"
      label="Vorname"
      name="pm-correspondent-first-search"
      maxlength="120"
      variant="outlined"
      :density="density"
      :autofocus="autofocus"
      :disabled="disabled"
      hide-details
      autocomplete="off"
      @keydown.enter.prevent="emit('submit')"
    />
    <v-text-field
      v-model="lastName"
      label="Nachname"
      name="pm-correspondent-last-search"
      maxlength="120"
      variant="outlined"
      :density="density"
      :disabled="disabled"
      hide-details
      autocomplete="off"
      @keydown.enter.prevent="emit('submit')"
    />
  </div>
</template>

<script setup>
defineProps({
  density: { type: String, default: 'comfortable' },
  autofocus: Boolean,
  disabled: Boolean,
});
const firstName = defineModel('firstName', { type: String, required: true });
const lastName = defineModel('lastName', { type: String, required: true });
const emit = defineEmits(['submit']);
</script>

<style scoped>
.person-name-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 145px), 1fr));
  gap: 10px;
}
</style>
