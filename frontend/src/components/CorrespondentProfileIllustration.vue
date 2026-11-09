<template>
  <div
    class="correspondent-profile-illustration"
    role="status"
    aria-label="Kein Korrespondent ausgewählt. Wähle einen Eintrag aus der Liste, um sein Profil zu öffnen."
  >
    <svg viewBox="0 0 560 360" fill="none" aria-hidden="true">
      <g class="correspondent-profile-illustration__sketch" stroke-linecap="round" stroke-linejoin="round">
        <path class="outline" d="M146 84C212 81 331 85 389 83C403 83 412 92 412 107C413 151 410 210 412 249C413 264 404 273 389 273C328 271 204 275 145 273C130 273 122 264 123 249C124 209 121 147 123 107C123 94 132 85 146 84Z" />
        <path class="echo" d="M148 88C214 85 328 89 388 87C400 87 408 95 408 108C409 151 406 210 408 248C409 261 401 269 388 269C325 267 205 271 147 269C134 269 126 261 127 248C128 208 125 148 127 109C127 97 135 89 148 88Z" />
        <path class="detail" d="M155 128C174 127 207 129 227 128C233 128 237 132 237 138L236 219C236 225 232 229 226 229C207 228 173 231 154 229C148 229 145 225 145 219L146 138C146 132 149 129 155 128Z" />
        <path class="outline" d="M191 146C200 146 207 153 207 162C206 171 200 178 191 178C182 178 175 171 175 162C175 153 182 146 191 146ZM164 210C165 194 176 186 191 186C206 186 217 194 218 210C203 211 179 210 164 210Z" />
        <path class="title-line" d="M259 149C286 147 317 150 352 148" />
        <path class="text-line" d="M259 176C283 175 320 178 374 175M259 199C279 201 311 198 339 199" />
        <path class="accent" d="M390 219C407 217 422 230 423 247C424 264 411 279 394 280C377 281 363 269 362 252C360 235 373 221 390 219ZM415 272C428 285 438 296 451 308M418 269C431 282 442 293 454 305L451 308" />
        <path class="accent-echo" d="M390 223C405 221 418 232 419 247C420 262 409 275 394 276C379 277 367 266 366 251C365 236 375 225 390 223Z" />
        <path class="spark" d="M108 121C107 128 109 135 108 142M98 132C105 131 112 133 118 131M447 110V121M442 116H452" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.correspondent-profile-illustration {
  display: grid;
  flex: 1;
  min-height: 0;
  place-items: center;
  overflow: hidden;
  background: var(--pm-viewer-surface);
}
.correspondent-profile-illustration svg {
  width: clamp(min(100%, 250px), 56%, 440px);
  max-height: min(58vh, 430px);
  animation: correspondent-profile-illustration-arrive var(--pm-duration-slow) var(--pm-easing-decel) both;
}
.correspondent-profile-illustration__sketch { transform: rotate(0.45deg); transform-origin: 280px 180px; }
.outline { stroke: color-mix(in srgb, var(--pm-text) 25%, transparent); stroke-width: 1.75; }
.echo { stroke: color-mix(in srgb, var(--pm-text) 8%, transparent); stroke-width: 1.15; }
.detail { stroke: color-mix(in srgb, var(--pm-text) 16%, transparent); stroke-width: 1.5; }
.title-line { stroke: color-mix(in srgb, var(--pm-text) 27%, transparent); stroke-width: 6.5; }
.text-line { stroke: color-mix(in srgb, var(--pm-text) 14%, transparent); stroke-width: 4.6; }
.accent { stroke: color-mix(in srgb, var(--pm-accent) 42%, transparent); stroke-width: 1.9; }
.accent-echo { stroke: color-mix(in srgb, var(--pm-accent) 13%, transparent); stroke-width: 1.05; }
.spark { stroke: color-mix(in srgb, var(--pm-accent) 34%, transparent); stroke-width: 1.55; }

@keyframes correspondent-profile-illustration-arrive {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
