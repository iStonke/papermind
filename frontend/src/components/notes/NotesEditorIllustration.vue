<template>
  <div
    class="notes-editor-illustration"
    role="status"
    aria-label="Keine Notiz ausgewählt. Wähle eine Notiz aus der Liste, um den Editor zu öffnen."
  >
    <svg
      class="notes-editor-illustration__canvas"
      viewBox="0 0 560 360"
      fill="none"
      aria-hidden="true"
    >
      <g class="notes-editor-illustration__sketch">
        <path
          class="notes-editor-illustration__sheet-outline"
          d="M148 66C202 64 299 67 358 65C379 86 401 108 423 132C424 172 422 234 424 276C425 291 415 299 400 300C335 298 215 302 145 300C131 300 123 290 124 276C126 223 122 145 124 88C124 74 134 67 148 66Z"
        />
        <path
          class="notes-editor-illustration__sheet-echo"
          d="M149 68C207 66 302 69 357 67C377 87 400 109 421 133C422 178 420 233 422 275C423 288 413 297 399 298C328 296 218 300 146 298C134 298 126 289 127 276C129 218 125 144 127 89C127 76 136 69 149 68Z"
        />
        <path
          class="notes-editor-illustration__fold"
          d="M358 66C357 82 359 103 358 113C358 124 367 131 378 131C391 130 408 133 422 132"
        />

        <path class="notes-editor-illustration__title-line" d="M169 119C199 116 239 121 286 118" />
        <path class="notes-editor-illustration__text-line" d="M170 160C217 157 286 162 362 159" />
        <path class="notes-editor-illustration__text-line" d="M171 189C224 191 274 186 340 190" />
        <path class="notes-editor-illustration__text-line notes-editor-illustration__text-line--short" d="M170 218C201 215 243 220 284 217" />

        <path
          class="notes-editor-illustration__check-circle"
          d="M190 259C190 266 185 270 179 269C172 268 169 264 171 257C172 251 176 248 182 249C188 250 191 253 190 259Z"
        />
        <path class="notes-editor-illustration__check" d="M175 259C177 260 179 263 181 263C183 259 185 256 188 253" />
        <path class="notes-editor-illustration__text-line" d="M208 259C235 257 270 261 302 258" />

        <g class="notes-editor-illustration__pencil">
          <path class="notes-editor-illustration__pencil-side" d="M376 281C393 263 429 229 450 207" />
          <path class="notes-editor-illustration__pencil-side notes-editor-illustration__pencil-side--second" d="M388 274C406 257 438 224 458 214" />
          <path class="notes-editor-illustration__pencil-end" d="M450 207C453 209 456 212 458 214" />
          <path class="notes-editor-illustration__pencil-tip" d="M376 281C378 274 381 267 384 263C386 267 390 271 394 273C389 277 382 280 376 281Z" />
          <path class="notes-editor-illustration__pencil-nib" d="M376 281C379 280 381 279 383 277" />
        </g>

        <path class="notes-editor-illustration__flourish" d="M102 266C119 280 136 283 150 274C157 269 155 262 149 263" />
        <path class="notes-editor-illustration__spark" d="M108 110C107 117 109 124 108 132M98 121C105 120 112 122 118 120" />
        <path class="notes-editor-illustration__spark notes-editor-illustration__spark--small" d="M454 91C454 95 455 98 454 102M449 97C452 97 456 98 459 97" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.notes-editor-illustration {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 0;
  place-items: center;
  overflow: hidden;
}

.notes-editor-illustration__canvas {
  width: min(56%, 440px);
  min-width: 280px;
  max-height: min(58vh, 430px);
  overflow: visible;
  animation: notes-editor-illustration-arrive 420ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) both;
}

.notes-editor-illustration__sketch {
  transform: rotate(-0.55deg);
  transform-origin: 280px 180px;
}

.notes-editor-illustration__sheet-outline,
.notes-editor-illustration__sheet-echo,
.notes-editor-illustration__fold {
  stroke-linecap: round;
  stroke-linejoin: round;
}

.notes-editor-illustration__sheet-outline {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 25%, transparent);
  stroke-width: 1.75;
}

.notes-editor-illustration__sheet-echo {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent);
  stroke-width: 1.15;
}

.notes-editor-illustration__fold {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 18%, transparent);
  stroke-width: 1.55;
}

.notes-editor-illustration__title-line,
.notes-editor-illustration__text-line {
  stroke-linecap: round;
}

.notes-editor-illustration__title-line {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 27%, transparent);
  stroke-width: 6.5;
}

.notes-editor-illustration__text-line {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 14%, transparent);
  stroke-width: 4.6;
}

.notes-editor-illustration__text-line--short {
  opacity: 0.76;
}

.notes-editor-illustration__check-circle,
.notes-editor-illustration__check,
.notes-editor-illustration__pencil-side,
.notes-editor-illustration__pencil-end,
.notes-editor-illustration__pencil-tip,
.notes-editor-illustration__pencil-nib,
.notes-editor-illustration__flourish,
.notes-editor-illustration__spark {
  stroke-linecap: round;
  stroke-linejoin: round;
}

.notes-editor-illustration__check-circle {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 38%, transparent);
  stroke-width: 1.55;
}

.notes-editor-illustration__check {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 58%, transparent);
  stroke-width: 1.9;
}

.notes-editor-illustration__pencil-side,
.notes-editor-illustration__pencil-end {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 38%, transparent);
  stroke-width: 2.1;
}

.notes-editor-illustration__pencil-side--second {
  stroke-width: 1.7;
  opacity: 0.82;
}

.notes-editor-illustration__pencil-tip {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 28%, transparent);
  stroke-width: 1.45;
}

.notes-editor-illustration__pencil-nib {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 26%, transparent);
  stroke-width: 1.35;
}

.notes-editor-illustration__flourish {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent);
  stroke-width: 1.35;
}

.notes-editor-illustration__spark {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  stroke-width: 1.55;
}

.notes-editor-illustration__spark--small {
  opacity: 0.62;
}

@keyframes notes-editor-illustration-arrive {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 920px) {
  .notes-editor-illustration__canvas {
    width: min(64%, 380px);
    min-width: 250px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .notes-editor-illustration__canvas {
    animation: none;
  }
}

:global(.pm-no-animations) .notes-editor-illustration__canvas {
  animation: none;
}
</style>
