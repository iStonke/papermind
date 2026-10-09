import { computed, onBeforeUnmount, ref } from 'vue';

// Node views are separate Vue trees, even when their DOM is nested.
export function useLectureCapture(props) {
  const version = ref(0);
  const refresh = () => { version.value++; };
  props.editor.on('transaction', refresh);
  onBeforeUnmount(() => props.editor.off('transaction', refresh));
  const slide = computed(() => {
    void version.value;
    try {
      const pos = props.getPos();
      if (!Number.isInteger(pos)) return null;
      const resolved = props.editor.state.doc.resolve(pos);
      for (let depth = resolved.depth; depth > 0; depth--) {
        const node = resolved.node(depth);
        if (node.type.name === 'lectureSlide') return node;
      }
    } catch { /* The node may have just been removed. */ }
    return null;
  });
  const capturedAt = computed(() => slide.value?.attrs.capturedAt || null);
  const slideNumber = computed(() => {
    void version.value;
    if (!slide.value) return null;
    let number = 0;
    let found = false;
    props.editor.state.doc.descendants(node => {
      if (found) return false;
      if (node.type.name === 'lectureSlide') {
        number++;
        if (node === slide.value) found = true;
        return false;
      }
    });
    return number;
  });
  const captureLabel = computed(() => capturedAt.value ? new Date(capturedAt.value).toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '');
  return { isLectureImage: computed(() => Boolean(slide.value)), capturedAt, captureLabel, slideNumber };
}
