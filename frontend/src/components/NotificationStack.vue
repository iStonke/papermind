<template>
  <div class="notification-stack" aria-live="polite" aria-atomic="false">
    <transition-group name="notification-card" tag="div" class="notification-stack__list">
      <article
        v-for="notification in visibleNotifications"
        :key="notification.id"
        class="notification-card"
        :class="`notification-card--${notification.type}`"
        @mouseenter="pauseNotificationTimer(notification.id)"
        @mouseleave="resumeNotificationTimer(notification.id)"
      >
        <div class="notification-card__accent" aria-hidden="true" />
        <v-icon :icon="typeIcon(notification.type)" size="18" class="notification-card__icon" />
        <div class="notification-card__content">
          <div v-if="notification.title" class="notification-card__title">{{ notification.title }}</div>
          <div class="notification-card__message">{{ notification.message }}</div>
        </div>
        <v-btn
          icon="mdi-close"
          size="x-small"
          density="comfortable"
          variant="text"
          aria-label="Meldung schließen"
          class="notification-card__close"
          @click="dismissNotification(notification.id)"
        />
      </article>
    </transition-group>
  </div>
</template>

<script setup>
import { useNotifications } from '../stores/notifications';

const { visibleNotifications, dismissNotification, pauseNotificationTimer, resumeNotificationTimer } = useNotifications();

function typeIcon(type) {
  switch (type) {
    case 'success':
      return 'mdi-check-circle-outline';
    case 'warning':
      return 'mdi-alert-circle-outline';
    case 'error':
      return 'mdi-alert-circle-outline';
    default:
      return 'mdi-information-outline';
  }
}
</script>

<style scoped>
.notification-stack {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2600;
  pointer-events: none;
}

.notification-stack__list {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.notification-card {
  pointer-events: auto;
  width: min(460px, calc(100vw - 24px));
  display: grid;
  grid-template-columns: 3px auto 1fr auto;
  align-items: center;
  column-gap: 10px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  background: rgba(var(--v-theme-surface), 0.95);
  box-shadow: 0 12px 26px rgba(0, 0, 0, 0.15);
  padding: 9px 10px 9px 0;
}

.notification-card__accent {
  align-self: stretch;
  border-radius: 999px;
  background: rgba(var(--v-theme-primary), 0.42);
}

.notification-card__icon {
  opacity: 0.9;
}

.notification-card__content {
  min-width: 0;
}

.notification-card__title {
  font-size: 0.81rem;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 2px;
}

.notification-card__message {
  font-size: 0.84rem;
  line-height: 1.35;
  word-break: break-word;
}

.notification-card__close {
  opacity: 0.74;
}

.notification-card--success .notification-card__accent {
  background: rgba(56, 142, 60, 0.72);
}

.notification-card--success .notification-card__icon {
  color: rgb(46, 125, 50);
}

.notification-card--info .notification-card__accent {
  background: rgba(var(--pm-indigo-rgb, 48, 57, 112), 0.62);
}

.notification-card--info .notification-card__icon {
  color: rgba(var(--pm-indigo-rgb, 48, 57, 112), 0.95);
}

.notification-card--warning .notification-card__accent {
  background: rgba(245, 124, 0, 0.72);
}

.notification-card--warning .notification-card__icon {
  color: rgb(166, 94, 12);
}

.notification-card--error .notification-card__accent {
  background: rgba(211, 47, 47, 0.72);
}

.notification-card--error .notification-card__icon {
  color: rgb(166, 45, 45);
}

.notification-card-enter-active,
.notification-card-leave-active {
  transition: transform 0.22s ease-out, opacity 0.22s ease-out;
}

.notification-card-enter-from,
.notification-card-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

@media (max-width: 900px) {
  .notification-stack {
    right: 12px;
    left: 12px;
    bottom: 14px;
  }

  .notification-stack__list {
    align-items: stretch;
  }

  .notification-card {
    width: 100%;
  }
}
</style>
