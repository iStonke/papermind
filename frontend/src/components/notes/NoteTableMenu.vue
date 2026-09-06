<template>
  <button
    v-if="editor && tableHandle.visible"
    type="button"
    class="pm-table-handle"
    :class="{ 'is-open': tableMenu.open && tableMenu.mode === 'edit' }"
    :style="tableHandle.style"
    aria-label="Tabellenaktionen öffnen"
    title="Tabellenaktionen"
    @pointermove.stop
    @mousedown.stop.prevent="openTableMenuFromHandle"
  >
    <v-icon size="18">mdi-dots-vertical</v-icon>
  </button>

  <div
    v-if="editor && tableMenu.open"
    class="pm-float pm-table-menu"
    :style="tableMenu.style"
    :aria-label="tableMenu.mode === 'insert' ? 'Tabelle einfügen' : 'Tabelle bearbeiten'"
    @mousedown.stop
  >
    <template v-if="tableMenu.mode === 'insert'">
      <div class="pm-table-menu__head">
        <span>Tabelle einfügen</span>
        <strong>{{ tableMenu.rows }} × {{ tableMenu.cols }}</strong>
      </div>
      <div class="pm-table-menu__grid" role="grid" aria-label="Tabellengröße wählen">
        <button
          v-for="cell in TABLE_PICKER_CELLS"
          :key="`${cell.row}:${cell.col}`"
          type="button"
          class="pm-table-menu__cell"
          :class="{ 'is-selected': cell.row <= tableMenu.rows && cell.col <= tableMenu.cols }"
          :aria-label="`${cell.row} Zeilen und ${cell.col} Spalten`"
          @mouseenter="selectTableSize(cell.row, cell.col)"
          @focus="selectTableSize(cell.row, cell.col)"
          @mousedown.prevent="insertTable(cell.row, cell.col)"
        ></button>
      </div>
      <div class="pm-table-menu__header-options" role="radiogroup" aria-label="Tabellenkopf wählen">
        <button
          type="button"
          class="pm-table-menu__header-toggle"
          :class="{ 'is-active': tableMenu.withHeaderRow }"
          role="radio"
          :aria-checked="tableMenu.withHeaderRow"
          @mousedown.prevent="selectTableHeaderMode('row')"
        >
          <v-icon size="17">mdi-table-headers-eye</v-icon>
          Erste Zeile als Kopfzeile
        </button>
        <button
          type="button"
          class="pm-table-menu__header-toggle"
          :class="{ 'is-active': tableMenu.withHeaderColumn }"
          role="radio"
          :aria-checked="tableMenu.withHeaderColumn"
          @mousedown.prevent="selectTableHeaderMode('column')"
        >
          <v-icon size="17">mdi-table-column</v-icon>
          Erste Spalte als Kopfspalte
        </button>
      </div>
    </template>

    <template v-else>
      <div class="pm-table-menu__head">
        <span>Tabelle bearbeiten</span>
      </div>
      <div class="pm-table-menu__actions">
        <button type="button" @mousedown.prevent="runTableCommand('addRowAfter')">
          <v-icon size="17">mdi-table-row-plus-after</v-icon><span>Zeile darunter</span>
        </button>
        <button type="button" @mousedown.prevent="runTableCommand('addColumnAfter')">
          <v-icon size="17">mdi-table-column-plus-after</v-icon><span>Spalte rechts</span>
        </button>
        <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderRow')">
          <v-icon size="17">mdi-table-headers-eye</v-icon><span>Kopfzeile umschalten</span>
        </button>
        <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderColumn')">
          <v-icon size="17">mdi-table-column</v-icon><span>Kopfspalte umschalten</span>
        </button>
        <button type="button" @mousedown.prevent="runTableCommand('deleteRow')">
          <v-icon size="17">mdi-table-row-remove</v-icon><span>Zeile löschen</span>
        </button>
        <button type="button" @mousedown.prevent="runTableCommand('deleteColumn')">
          <v-icon size="17">mdi-table-column-remove</v-icon><span>Spalte löschen</span>
        </button>
        <button type="button" class="is-danger" @mousedown.prevent="runTableCommand('deleteTable')">
          <v-icon size="17">mdi-table-remove</v-icon><span>Tabelle löschen</span>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
const props = defineProps({ controller: { type: Object, required: true } });
const {
  editor,
  TABLE_PICKER_CELLS,
  tableMenu,
  tableHandle,
  openTableMenuFromHandle,
  selectTableSize,
  selectTableHeaderMode,
  insertTable,
  runTableCommand,
} = props.controller;
</script>

<style scoped src="./styles/tableMenu.css"></style>
<style scoped src="./styles/floating.css"></style>
