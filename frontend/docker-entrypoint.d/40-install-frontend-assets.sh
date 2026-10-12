#!/bin/sh
set -eu

source_dir=/opt/papermind-dist
target_dir=/usr/share/nginx/html

mkdir -p "${target_dir}/assets"

# Neue, gehashte Assets ergänzen, vorhandene ältere Versionen aber bewusst
# behalten. Bereits offene oder von Safari gecachte index.html-/JS-Versionen
# können dadurch während und nach einem Deployment weiter ihre Chunks laden.
cp -R "${source_dir}/assets/." "${target_dir}/assets/"

# HTML und sonstige Root-Dateien werden beim Start durch den aktuellen Build
# ersetzt. Keine fremden Datei-Eigentümer übernehmen: der Prozess läuft ohne Root.
find "${source_dir}" -mindepth 1 -maxdepth 1 ! -name assets -exec cp -R {} "${target_dir}/" \;
