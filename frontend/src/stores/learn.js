import { defineStore } from 'pinia';
import {
  listCourses,
  createCourse,
  updateCourse,
  deleteCourse,
  getCourseBoard,
  createSession,
  createSheet,
  updateSheet,
  deleteSheet,
  listSheets,
  listCards,
  createCard,
  updateCard,
  deleteCard,
  reviewCard,
  listLearningRuns,
  createLearningRun,
  updateLearningRun,
  deleteLearningRun,
  listMarkers,
  promoteMarker,
} from '../api/learn.js';

// Lernbereich-Store (Container-Ebene). Hält die Kursliste und das Board des
// aktiven Kurses (Sitzungen mit ihren Lernblättern) für Artboard 1a.
export const useLearnStore = defineStore('learn', {
  state: () => ({
    courses: [],
    activeCourseId: null,
    board: null, // { course, sessions:[{...,sheets:[]}], loose_sheets:[] }
    allSheets: [], // alle Lernblätter (kursübergreifend) für die Startseite
    cards: [], // Karten des aktuell geöffneten Lernblatts
    cardsSheetId: null,
    learningRuns: [], // gespeicherter Verlauf des aktiven Kurses
    openMarkers: [], // offene Lernmarker (keine oder noch unvollständige Karte)
    loadingCourses: false,
    loadingBoard: false,
    loadingCards: false,
    loadingMarkers: false,
    error: null,
  }),

  getters: {
    activeCourse: (state) => state.courses.find((c) => c.id === state.activeCourseId) || null,
  },

  actions: {
    async fetchCourses() {
      this.loadingCourses = true;
      this.error = null;
      try {
        const res = await listCourses();
        this.courses = res.items || [];
        if (!this.activeCourseId && this.courses.length) {
          await this.selectCourse(this.courses[0].id);
        }
      } catch (err) {
        this.error = err?.message || 'Kurse konnten nicht geladen werden';
      } finally {
        this.loadingCourses = false;
      }
    },

    async selectCourse(courseId) {
      this.activeCourseId = courseId;
      await Promise.all([this.fetchBoard(), this.fetchLearningRuns()]);
    },

    // Alle Lernblätter kursübergreifend – Grundlage der Startseiten-Übersicht.
    async fetchAllSheets() {
      try {
        const res = await listSheets({});
        this.allSheets = res.items || [];
      } catch (err) {
        this.error = err?.message || 'Lernblätter konnten nicht geladen werden';
      }
    },

    async fetchBoard() {
      if (!this.activeCourseId) {
        this.board = null;
        return;
      }
      this.loadingBoard = true;
      try {
        this.board = await getCourseBoard(this.activeCourseId);
      } catch (err) {
        this.error = err?.message || 'Board konnte nicht geladen werden';
      } finally {
        this.loadingBoard = false;
      }
    },

    async addCourse(payload) {
      const course = await createCourse(payload);
      this.courses.push(course);
      await this.selectCourse(course.id);
      return course;
    },

    async renameCourse(id, payload) {
      const updated = await updateCourse(id, payload);
      const idx = this.courses.findIndex((c) => c.id === id);
      if (idx !== -1) this.courses[idx] = { ...this.courses[idx], ...updated };
      return updated;
    },

    async removeCourse(id) {
      await deleteCourse(id);
      this.courses = this.courses.filter((c) => c.id !== id);
      if (this.activeCourseId === id) {
        this.activeCourseId = null;
        await (this.courses.length ? this.selectCourse(this.courses[0].id) : this.fetchBoard());
      }
      await this.fetchCourses();
    },

    async addSession(courseId, payload) {
      await createSession(courseId, payload);
      await Promise.all([this.fetchBoard(), this.fetchCourses()]);
    },

    async addSheet(payload) {
      await createSheet(payload);
      await Promise.all([this.fetchBoard(), this.fetchCourses(), this.fetchAllSheets()]);
    },

    async patchSheet(id, payload) {
      await updateSheet(id, payload);
      await Promise.all([this.fetchBoard(), this.fetchAllSheets()]);
    },

    async removeSheet(id) {
      await deleteSheet(id);
      await Promise.all([this.fetchBoard(), this.fetchCourses(), this.fetchAllSheets()]);
    },

    // --- Karten ------------------------------------------------------------
    async fetchCards(sheetId) {
      this.cardsSheetId = sheetId;
      this.loadingCards = true;
      try {
        const res = await listCards(sheetId);
        // Nur übernehmen, wenn noch dasselbe Blatt offen ist (Race vermeiden).
        if (this.cardsSheetId === sheetId) this.cards = res.items || [];
      } catch (err) {
        this.error = err?.message || 'Karten konnten nicht geladen werden';
      } finally {
        this.loadingCards = false;
      }
    },

    async addCard(sheetId, payload) {
      await createCard(sheetId, payload);
      await Promise.all([this.fetchCards(sheetId), this.fetchBoard(), this.fetchAllSheets()]);
    },

    async patchCard(id, sheetId, payload) {
      await updateCard(id, payload);
      // Eine Bearbeitung kann die Lernbereitschaft ändern (beide Seiten befüllt).
      await Promise.all([this.fetchCards(sheetId), this.fetchBoard(), this.fetchAllSheets()]);
    },

    async removeCard(id, sheetId) {
      await deleteCard(id);
      await Promise.all([this.fetchCards(sheetId), this.fetchBoard(), this.fetchAllSheets()]);
    },

    // Lernstand einer Karte setzen (Selbsteinschätzung). Optimistisch im lokalen
    // cards-Array spiegeln; Kurs-/Board-Aggregate erst am Ende des Durchlaufs neu laden.
    async reviewCard(id, status) {
      const updated = await reviewCard(id, status);
      const idx = this.cards.findIndex((c) => c.id === id);
      if (idx !== -1) this.cards[idx] = { ...this.cards[idx], ...updated };
      return updated;
    },

    // --- Gespeicherte Lerndurchläufe --------------------------------------
    async fetchLearningRuns() {
      if (!this.activeCourseId) {
        this.learningRuns = [];
        return;
      }
      try {
        const res = await listLearningRuns(this.activeCourseId);
        this.learningRuns = res.items || [];
      } catch (err) {
        this.error = err?.message || 'Lernverlauf konnte nicht geladen werden';
      }
    },

    async addLearningRun(courseId, payload) {
      const run = await createLearningRun(courseId, payload);
      this.learningRuns = [run, ...this.learningRuns.filter((item) => item.id !== run.id)];
      return run;
    },

    async patchLearningRun(id, payload) {
      const run = await updateLearningRun(id, payload);
      const idx = this.learningRuns.findIndex((item) => item.id === id);
      if (idx === -1) this.learningRuns.unshift(run);
      else this.learningRuns[idx] = run;
      return run;
    },

    async removeLearningRun(id) {
      await deleteLearningRun(id);
      this.learningRuns = this.learningRuns.filter((item) => item.id !== id);
    },

    // --- Nachbereitung: offene Marker --------------------------------------
    async fetchOpenMarkers() {
      this.loadingMarkers = true;
      try {
        const res = await listMarkers({ open: true });
        this.openMarkers = res.items || [];
      } catch (err) {
        this.error = err?.message || 'Lernmarker konnten nicht geladen werden';
      } finally {
        this.loadingMarkers = false;
      }
    },

    // Marker → Karte mit Anker. `refresh=false` überspringt das Auffrischen
    // (für Warteschlangen: einmal am Ende auffrischen statt pro Schritt).
    async promoteMarker(payload, refresh = true) {
      const card = await promoteMarker(payload);
      if (refresh) await this.refreshAfterPromote();
      return card;
    },

    async refreshAfterPromote() {
      await Promise.all([this.fetchOpenMarkers(), this.fetchBoard(), this.fetchCourses(), this.fetchAllSheets()]);
    },
  },
});
