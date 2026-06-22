#!/bin/sh
set -eu

source_dir=/opt/papermind-dist
target_dir=/usr/share/nginx/html

mkdir -p "${target_dir}/assets"

# Neue, gehashte Assets ergänzen, vorhandene ältere Versionen aber bewusst
# behalten. Bereits offene oder von Safari gecachte index.html-/JS-Versionen
# können dadurch während und nach einem Deployment weiter ihre Chunks laden.
cp -a "${source_dir}/assets/." "${target_dir}/assets/"

# HTML und sonstige Root-Dateien werden dagegen immer atomar durch den aktuellen
# Build ersetzt.
find "${source_dir}" -mindepth 1 -maxdepth 1 ! -name assets -exec cp -a {} "${target_dir}/" \;
