#!/usr/bin/env bash
# =============================================================================
#  PaperMind – Raspberry Pi Setup Script
#  Führt alle Schritte für eine saubere Erstinstallation durch:
#    1. Systemprüfung
#    2. System-Updates & Abhängigkeiten
#    3. Docker + Docker Compose
#    4. Repo klonen / aktualisieren
#    5. .env interaktiv konfigurieren
#    6. SMB-Scanordner einrichten
#    7. Docker-Autostart einrichten
#    8. Images bauen & Stack starten
#    9. Statusprüfung
#
#  Verwendung:
#    chmod +x scripts/setup_pi.sh
#    ./scripts/setup_pi.sh [--repo <git-url>] [--branch <name>] [--no-start]
# =============================================================================

set -euo pipefail

# ── Farben ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()     { echo -e "${CYAN}[setup]${RESET} $*"; }
success() { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
error()   { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}══ $* ══${RESET}\n"; }

# ── CLI-Argumente ─────────────────────────────────────────────────────────────
REPO_URL=""
BRANCH="main"
NO_START=0
REPO_DIR="$HOME/papermind"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)   shift; REPO_URL="${1:-}"; [[ -z "$REPO_URL" ]] && error "--repo braucht eine URL" ;;
    --branch) shift; BRANCH="${1:-main}" ;;
    --dir)    shift; REPO_DIR="${1:-$HOME/papermind}" ;;
    --no-start) NO_START=1 ;;
    -h|--help)
      echo "Verwendung: $0 [--repo <git-url>] [--branch <name>] [--dir <pfad>] [--no-start]"
      exit 0 ;;
    *) error "Unbekannte Option: $1" ;;
  esac
  shift
done

# ── 1. Systemprüfung ──────────────────────────────────────────────────────────
header "1 / 9  Systemprüfung"

# Architektur
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "armv7l" && "$ARCH" != "x86_64" ]]; then
  warn "Unbekannte Architektur: $ARCH – Script wurde nur für aarch64/armv7l/x86_64 getestet."
else
  success "Architektur: $ARCH"
fi

# RAM
TOTAL_RAM_MB=$(awk '/MemTotal/ { printf "%d", $2/1024 }' /proc/meminfo)
if [[ "$TOTAL_RAM_MB" -lt 3800 ]]; then
  warn "Nur ${TOTAL_RAM_MB} MB RAM. Empfohlen: mindestens 4 GB."
else
  success "RAM: ${TOTAL_RAM_MB} MB"
fi

# Freier Speicher
FREE_DISK_GB=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
if [[ "$FREE_DISK_GB" -lt 8 ]]; then
  warn "Nur ${FREE_DISK_GB} GB freier Speicher auf /. Empfohlen: mindestens 8 GB."
else
  success "Freier Speicher: ${FREE_DISK_GB} GB"
fi

# Root-Rechte prüfen
if [[ "$EUID" -eq 0 ]]; then
  warn "Script läuft als root. Besser als normaler User mit sudo-Rechten ausführen."
fi

# ── 2. System-Updates & Abhängigkeiten ────────────────────────────────────────
header "2 / 9  System-Updates & Abhängigkeiten"

log "apt update + upgrade ..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

log "Installiere Basispakete ..."
sudo apt-get install -y -qq \
  git curl wget ca-certificates gnupg \
  htop unzip openssl \
  lsb-release apt-transport-https \
  samba

success "Systempakete installiert"

# ── 3. Docker ─────────────────────────────────────────────────────────────────
header "3 / 9  Docker & Docker Compose"

if command -v docker &>/dev/null; then
  DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
  success "Docker bereits installiert: $DOCKER_VERSION"
else
  log "Installiere Docker über get.docker.com ..."
  curl -fsSL https://get.docker.com | sh
  success "Docker installiert"
fi

# Aktuellen User zur docker-Gruppe hinzufügen
if ! groups "$USER" | grep -q docker; then
  log "Füge $USER zur docker-Gruppe hinzu ..."
  sudo usermod -aG docker "$USER"
  warn "Gruppe hinzugefügt. Damit der Effekt ohne Neustart gilt, wird 'newgrp docker' verwendet."
fi

# Docker Compose Plugin prüfen
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unbekannt")
  success "Docker Compose Plugin: $COMPOSE_VERSION"
else
  log "Installiere Docker Compose Plugin ..."
  DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  # Ermittelt die passende Compose-Version für die Architektur
  COMPOSE_ARCH=$(uname -m)
  case "$COMPOSE_ARCH" in
    aarch64) COMPOSE_ARCH="aarch64" ;;
    armv7l)  COMPOSE_ARCH="armv7" ;;
    x86_64)  COMPOSE_ARCH="x86_64" ;;
  esac
  COMPOSE_URL="https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${COMPOSE_ARCH}"
  curl -SL "$COMPOSE_URL" -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  success "Docker Compose Plugin installiert"
fi

# ── 4. Repo klonen / aktualisieren ────────────────────────────────────────────
header "4 / 9  Repository"

if [[ -d "$REPO_DIR/.git" ]]; then
  log "Repo bereits vorhanden in $REPO_DIR – aktualisiere ..."
  cd "$REPO_DIR"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
  success "Repo aktualisiert (Branch: $BRANCH)"
elif [[ -n "$REPO_URL" ]]; then
  log "Klone $REPO_URL nach $REPO_DIR ..."
  git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
  cd "$REPO_DIR"
  success "Repo geklont"
else
  # Script läuft bereits aus dem Repo-Verzeichnis
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  cd "$REPO_DIR"
  log "Kein --repo angegeben. Arbeite in: $REPO_DIR"
  success "Repo-Verzeichnis: $REPO_DIR"
fi

# ── 5. .env konfigurieren ─────────────────────────────────────────────────────
header "5 / 9  .env Konfiguration"

ENV_FILE="$REPO_DIR/.env"
ENV_EXAMPLE="$REPO_DIR/.env.example"

if [[ -f "$ENV_FILE" ]]; then
  warn ".env existiert bereits."
  read -rp "    Überschreiben? Bestehende Werte gehen verloren. [j/N] " OVERWRITE
  if [[ "${OVERWRITE,,}" != "j" ]]; then
    success ".env unverändert."
    SKIP_ENV=1
  else
    SKIP_ENV=0
  fi
else
  SKIP_ENV=0
fi

if [[ "${SKIP_ENV}" -eq 0 ]]; then
  # PI-IP ermitteln
  DETECTED_IP=$(hostname -I | awk '{print $1}')
  echo ""
  echo -e "  ${BOLD}Erkannte IP-Adresse:${RESET} $DETECTED_IP"
  read -rp "  Pi-IP-Adresse eingeben [${DETECTED_IP}]: " PI_IP
  PI_IP="${PI_IP:-$DETECTED_IP}"

  # Datenbank-Zugangsdaten
  echo ""
  read -rp "  Datenbankname      [papermind]: " POSTGRES_DB
  POSTGRES_DB="${POSTGRES_DB:-papermind}"

  read -rp "  Datenbankbenutzer  [pmuser]:    " POSTGRES_USER
  POSTGRES_USER="${POSTGRES_USER:-pmuser}"

  read -rsp "  Datenbankpasswort  (leer = zufällig generieren): " POSTGRES_PASSWORD
  echo ""
  if [[ -z "$POSTGRES_PASSWORD" ]]; then
    POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
    log "Generiertes Passwort: ${BOLD}${POSTGRES_PASSWORD}${RESET}  ← bitte notieren!"
  fi

  # API-Key
  DIRECT_UPLOAD_API_KEY=$(openssl rand -hex 32)
  log "Generierter API-Key für iOS Shortcut: ${BOLD}${DIRECT_UPLOAD_API_KEY}${RESET}  ← im Shortcut eintragen!"

  # .env schreiben
  cp "$ENV_EXAMPLE" "$ENV_FILE"

  # Werte einsetzen (sed, funktioniert auf Linux)
  sed -i "s|<your_db_name>|${POSTGRES_DB}|g"        "$ENV_FILE"
  sed -i "s|<your_db_user>|${POSTGRES_USER}|g"       "$ENV_FILE"
  sed -i "s|<your_db_password>|${POSTGRES_PASSWORD}|g" "$ENV_FILE"
  sed -i "s|<PI_IP>|${PI_IP}|g"                       "$ENV_FILE"
  sed -i "s|<generate_with_openssl_rand_hex_32>|${DIRECT_UPLOAD_API_KEY}|g" "$ENV_FILE"

  success ".env konfiguriert für $PI_IP"
  echo ""
  echo -e "  ${YELLOW}Bitte jetzt notieren:${RESET}"
  echo -e "    DB-Passwort : ${BOLD}${POSTGRES_PASSWORD}${RESET}"
  echo -e "    API-Key     : ${BOLD}${DIRECT_UPLOAD_API_KEY}${RESET}"
  echo ""
fi

# .env laden für spätere Ausgabe
set -a; source "$ENV_FILE"; set +a

# ── 6. SMB-Scanordner ────────────────────────────────────────────────────────
header "6 / 9  SMB Scanordner"

SCAN_INBOX_DIR="$REPO_DIR/scan-inbox"
SMB_SHARE_NAME="PaperMind Scans"
sudo install -d -m 0770 -o "$USER" -g "$USER" "$SCAN_INBOX_DIR"
success "Scanordner angelegt: $SCAN_INBOX_DIR"

read -rp "    SMB-Freigabe '${SMB_SHARE_NAME}' für iPhone-Dateien-App einrichten? [J/n] " CONFIGURE_SMB
if [[ "${CONFIGURE_SMB,,}" != "n" ]]; then
  SMB_CONF="/etc/samba/smb.conf"
  SMB_MARKER_BEGIN="# BEGIN PaperMind Scan Inbox"
  SMB_MARKER_END="# END PaperMind Scan Inbox"

  if sudo test -f "$SMB_CONF"; then
    sudo cp "$SMB_CONF" "${SMB_CONF}.papermind.bak"
  fi

  sudo sed -i "/${SMB_MARKER_BEGIN}/,/${SMB_MARKER_END}/d" "$SMB_CONF"
  sudo tee -a "$SMB_CONF" >/dev/null <<EOF

${SMB_MARKER_BEGIN}
[${SMB_SHARE_NAME}]
   path = ${SCAN_INBOX_DIR}
   browseable = yes
   read only = no
   guest ok = no
   valid users = ${USER}
   force user = ${USER}
   create mask = 0660
   directory mask = 0770
   vfs objects = catia fruit streams_xattr
   fruit:metadata = stream
   fruit:model = MacSamba
${SMB_MARKER_END}
EOF

  if ! sudo pdbedit -L 2>/dev/null | cut -d: -f1 | grep -qx "$USER"; then
    echo ""
    echo -e "  ${BOLD}SMB-Passwort für Benutzer '${USER}' festlegen.${RESET}"
    echo "  Dieses Passwort gibst du später in der iOS Dateien-App ein."
    read -rsp "  SMB-Passwort: " SMB_PASSWORD
    echo ""
    read -rsp "  SMB-Passwort wiederholen: " SMB_PASSWORD_REPEAT
    echo ""
    if [[ "$SMB_PASSWORD" != "$SMB_PASSWORD_REPEAT" || -z "$SMB_PASSWORD" ]]; then
      error "SMB-Passwörter stimmen nicht überein oder sind leer."
    fi
    printf '%s\n%s\n' "$SMB_PASSWORD" "$SMB_PASSWORD" | sudo smbpasswd -s -a "$USER" >/dev/null
  else
    warn "SMB-Benutzer '${USER}' existiert bereits. Passwort bleibt unverändert."
  fi

  sudo systemctl enable smbd >/dev/null
  sudo systemctl restart smbd
  success "SMB-Freigabe aktiv: smb://$(hostname -I | awk '{print $1}')/${SMB_SHARE_NAME}"
else
  warn "SMB-Freigabe übersprungen. Der Ordner kann später manuell freigegeben werden."
fi

# ── 7. Docker-Autostart & Host-Helfer ─────────────────────────────────────────
header "7 / 9  Docker Autostart & Host-Helfer"

sudo systemctl enable docker
sudo systemctl start docker
success "Docker-Dienst aktiviert und gestartet"

# Host-Control: ermöglicht Herunterfahren/Neustarten aus dem System-Tab.
# Der Container schreibt Kommandos in $REPO_DIR/host-control, dieser
# systemd-Service auf dem Host führt poweroff/reboot aus.
CONTROL_DIR="$REPO_DIR/host-control"
WATCHER="$REPO_DIR/deploy/host-control/papermind-host-control.sh"

if [[ -f "$WATCHER" ]]; then
  log "Richte Host-Helfer für Power-Aktionen ein ..."
  mkdir -p "$CONTROL_DIR"
  chmod 0770 "$CONTROL_DIR"
  chmod +x "$WATCHER"

  # systemd-Unit mit den tatsächlichen Pfaden erzeugen (passt zur Compose-
  # Default-Bind-Mount ./host-control relativ zu $REPO_DIR).
  sudo tee /etc/systemd/system/papermind-host-control.service >/dev/null <<UNIT
[Unit]
Description=PaperMind Host-Control (Power-Aktionen aus dem Container)
After=multi-user.target

[Service]
Type=simple
Environment=CONTROL_DIR=${CONTROL_DIR}
Environment=POLL_INTERVAL=3
ExecStart=${WATCHER}
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
UNIT

  sudo systemctl daemon-reload
  sudo systemctl enable --now papermind-host-control.service
  success "Host-Helfer aktiv (papermind-host-control.service)"
else
  warn "deploy/host-control nicht gefunden – Power-Aktionen bleiben deaktiviert."
fi

# ── 8. Images bauen & Stack starten ──────────────────────────────────────────
header "8 / 9  Docker Images bauen & Stack starten"

cd "$REPO_DIR"

if [[ "$NO_START" -eq 1 ]]; then
  warn "--no-start gesetzt: Überspringe docker compose up."
else
  log "Baue Images (das dauert beim ersten Mal mehrere Minuten) ..."
  # newgrp sorgt dafür, dass die docker-Gruppe aktiv ist, ohne Neuanmeldung
  sg docker -c "docker compose build" 2>&1 | tee /tmp/pm_build.log | grep -E '^\[|\berror\b|Step|--->' || true

  log "Starte Stack ..."
  sg docker -c "docker compose up -d"
  success "Stack gestartet"
fi

# ── 9. Statusprüfung ─────────────────────────────────────────────────────────
header "9 / 9  Statusprüfung"

if [[ "$NO_START" -eq 0 ]]; then
  log "Warte 15 Sekunden auf Healthchecks ..."
  sleep 15

  echo ""
  sg docker -c "docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'" 2>/dev/null || \
    sg docker -c "docker compose ps"
  echo ""

  # Frontend & Backend erreichbar?
  FRONTEND_PORT="${FRONTEND_PORT:-5179}"
  BACKEND_PORT="${BACKEND_PORT:-8040}"

  if curl -sf "http://localhost:${BACKEND_PORT}/health" -o /dev/null; then
    success "Backend antwortet auf Port ${BACKEND_PORT}"
  else
    warn "Backend antwortet noch nicht auf Port ${BACKEND_PORT} – ggf. noch am Starten."
  fi
fi

# ── Zusammenfassung ───────────────────────────────────────────────────────────
DETECTED_IP=$(hostname -I | awk '{print $1}')
FRONTEND_PORT="${FRONTEND_PORT:-5179}"
BACKEND_PORT="${BACKEND_PORT:-8040}"

echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  PaperMind Setup abgeschlossen!${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Frontend  →  ${CYAN}http://${DETECTED_IP}:${FRONTEND_PORT}${RESET}"
echo -e "  Backend   →  ${CYAN}http://${DETECTED_IP}:${BACKEND_PORT}${RESET}"
echo -e "  Scan SMB  →  ${CYAN}smb://${DETECTED_IP}/${SMB_SHARE_NAME}${RESET}"
echo -e "  Repo      →  ${REPO_DIR}"
echo ""
echo -e "  Nützliche Befehle:"
echo -e "    ${BOLD}docker compose logs -f${RESET}          # Live-Logs"
echo -e "    ${BOLD}docker compose ps${RESET}               # Status aller Dienste"
echo -e "    ${BOLD}docker compose down${RESET}             # Stack stoppen"
echo -e "    ${BOLD}./scripts/deploy_pi.sh --build${RESET}  # Update deployen"
echo ""
echo -e "  ${YELLOW}Hinweis:${RESET} Falls die docker-Gruppe neu vergeben wurde,"
echo -e "  bitte einmal ab- und wieder anmelden oder ${BOLD}newgrp docker${RESET} ausführen."
echo ""
