import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

// Lernbereich – Container-Ebene (Kurs/Sitzung/Lernblatt). Karten/Artefakte
// folgen später (Masken 1b/1c).

// --- Kurse -----------------------------------------------------------------
export const listCourses = () => apiGet('/api/learn/courses');
export const createCourse = (body = {}) => apiPost('/api/learn/courses', body);
export const updateCourse = (id, body = {}) => apiPatch(`/api/learn/courses/${id}`, body);
export const deleteCourse = (id) => apiDelete(`/api/learn/courses/${id}`);
export const getCourseBoard = (id) => apiGet(`/api/learn/courses/${id}/board`);

// --- Sitzungen -------------------------------------------------------------
export const listSessions = (courseId) => apiGet(`/api/learn/courses/${courseId}/sessions`);
export const createSession = (courseId, body = {}) => apiPost(`/api/learn/courses/${courseId}/sessions`, body);
export const updateSession = (id, body = {}) => apiPatch(`/api/learn/sessions/${id}`, body);
export const deleteSession = (id) => apiDelete(`/api/learn/sessions/${id}`);

// --- Lernblätter -----------------------------------------------------------
export const listSheets = ({ courseId = null, sessionId = null } = {}) => {
  const params = new URLSearchParams();
  if (courseId) params.set('course_id', courseId);
  if (sessionId) params.set('session_id', sessionId);
  const suffix = params.toString();
  return apiGet(`/api/learn/sheets${suffix ? `?${suffix}` : ''}`);
};
export const createSheet = (body = {}) => apiPost('/api/learn/sheets', body);
export const updateSheet = (id, body = {}) => apiPatch(`/api/learn/sheets/${id}`, body);
export const deleteSheet = (id) => apiDelete(`/api/learn/sheets/${id}`);

// --- Karten ----------------------------------------------------------------
export const listCards = (sheetId) => apiGet(`/api/learn/sheets/${sheetId}/cards`);
export const createCard = (sheetId, body = {}) => apiPost(`/api/learn/sheets/${sheetId}/cards`, body);
export const updateCard = (id, body = {}) => apiPatch(`/api/learn/cards/${id}`, body);
export const deleteCard = (id) => apiDelete(`/api/learn/cards/${id}`);
