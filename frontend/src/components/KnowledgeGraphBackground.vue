<template>
  <canvas ref="canvasRef" class="kg-canvas" aria-hidden="true" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

/**
 * Animierter "Wissensgraph"-Hintergrund: vernetzte, langsam treibende Knoten,
 * die untereinander und zum Mauszeiger Verbindungslinien ziehen. Einige
 * Knoten pulsieren als hervorgehobene "Konzepte". Rein dekorativ.
 */

const props = defineProps({
  // Brand-Akzentfarben (RGB-Tripel). Reihenfolge = Gewichtung.
  palette: {
    type: Array,
    default: () => [
      [59, 130, 246], // primary blue
      [45, 212, 191], // teal accent
      [129, 140, 248] // indigo accent
    ]
  },
  // Von aussen anhalten (z. B. Tab versteckt, Glass-Look aus).
  paused: {
    type: Boolean,
    default: false
  },
  // Knotendichte (1 = Standard). Auf schwachen/mobilen Geraeten reduzieren.
  density: {
    type: Number,
    default: 1
  },
  // Maus-Interaktion (Anziehung + Linien zum Cursor).
  interactive: {
    type: Boolean,
    default: true
  }
});

const canvasRef = ref(null);

let ctx = null;
let rafId = 0;
let width = 0;
let height = 0;
let dpr = 1;
let nodes = [];
let resizeObserver = null;
let active = false;

const pointer = { x: -9999, y: -9999, active: false };

// Verbindungsdistanzen (in CSS-Pixeln).
const LINK_DIST = 150;
const POINTER_DIST = 220;

const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function buildNodes() {
  // Knotenanzahl an die Flaeche koppeln, aber begrenzen; density skaliert.
  const base = Math.min(150, Math.max(40, Math.round((width * height) / 11000)));
  const target = Math.max(12, Math.round(base * props.density));
  nodes = [];
  for (let i = 0; i < target; i += 1) {
    const highlighted = Math.random() < 0.16;
    nodes.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.28,
      vy: (Math.random() - 0.5) * 0.28,
      radius: highlighted ? 2.4 + Math.random() * 1.6 : 1 + Math.random() * 1.2,
      color: pick(props.palette),
      highlighted,
      phase: Math.random() * Math.PI * 2,
      pulseSpeed: 0.6 + Math.random() * 0.9
    });
  }
}

function resize() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  width = rect.width;
  height = rect.height;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  buildNodes();
}

function rgba(color, alpha) {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
}

let lastTime = 0;

function frame(time) {
  const dt = Math.min(2, (time - lastTime) / 16.67 || 1);
  lastTime = time;

  ctx.clearRect(0, 0, width, height);

  // Knoten bewegen + an Raendern weich wenden.
  for (const n of nodes) {
    n.x += n.vx * dt;
    n.y += n.vy * dt;
    if (n.x < -20) n.x = width + 20;
    else if (n.x > width + 20) n.x = -20;
    if (n.y < -20) n.y = height + 20;
    else if (n.y > height + 20) n.y = -20;

    // Sanfte Anziehung Richtung Mauszeiger.
    if (props.interactive && pointer.active) {
      const dx = pointer.x - n.x;
      const dy = pointer.y - n.y;
      const dist = Math.hypot(dx, dy);
      if (dist < POINTER_DIST && dist > 1) {
        const force = (1 - dist / POINTER_DIST) * 0.04;
        n.x += (dx / dist) * force * dt;
        n.y += (dy / dist) * force * dt;
      }
    }
  }

  // Verbindungslinien zwischen Knoten.
  ctx.lineWidth = 1;
  for (let i = 0; i < nodes.length; i += 1) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j += 1) {
      const b = nodes[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = dx * dx + dy * dy;
      if (distSq < LINK_DIST * LINK_DIST) {
        const dist = Math.sqrt(distSq);
        const alpha = (1 - dist / LINK_DIST) * 0.32;
        ctx.strokeStyle = rgba(a.color, alpha);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
  }

  // Linien Knoten -> Mauszeiger.
  if (props.interactive && pointer.active) {
    for (const n of nodes) {
      const dx = pointer.x - n.x;
      const dy = pointer.y - n.y;
      const dist = Math.hypot(dx, dy);
      if (dist < POINTER_DIST) {
        const alpha = (1 - dist / POINTER_DIST) * 0.5;
        ctx.strokeStyle = rgba(n.color, alpha);
        ctx.lineWidth = 1.1;
        ctx.beginPath();
        ctx.moveTo(n.x, n.y);
        ctx.lineTo(pointer.x, pointer.y);
        ctx.stroke();
      }
    }
  }

  // Knoten zeichnen (mit Glow).
  for (const n of nodes) {
    let r = n.radius;
    let glow = n.highlighted ? 14 : 6;
    if (n.highlighted) {
      const pulse = 0.5 + 0.5 * Math.sin(time * 0.001 * n.pulseSpeed + n.phase);
      r = n.radius * (0.85 + pulse * 0.5);
      glow = 10 + pulse * 14;
    }
    ctx.shadowBlur = glow;
    ctx.shadowColor = rgba(n.color, 0.9);
    ctx.fillStyle = rgba(n.color, n.highlighted ? 0.95 : 0.7);
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.shadowBlur = 0;

  if (active) rafId = requestAnimationFrame(frame);
}

function shouldAnimate() {
  return !prefersReducedMotion && !props.paused && !document.hidden;
}

function start() {
  if (active) return;
  active = true;
  lastTime = performance.now();
  rafId = requestAnimationFrame(frame);
}

function stop() {
  active = false;
  cancelAnimationFrame(rafId);
}

function syncRunning() {
  if (shouldAnimate()) start();
  else stop();
}

function drawStatic() {
  // Ein einzelnes ruhiges Bild fuer prefers-reduced-motion.
  ctx.clearRect(0, 0, width, height);
  ctx.lineWidth = 1;
  for (let i = 0; i < nodes.length; i += 1) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j += 1) {
      const b = nodes[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distSq = dx * dx + dy * dy;
      if (distSq < LINK_DIST * LINK_DIST) {
        const dist = Math.sqrt(distSq);
        ctx.strokeStyle = rgba(a.color, (1 - dist / LINK_DIST) * 0.28);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
  }
  for (const n of nodes) {
    ctx.shadowBlur = n.highlighted ? 14 : 6;
    ctx.shadowColor = rgba(n.color, 0.9);
    ctx.fillStyle = rgba(n.color, n.highlighted ? 0.95 : 0.7);
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.shadowBlur = 0;
}

function onPointerMove(e) {
  const rect = canvasRef.value.getBoundingClientRect();
  pointer.x = e.clientX - rect.left;
  pointer.y = e.clientY - rect.top;
  pointer.active = true;
}

function onPointerLeave() {
  pointer.active = false;
  pointer.x = -9999;
  pointer.y = -9999;
}

function onVisibilityChange() {
  // Bei verstecktem Tab anhalten (CPU/Akku schonen), sonst fortsetzen.
  syncRunning();
}

// Pause-Prop von aussen (Glass-Look aus / Animations-Schalter) live nachfuehren.
watch(() => props.paused, () => syncRunning());

onMounted(() => {
  const canvas = canvasRef.value;
  ctx = canvas.getContext('2d');
  resize();

  if (prefersReducedMotion) {
    drawStatic();
    return;
  }

  resizeObserver = new ResizeObserver(() => resize());
  resizeObserver.observe(canvas);

  if (props.interactive) {
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerleave', onPointerLeave, { passive: true });
  }
  document.addEventListener('visibilitychange', onVisibilityChange);

  syncRunning();
});

onBeforeUnmount(() => {
  stop();
  if (resizeObserver) resizeObserver.disconnect();
  window.removeEventListener('pointermove', onPointerMove);
  window.removeEventListener('pointerleave', onPointerLeave);
  document.removeEventListener('visibilitychange', onVisibilityChange);
});
</script>

<style scoped>
.kg-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
</style>
