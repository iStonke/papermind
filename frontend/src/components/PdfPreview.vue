<template>
  <div ref="rootEl" class="pdf-preview" role="region" aria-label="PDF Vorschau">
    <div v-if="errorMessage" class="pdf-preview__state pdf-preview__state--error">
      <v-icon size="20">mdi-file-alert-outline</v-icon>
      <div class="pdf-preview__state-title">Vorschau nicht verfügbar</div>
      <div class="pdf-preview__state-subtitle">{{ errorMessage }}</div>
    </div>

    <div v-else-if="isRendering && pages.length === 0" class="pdf-preview__state pdf-preview__state--loading">
      <v-progress-circular size="18" width="2" indeterminate />
      <span>Vorschau wird geladen…</span>
    </div>

    <div v-else class="pdf-preview__pages">
      <article v-for="page in pages" :key="page.page" class="pdf-preview__page" :data-page="page.page">
        <img :src="page.src" :alt="`Seite ${page.page}`" loading="lazy" draggable="false" />
      </article>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorkerSrc;

const props = defineProps({
  src: {
    type: String,
    default: ''
  },
  targetPage: {
    type: Number,
    default: null
  }
});

const emit = defineEmits(['loaded', 'failed']);

const rootEl = ref(null);
const pages = ref([]);
const isRendering = ref(false);
const errorMessage = ref('');

let renderEpoch = 0;
let activeTask = null;

function clearPreviewState() {
  pages.value = [];
  errorMessage.value = '';
}

function scrollToTargetPage() {
  const targetPage = Number(props.targetPage || 0);
  if (!targetPage || targetPage < 1 || pages.value.length === 0) {
    return;
  }

  const targetEl = rootEl.value?.querySelector?.(`.pdf-preview__page[data-page=\"${targetPage}\"]`);
  if (!targetEl) {
    return;
  }

  targetEl.scrollIntoView({
    behavior: 'smooth',
    block: 'start'
  });
}

async function renderPdf() {
  const currentSrc = String(props.src || '').trim();
  const epoch = ++renderEpoch;

  if (!currentSrc) {
    clearPreviewState();
    return;
  }

  if (activeTask) {
    activeTask.destroy();
    activeTask = null;
  }

  isRendering.value = true;
  errorMessage.value = '';

  try {
    await nextTick();
    const containerWidth = Math.max(340, (rootEl.value?.clientWidth || 900) - 28);

    activeTask = getDocument({
      url: currentSrc,
      withCredentials: false,
      disableStream: false,
      disableAutoFetch: false
    });

    const pdf = await activeTask.promise;
    if (epoch !== renderEpoch) {
      return;
    }

    const renderedPages = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      if (epoch !== renderEpoch) {
        return;
      }

      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1 });
      const scale = Math.max(0.5, Math.min(2.1, containerWidth / viewport.width));
      const renderViewport = page.getViewport({ scale });

      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) {
        throw new Error('Canvas context unavailable');
      }

      canvas.width = Math.floor(renderViewport.width);
      canvas.height = Math.floor(renderViewport.height);

      const task = page.render({
        canvasContext: context,
        viewport: renderViewport,
        background: 'rgb(255,255,255)'
      });
      await task.promise;

      renderedPages.push({
        page: pageNumber,
        src: canvas.toDataURL('image/webp', 0.92)
      });

      page.cleanup();
    }

    if (epoch !== renderEpoch) {
      return;
    }

    pages.value = renderedPages;
    scrollToTargetPage();
    emit('loaded');
  } catch (error) {
    if (epoch !== renderEpoch) {
      return;
    }
    console.warn('preview render failed', error);
    pages.value = [];
    errorMessage.value = 'Vorschau konnte nicht geladen werden.';
    emit('failed', error);
  } finally {
    if (epoch === renderEpoch) {
      isRendering.value = false;
    }
    if (activeTask) {
      activeTask.destroy();
      activeTask = null;
    }
  }
}

watch(
  () => props.src,
  () => {
    void renderPdf();
  },
  { immediate: true }
);

watch(
  () => props.targetPage,
  () => {
    nextTick(() => {
      scrollToTargetPage();
    });
  }
);

onBeforeUnmount(() => {
  renderEpoch += 1;
  if (activeTask) {
    activeTask.destroy();
    activeTask = null;
  }
});
</script>

<style scoped>
.pdf-preview {
  width: 100%;
  height: 100%;
  overflow: auto;
  background: var(--pm-pdf-stage-bg, rgb(var(--v-theme-surface)));
}

.pdf-preview__pages {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 14px;
}

.pdf-preview__page {
  width: 100%;
  display: flex;
  justify-content: center;
}

.pdf-preview__page img {
  width: min(100%, 980px);
  height: auto;
  display: block;
  border-radius: 8px;
}

.pdf-preview__state {
  min-height: 100%;
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  font-size: 0.86rem;
  opacity: 0.78;
  padding: 24px;
}

.pdf-preview__state--loading {
  flex-direction: row;
  gap: 10px;
}

.pdf-preview__state-title {
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.2;
}

.pdf-preview__state-subtitle {
  font-size: 0.82rem;
  opacity: 0.78;
  line-height: 1.35;
}
</style>
