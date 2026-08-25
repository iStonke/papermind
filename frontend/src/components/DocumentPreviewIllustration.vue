<template>
  <div
    class="document-preview-illustration"
    role="status"
    aria-label="Kein Dokument ausgewählt. Wähle ein Dokument aus der Liste, um die Vorschau zu öffnen."
  >
    <svg
      class="document-preview-illustration__canvas"
      viewBox="0 0 560 360"
      fill="none"
      aria-hidden="true"
    >
      <g class="document-preview-illustration__sketch">
        <path
          class="document-preview-illustration__sheet-outline"
          d="M160 58C210 56 286 59 342 57C363 78 383 98 405 121C406 158 404 227 406 270C407 285 397 294 383 294C318 292 217 296 157 294C143 294 135 285 136 271C138 217 134 137 136 80C136 67 146 59 160 58Z"
        />
        <path
          class="document-preview-illustration__sheet-echo"
          d="M162 61C216 59 289 62 341 60C361 80 381 100 402 122C403 163 401 225 403 269C404 282 395 291 382 291C314 289 220 293 159 291C147 291 139 283 140 270C142 214 138 138 140 82C140 70 149 62 162 61Z"
        />
        <path
          class="document-preview-illustration__fold"
          d="M342 58C341 74 343 92 342 103C342 115 350 121 362 121C375 120 391 123 404 121"
        />

        <path class="document-preview-illustration__title-line" d="M174 104C204 101 239 106 274 103" />

        <path
          class="document-preview-illustration__image-frame"
          d="M173 137C214 136 275 139 331 137C339 137 343 142 342 150C341 170 344 190 342 210C341 218 336 221 328 220C282 219 222 222 177 220C170 220 166 215 167 208C169 187 165 163 167 145C167 140 169 138 173 137Z"
        />
        <path class="document-preview-illustration__sun" d="M310 157C316 156 320 160 320 166C320 172 316 175 310 174C305 174 302 171 303 165C304 160 306 158 310 157Z" />
        <path class="document-preview-illustration__landscape" d="M177 208C190 194 202 184 214 190C224 195 229 203 237 201C249 198 255 175 269 176C282 178 295 194 305 202C316 211 327 211 340 208" />

        <path class="document-preview-illustration__text-line" d="M174 246C211 243 257 248 302 245" />
        <path class="document-preview-illustration__text-line document-preview-illustration__text-line--short" d="M174 268C201 270 228 266 256 269" />

        <g class="document-preview-illustration__magnifier">
          <path
            class="document-preview-illustration__lens"
            d="M376 218C393 216 408 229 409 246C410 263 397 277 380 278C363 279 349 267 348 250C346 233 359 220 376 218Z"
          />
          <path
            class="document-preview-illustration__lens-echo"
            d="M376 221C391 219 405 231 406 246C407 261 395 274 380 275C365 276 352 265 351 250C349 235 361 223 376 221Z"
          />
          <path class="document-preview-illustration__handle" d="M399 270C412 283 424 294 437 307" />
          <path class="document-preview-illustration__handle-echo" d="M403 266C416 279 429 291 441 303" />
          <path class="document-preview-illustration__handle-end" d="M437 307C439 306 441 305 441 303" />
        </g>

        <path class="document-preview-illustration__corner-mark" d="M116 249C128 258 139 259 149 253C154 249 153 244 148 245" />
        <path class="document-preview-illustration__spark" d="M111 102C110 109 112 116 111 123M101 113C108 112 115 114 121 112" />
        <path class="document-preview-illustration__spark document-preview-illustration__spark--small" d="M435 91C435 95 436 98 435 102M430 97C433 97 437 98 440 97" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.document-preview-illustration {
  display: grid;
  width: 100%;
  height: 100%;
  min-height: 0;
  place-items: center;
  overflow: hidden;
}

.document-preview-illustration__canvas {
  width: min(56%, 440px);
  min-width: 280px;
  max-height: min(58vh, 430px);
  overflow: visible;
  animation: document-preview-illustration-arrive 420ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1)) both;
}

.document-preview-illustration__sketch {
  transform: rotate(0.45deg);
  transform-origin: 280px 180px;
}

.document-preview-illustration__sheet-outline,
.document-preview-illustration__sheet-echo,
.document-preview-illustration__fold,
.document-preview-illustration__image-frame,
.document-preview-illustration__sun,
.document-preview-illustration__landscape,
.document-preview-illustration__lens,
.document-preview-illustration__lens-echo,
.document-preview-illustration__handle,
.document-preview-illustration__handle-echo,
.document-preview-illustration__handle-end,
.document-preview-illustration__corner-mark,
.document-preview-illustration__spark {
  stroke-linecap: round;
  stroke-linejoin: round;
}

.document-preview-illustration__sheet-outline {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 25%, transparent);
  stroke-width: 1.75;
}

.document-preview-illustration__sheet-echo {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent);
  stroke-width: 1.15;
}

.document-preview-illustration__fold {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 18%, transparent);
  stroke-width: 1.55;
}

.document-preview-illustration__title-line,
.document-preview-illustration__text-line {
  stroke-linecap: round;
}

.document-preview-illustration__title-line {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 27%, transparent);
  stroke-width: 6.5;
}

.document-preview-illustration__text-line {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 14%, transparent);
  stroke-width: 4.6;
}

.document-preview-illustration__text-line--short {
  opacity: 0.76;
}

.document-preview-illustration__image-frame {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 15%, transparent);
  stroke-width: 1.45;
}

.document-preview-illustration__sun {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  stroke-width: 1.45;
}

.document-preview-illustration__landscape {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 16%, transparent);
  stroke-width: 1.55;
}

.document-preview-illustration__lens {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 42%, transparent);
  stroke-width: 1.9;
}

.document-preview-illustration__lens-echo {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 13%, transparent);
  stroke-width: 1.05;
}

.document-preview-illustration__handle,
.document-preview-illustration__handle-echo,
.document-preview-illustration__handle-end {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 38%, transparent);
}

.document-preview-illustration__handle {
  stroke-width: 2.1;
}

.document-preview-illustration__handle-echo {
  stroke-width: 1.55;
  opacity: 0.8;
}

.document-preview-illustration__handle-end {
  stroke-width: 1.35;
}

.document-preview-illustration__corner-mark {
  stroke: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent);
  stroke-width: 1.35;
}

.document-preview-illustration__spark {
  stroke: color-mix(in srgb, var(--pm-accent, #006b75) 34%, transparent);
  stroke-width: 1.55;
}

.document-preview-illustration__spark--small {
  opacity: 0.62;
}

@keyframes document-preview-illustration-arrive {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 920px) {
  .document-preview-illustration__canvas {
    width: min(64%, 380px);
    min-width: 250px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .document-preview-illustration__canvas {
    animation: none;
  }
}

:global(.pm-no-animations) .document-preview-illustration__canvas {
  animation: none;
}
</style>
