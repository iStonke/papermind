<template>
  <v-progress-circular v-if="status === 'running'" indeterminate size="18" width="2" color="primary" class="activity-status-icon" />
  <v-icon v-else size="18" :color="color" class="activity-status-icon">{{ icon }}</v-icon>
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ status: String, autoEnded: Boolean });
const icon = computed(() => props.autoEnded ? 'mdi-timer-alert-outline' : ({
  queued: 'mdi-progress-clock', paused: 'mdi-pause-circle-outline',
  done: 'mdi-check-circle-outline', failed: 'mdi-alert-circle-outline',
  cancelled: 'mdi-stop',
}[props.status] || 'mdi-progress-clock'));
const color = computed(() => props.autoEnded ? 'warning' : ({ running: 'primary', queued: 'primary', done: 'success', failed: 'error' }[props.status]));
</script>
