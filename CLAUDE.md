# PaperMind – Hinweise für KI-Agenten

## Lokale Frontend-Entwicklung: immer den Vite-Dev-Server auf 5179 nutzen

Zum Prüfen von Frontend-Änderungen **immer den Vite-Dev-Server** verwenden, der
unter **`http://127.0.0.1:5179`** läuft – **nicht** den Docker-Container
`papermind-frontend`.

- **`127.0.0.1:5179` = Vite-Dev-Server** (`npm run dev` im Ordner `frontend/`).
  Liefert die Live-Quellen mit HMR und proxyt `/api` → `http://localhost:8040`
  (Backend-Container). Änderungen sind sofort sichtbar.
- Der **Docker-Container `papermind-frontend`** serviert einen fertigen nginx-Build
  und zeigt Quelltext-Änderungen erst nach `docker compose build frontend`. Er darf
  **nicht** zum Verifizieren laufender Änderungen genutzt werden. Vor der Dev-Arbeit
  `docker compose stop frontend`; nur für echte Prod-Build-Tests wieder hochfahren.
- Falls der Dev-Server nicht läuft: `docker compose stop frontend`, dann im Ordner
  `frontend/` `npm run dev` starten (bindet 5179 aus `.env` `FRONTEND_PORT`).
- **Immer über die IPv4-Adresse `http://127.0.0.1:5179` öffnen**, nicht `localhost`:
  macOS löst `localhost` zuerst nach IPv6 `::1` auf, wo parallele Dev-Server binden
  und den eigenen Server verdecken können.
- Backend, DB, AI und Worker laufen in Docker und bleiben stehen.
