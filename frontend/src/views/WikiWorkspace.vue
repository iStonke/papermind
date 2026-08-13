<template>
  <main class="wiki-workspace">
    <header class="wiki-toolbar">
      <button type="button" class="wiki-toolbar__back" @click="$emit('show-chat')">
        <v-icon size="16">mdi-arrow-left</v-icon>
        Zum Chat
      </button>
      <nav class="wiki-toolbar__views" aria-label="Wissensbasis" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'pages'"
          :class="{ active: activeTab === 'pages' }"
          @click="activeTab = 'pages'"
        >Seiten</button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'review'"
          :class="{ active: activeTab === 'review' }"
          @click="activeTab = 'review'"
        >
          Zu prüfen
          <span v-if="overview.pending_proposals" class="wiki-review-count">{{ overview.pending_proposals }}</span>
        </button>
      </nav>
      <div class="wiki-toolbar__actions">
        <span class="wiki-trust-status" title="Nur Aussagen mit gültigem Originalbeleg werden für Antworten verwendet">
          <v-icon size="15">mdi-shield-check-outline</v-icon>
          {{ overview.active_claims }} belegt
        </span>
        <v-menu location="bottom end">
          <template #activator="{ props }">
            <v-btn v-bind="props" icon="mdi-dots-horizontal" size="small" variant="text" aria-label="Wissenswerkzeuge" />
          </template>
          <v-list density="compact" min-width="220">
            <v-list-item
              prepend-icon="mdi-shield-check-outline"
              title="Belege prüfen"
              :disabled="linting"
              @click="runLint"
            />
            <v-list-item
              prepend-icon="mdi-source-merge"
              title="Testlauf mit 20 Dokumenten"
              subtitle="Sicher prüfen, bevor der gesamte Bestand folgt"
              :disabled="backfillActive"
              @click="runBackfill({ documentLimit: 20 })"
            />
            <v-list-item
              prepend-icon="mdi-database-sync-outline"
              title="Alle Dokumente abgleichen"
              :disabled="backfillActive"
              @click="fullBackfillOpen = true"
            />
          </v-list>
        </v-menu>
      </div>
    </header>

    <v-alert
      v-if="notice"
      class="wiki-notice"
      :type="notice.type"
      variant="tonal"
      closable
      @click:close="notice = null"
    >{{ notice.message }}</v-alert>

    <section v-if="showBackfillProgress" class="wiki-backfill-progress" :class="`wiki-backfill-progress--${backfillRun.status}`">
      <div class="wiki-backfill-progress__head">
        <div class="wiki-backfill-progress__copy">
          <strong>{{ backfillProgressLabel }}</strong>
          <span v-if="backfillRun.status === 'queued'">Wartet auf freie Worker-Kapazität</span>
          <span v-else-if="backfillRun.status === 'running'">Ein Dokument nach dem anderen; Scans und Indexierung haben dazwischen Vorrang</span>
          <span v-else-if="backfillRun.status === 'paused'">Pausiert; das aktuell begonnene Dokument darf noch sauber abschließen</span>
          <span v-else>{{ backfillRun.error_message || 'Bestandsabgleich fehlgeschlagen' }}</span>
        </div>
        <div v-if="['queued', 'running', 'paused'].includes(backfillRun.status)" class="wiki-backfill-progress__actions">
          <v-btn
            v-if="backfillRun.status !== 'paused'"
            size="x-small"
            variant="text"
            prepend-icon="mdi-pause"
            :loading="controllingBackfill === 'pause'"
            @click="controlBackfill('pause')"
          >Pause</v-btn>
          <v-btn
            v-else
            size="x-small"
            variant="text"
            prepend-icon="mdi-play"
            :loading="controllingBackfill === 'resume'"
            @click="controlBackfill('resume')"
          >Fortsetzen</v-btn>
          <v-btn
            size="x-small"
            variant="text"
            color="error"
            :loading="controllingBackfill === 'cancel'"
            @click="controlBackfill('cancel')"
          >Abbrechen</v-btn>
        </div>
      </div>
      <v-progress-linear
        :model-value="backfillRun.progress || 0"
        :indeterminate="backfillRun.status === 'queued' && !backfillRun.total_documents"
        height="7"
        rounded
        color="primary"
      />
    </section>

    <section v-if="activeTab === 'pages'" class="wiki-browser">
      <aside class="wiki-nav">
        <div class="wiki-nav__head">
          <div class="wiki-nav__title">
            <span>Wissen</span>
            <small>{{ overview.active_claims }} Fakten</small>
          </div>
          <v-text-field
            v-model="search"
            prepend-inner-icon="mdi-magnify"
            placeholder="Wissen durchsuchen"
            variant="outlined"
            density="compact"
            clearable
            hide-details
            @update:model-value="scheduleSearch"
          />
          <button
            type="button"
            class="wiki-nav__filter"
            :aria-pressed="hideEmptyPages"
            @click="hideEmptyPages = !hideEmptyPages"
          >
            <span class="wiki-nav__switch" :class="{ 'wiki-nav__switch--on': hideEmptyPages }"></span>
            Nur befüllte anzeigen
          </button>
        </div>

        <div class="wiki-nav__scroll">
          <button
            type="button"
            class="wiki-home-link"
            :class="{ active: showHome }"
            @click="goHome"
          >
            <span class="wiki-home-link__ic"><v-icon size="17">mdi-view-dashboard-outline</v-icon></span>
            <span class="wiki-home-link__t">
              <strong>Überblick</strong>
              <small>Zuhause der Wissensbasis</small>
            </span>
          </button>

          <div v-if="loadingPages && !pages.length" class="wiki-loading"><v-progress-circular indeterminate size="24" /></div>

          <template v-for="group in groupedPages" :key="group.key">
            <div class="wiki-nav-group">{{ group.label }} <span>{{ group.pages.length }}</span></div>
            <button
              v-for="page in group.pages"
              :key="page.id"
              type="button"
              class="wiki-knav"
              :class="{ active: selectedPageId === page.id }"
              @click="openPage(page.id)"
            >
              <span class="wiki-knav__ic" :class="`wiki-knav__ic--${group.key}`"><v-icon size="16">{{ kindIcon(page.kind) }}</v-icon></span>
              <span class="wiki-knav__t">
                <strong>{{ page.title }}</strong>
                <small>{{ page.active_claim_count }} {{ page.active_claim_count === 1 ? 'Fakt' : 'Fakten' }}</small>
              </span>
              <span class="wiki-status-dot" :class="`wiki-status-dot--${page.status}`" :title="statusLabel(page.status)" />
            </button>
          </template>

          <div v-if="!loadingPages && !visiblePages.length" class="wiki-empty-list">
            Noch keine passende Wissensseite.
          </div>
          <div v-if="hideEmptyPages && hiddenEmptyCount > 0" class="wiki-nav-note">
            {{ hiddenEmptyCount }} leere {{ hiddenEmptyCount === 1 ? 'Seite' : 'Seiten' }} ausgeblendet
          </div>
          <button
            v-if="pages.length < pageTotal"
            type="button"
            class="wiki-load-more"
            :disabled="loadingPages"
            @click="loadPages({ append: true })"
          >{{ loadingPages ? 'Lädt …' : `Weitere laden (${pages.length} von ${pageTotal})` }}</button>
        </div>
      </aside>

      <article class="wiki-detail">
        <!-- ── Überblick (Zuhause) ── -->
        <div v-if="showHome" class="wiki-home">
          <div class="wiki-home__ask">
            <v-icon size="18" class="wiki-home__ask-ic">mdi-message-text-outline</v-icon>
            <span class="wiki-home__ask-text">Frag deine Unterlagen – z. B. „Welche Versicherungen habe ich?“</span>
            <v-btn size="small" color="primary" variant="tonal" @click="$emit('show-chat')">Zum Chat</v-btn>
          </div>

          <p class="wiki-home__knows">
            Deine Wissensbasis kennt <strong>{{ overview.active_claims }} belegte Fakten</strong><template v-if="overview.source_total"> aus <strong>{{ overview.source_coverage }}/{{ overview.source_total }} Dokumenten</strong></template> – jeder Fakt belegt und auf Klick zurück an die Stelle im Dokument.
          </p>

          <div v-if="homeClusters.length" class="wiki-cluster-grid">
            <button
              v-for="cluster in homeClusters"
              :key="cluster.key"
              type="button"
              class="wiki-cluster"
              @click="cluster.top && openPage(cluster.top.id)"
            >
              <div class="wiki-cluster__top">
                <span class="wiki-cluster__ic"><v-icon size="17">{{ groupIcon(cluster.key) }}</v-icon></span>
                <span class="wiki-cluster__title">{{ cluster.label }}</span>
                <span class="wiki-cluster__meta">{{ cluster.count }} · {{ cluster.facts }} Fakten</span>
              </div>
              <p v-if="cluster.top" class="wiki-cluster__lead">
                Meiste Fakten: <strong>{{ cluster.top.title }}</strong> ({{ cluster.top.active_claim_count }}).
              </p>
              <div class="wiki-cluster__chips">
                <span v-if="cluster.review" class="wiki-minichip wiki-minichip--warn">{{ cluster.review }} zu prüfen</span>
                <span v-if="cluster.conflict" class="wiki-minichip wiki-minichip--bad">{{ cluster.conflict }} Widerspruch</span>
                <span v-if="!cluster.review && !cluster.conflict" class="wiki-minichip wiki-minichip--ok">alle belegt</span>
              </div>
            </button>
          </div>
          <div v-else class="wiki-empty-detail wiki-home__empty">
            <v-icon size="34">mdi-brain</v-icon>
            <strong>Noch kein Wissen aufgebaut</strong>
            <span>Starte über das Menü einen Abgleich, damit PaperMind Fakten aus deinen Dokumenten extrahiert.</span>
          </div>

          <div v-if="attentionItems.length" class="wiki-attn">
            <div class="wiki-attn__head"><span class="wiki-attn__dot"></span>Braucht deine Aufmerksamkeit</div>
            <button
              v-for="item in attentionItems"
              :key="item.key"
              type="button"
              class="wiki-attn__row"
              @click="item.action()"
            >
              <span class="wiki-attn__pill" :class="`wiki-attn__pill--${item.tone}`">{{ item.count }}</span>
              <span class="wiki-attn__txt"><strong>{{ item.label }}</strong> <span>{{ item.hint }}</span></span>
              <v-icon size="18" class="wiki-attn__chev">mdi-chevron-right</v-icon>
            </button>
          </div>
          <div v-else-if="homeClusters.length" class="wiki-attn wiki-attn--clear">
            <v-icon size="17">mdi-check-circle-outline</v-icon>
            Alles geprüft – nichts braucht gerade deine Aufmerksamkeit.
          </div>
        </div>

        <div v-else-if="loadingDetail" class="wiki-detail__loading"><v-progress-circular indeterminate /></div>

        <template v-else-if="pageDetail">
          <header class="wiki-detail__header">
            <div class="wiki-detail__headmain">
              <div class="wiki-detail__meta">
                <span class="wiki-detail__kind">{{ kindLabel(pageDetail.kind) }}</span>
                <span class="wiki-state" :class="`wiki-state--${pageDetail.status}`">{{ statusLabel(pageDetail.status) }}</span>
              </div>
              <h2>{{ pageDetail.title }}</h2>
              <p>Revision {{ pageDetail.current_revision?.revision_number || '–' }} · aktualisiert {{ formatDate(pageDetail.updated_at) }}</p>
            </div>
            <v-btn
              v-if="pageDetail.source_document_id"
              size="small"
              variant="tonal"
              prepend-icon="mdi-open-in-new"
              @click="$emit('open-document', pageDetail.source_document_id)"
            >Original</v-btn>
          </header>

          <!-- ── Themen-Lens: Querschnitt über alle Dokumente ── -->
          <section v-if="isLensPage" class="wiki-lens">
            <div class="wiki-kpi-row">
              <div class="wiki-kpi"><div class="wiki-kpi__k">Fakten</div><div class="wiki-kpi__v">{{ pageDetail.claim_total || visibleClaims.length }}</div><div class="wiki-kpi__s">in dieser Lens</div></div>
              <div class="wiki-kpi"><div class="wiki-kpi__k">Belegt</div><div class="wiki-kpi__v">{{ activeClaimCount }}</div><div class="wiki-kpi__s">quellengesichert</div></div>
              <div class="wiki-kpi" :class="{ 'wiki-kpi--warn': claimNeedsReviewCount }"><div class="wiki-kpi__k">Zu prüfen</div><div class="wiki-kpi__v">{{ claimNeedsReviewCount }}</div><div class="wiki-kpi__s">Fakten bestätigen</div></div>
              <div class="wiki-kpi"><div class="wiki-kpi__k">Dokumente</div><div class="wiki-kpi__v">{{ lensDocumentCount }}</div><div class="wiki-kpi__s">Querschnitt</div></div>
            </div>

            <div class="wiki-claims__bar">
              <h3>Fakten quer durch deine Dokumente</h3>
              <div class="wiki-claim-filters">
                <button type="button" class="wiki-fbtn" :class="{ active: claimStatusFilter === 'all' }" @click="claimStatusFilter = 'all'">Alle <span>{{ visibleClaims.length }}</span></button>
                <button type="button" class="wiki-fbtn wiki-fbtn--warn" :class="{ active: claimStatusFilter === 'needs_review' }" @click="claimStatusFilter = 'needs_review'">Zu prüfen <span>{{ claimNeedsReviewCount }}</span></button>
              </div>
            </div>

            <div v-if="filteredDetailClaims.length" class="wiki-ltable-wrap">
              <div class="wiki-ltable">
                <div class="wiki-ltable__head">
                  <span class="wiki-ltable__c-fact">Fakt</span>
                  <span class="wiki-ltable__c-src">Quelle</span>
                  <span class="wiki-ltable__c-date">Datum</span>
                  <span class="wiki-ltable__c-status">Status</span>
                </div>
                <div
                  v-for="claim in filteredDetailClaims"
                  :key="claim.id"
                  class="wiki-ltable__row"
                  :class="`wiki-ltable__row--${claim.status}`"
                  role="button"
                  tabindex="0"
                  @click="firstSource(claim) && $emit('open-document', firstSource(claim).document_id)"
                  @keydown.enter="firstSource(claim) && $emit('open-document', firstSource(claim).document_id)"
                >
                  <span class="wiki-ltable__c-fact" :title="claim.text">{{ claim.text }}</span>
                  <span class="wiki-ltable__c-src">{{ firstSource(claim) ? (firstSource(claim).document_title || 'Dokument') : '—' }}</span>
                  <span class="wiki-ltable__c-date">{{ claim.valid_from ? formatDateShort(claim.valid_from) : '—' }}</span>
                  <span class="wiki-ltable__c-status"><span class="wiki-spill" :class="`wiki-spill--${claim.status}`">{{ claimStatusLabel(claim.status) }}</span></span>
                </div>
              </div>
            </div>

            <div v-else class="wiki-empty-detail">Keine passenden Fakten in dieser Lens.</div>
            <button
              v-if="visibleClaims.length < (pageDetail.claim_total || 0)"
              type="button"
              class="wiki-load-more wiki-load-more--claims"
              :disabled="loadingMoreClaims"
              @click="loadMoreClaims"
            >{{ loadingMoreClaims ? 'Lädt …' : `Weitere Fakten laden (${visibleClaims.length} von ${pageDetail.claim_total})` }}</button>
            <p class="wiki-lens__legend">Eine Lens bündelt Fakten quer durch alle Dokumente – anders als ein Dossier, das eine einzelne Person, Firma oder einen Vorgang zeigt.</p>
          </section>

          <!-- ── Dossier: eine Entität, Fakten nach Art gruppiert ── -->
          <section v-else class="wiki-dossier">
            <p class="wiki-dossier__profile">
              {{ kindLabel(pageDetail.kind) }} · {{ pageDetail.claim_total || visibleClaims.length }} {{ (pageDetail.claim_total || visibleClaims.length) === 1 ? 'Fakt' : 'Fakten' }}<template v-if="pageDetail.source_count"> aus {{ pageDetail.source_count }} {{ pageDetail.source_count === 1 ? 'Dokument' : 'Dokumenten' }}</template>. {{ activeClaimCount }} belegt<template v-if="claimNeedsReviewCount">, {{ claimNeedsReviewCount }} zu prüfen</template>.
            </p>

            <div class="wiki-steckbrief">
              <div v-for="cell in dossierMeta" :key="cell.k" class="wiki-steckbrief__cell">
                <span class="wiki-steckbrief__k">{{ cell.k }}</span>
                <span class="wiki-steckbrief__v">{{ cell.v }}</span>
              </div>
            </div>

            <div class="wiki-claims__bar">
              <h3>Fakten</h3>
              <div class="wiki-claim-filters">
                <button type="button" class="wiki-fbtn" :class="{ active: claimStatusFilter === 'all' }" @click="claimStatusFilter = 'all'">Alle <span>{{ visibleClaims.length }}</span></button>
                <button type="button" class="wiki-fbtn wiki-fbtn--warn" :class="{ active: claimStatusFilter === 'needs_review' }" @click="claimStatusFilter = 'needs_review'">Zu prüfen <span>{{ claimNeedsReviewCount }}</span></button>
              </div>
            </div>

            <div v-for="group in groupedClaims" :key="group.type" class="wiki-fgroup">
              <div class="wiki-fgroup__label">{{ group.label }} <span>{{ group.claims.length }}</span></div>
              <div class="wiki-factrows">
                <div v-for="claim in group.claims" :key="claim.id" class="wiki-factrow" :class="`wiki-factrow--${claim.status}`">
                  <span v-if="splitFact(claim.text).key" class="wiki-factrow__key">{{ splitFact(claim.text).key }}</span>
                  <span class="wiki-factrow__val" :class="{ 'wiki-factrow__val--full': !splitFact(claim.text).key }">{{ splitFact(claim.text).value }}</span>
                  <span class="wiki-spill" :class="`wiki-spill--${claim.status}`">{{ claimStatusLabel(claim.status) }}</span>
                  <a
                    v-if="firstSource(claim)"
                    href="#"
                    class="wiki-factrow__src"
                    :class="{ 'wiki-factrow__src--invalid': !firstSource(claim).valid }"
                    :title="firstSource(claim).quote"
                    @click.prevent="$emit('open-document', firstSource(claim).document_id)"
                  >Quelle · {{ firstSource(claim).document_title || 'Dokument' }}<template v-if="firstSource(claim).page_from">, S. {{ firstSource(claim).page_from }}</template></a>
                  <span v-else class="wiki-factrow__src wiki-factrow__src--none">keine Quelle</span>
                  <span class="wiki-factrow__acts">
                    <template v-if="claim.status !== 'active'">
                      <button type="button" class="wiki-qa wiki-qa--yes" title="Als belegt bestätigen" @click="confirmClaim(claim)">✓</button>
                      <button type="button" class="wiki-qa wiki-qa--no" title="Fakt zurückziehen" @click="retractClaim(claim)">✕</button>
                    </template>
                    <v-menu v-else location="bottom end">
                      <template #activator="{ props }">
                        <v-btn v-bind="props" size="x-small" variant="text" icon="mdi-dots-horizontal" aria-label="Fakt bearbeiten" />
                      </template>
                      <v-list density="compact" min-width="190">
                        <v-list-item prepend-icon="mdi-pencil-outline" title="Fakt korrigieren" @click="startCorrection(claim)" />
                        <v-list-item prepend-icon="mdi-delete-outline" title="Fakt zurückziehen" @click="retractClaim(claim)" />
                      </v-list>
                    </v-menu>
                  </span>
                </div>
              </div>
            </div>

            <div v-if="!filteredDetailClaims.length" class="wiki-empty-detail">
              {{ claimStatusFilter === 'needs_review' ? 'Nichts zu prüfen – alle Fakten hier sind belegt.' : 'Hier gibt es noch keine Fakten.' }}
            </div>
            <button
              v-if="visibleClaims.length < (pageDetail.claim_total || 0)"
              type="button"
              class="wiki-load-more wiki-load-more--claims"
              :disabled="loadingMoreClaims"
              @click="loadMoreClaims"
            >{{ loadingMoreClaims ? 'Lädt …' : `Weitere Fakten laden (${visibleClaims.length} von ${pageDetail.claim_total})` }}</button>

            <div v-if="dossierLinks.length || dossierTimeline.length" class="wiki-connect-grid">
              <div v-if="dossierLinks.length" class="wiki-connect-card">
                <div class="wiki-connect-card__label">Verbindungen</div>
                <button
                  v-for="link in dossierLinks"
                  :key="link.id"
                  type="button"
                  class="wiki-connect-row"
                  @click="openPage(link.linked_page_id)"
                >
                  <span class="wiki-connect-row__ic">{{ entityInitials(link.linked_page_title) }}</span>
                  <span class="wiki-connect-row__t">{{ link.linked_page_title }}</span>
                  <span class="wiki-connect-row__rel">{{ relationLabel(link.relation) }}</span>
                </button>
              </div>
              <div v-if="dossierTimeline.length" class="wiki-connect-card">
                <div class="wiki-connect-card__label">Zeitleiste</div>
                <div v-for="item in dossierTimeline" :key="item.id" class="wiki-timeline-row">
                  <span class="wiki-timeline-row__date">{{ formatDateShort(item.date) }}</span>
                  <span class="wiki-timeline-row__label">{{ item.label }}</span>
                </div>
              </div>
            </div>
          </section>
        </template>
      </article>
    </section>

    <section v-else class="wiki-review">
      <header class="wiki-review__header">
        <div><h2>Zu prüfen</h2><p>Nur bestätigte Vorschläge werden Teil deiner Wissensbasis.</p></div>
        <v-btn icon="mdi-refresh" size="small" variant="text" aria-label="Prüfkorb aktualisieren" :loading="loadingProposals" @click="loadProposals" />
      </header>
      <div v-if="loadingProposals" class="wiki-loading"><v-progress-circular indeterminate /></div>
      <article v-for="proposal in proposals" :key="proposal.id" class="wiki-proposal">
        <div class="wiki-proposal__icon"><v-icon>{{ proposal.proposal_type === 'chat_analysis' ? 'mdi-robot-outline' : 'mdi-alert-circle-outline' }}</v-icon></div>
        <div class="wiki-proposal__body">
          <span>{{ proposalTypeLabel(proposal.proposal_type) }} · {{ formatDate(proposal.created_at) }}</span>
          <h3>{{ proposal.payload?.title || proposalTitle(proposal) }}</h3>
          <p v-if="proposal.payload?.content" class="wiki-proposal__content">{{ proposal.payload.content }}</p>
          <ul v-else-if="proposal.payload?.claims?.length">
            <li v-for="claim in proposal.payload.claims" :key="claim.stable_key">{{ claim.text }}</li>
          </ul>
          <div v-if="proposal.validation_errors?.length" class="wiki-proposal__errors">
            Automatische Übernahme gesperrt: Der Originalbeleg fehlt oder stimmt nicht exakt.
          </div>
        </div>
        <div class="wiki-proposal__actions">
          <v-btn size="small" variant="text" :loading="reviewingId === proposal.id" @click="reviewProposal(proposal, 'reject')">Verwerfen</v-btn>
          <v-btn
            size="small"
            color="primary"
            variant="tonal"
            :disabled="Boolean(proposal.validation_errors?.length)"
            :loading="reviewingId === proposal.id"
            @click="reviewProposal(proposal, 'accept')"
          >{{ proposal.proposal_type === 'chat_analysis' ? 'Als Arbeitsnotiz behalten' : 'Übernehmen' }}</v-btn>
        </div>
      </article>
      <button
        v-if="proposals.length < proposalTotal"
        type="button"
        class="wiki-load-more wiki-load-more--review"
        :disabled="loadingProposals"
        @click="loadProposals({ append: true })"
      >{{ loadingProposals ? 'Lädt …' : `Weitere laden (${proposals.length} von ${proposalTotal})` }}</button>
      <div v-if="!loadingProposals && !proposals.length" class="wiki-review__empty">
        <v-icon size="34">mdi-check-circle-outline</v-icon><strong>Alles geprüft</strong><span>Der Prüfkorb ist leer.</span>
      </div>
    </section>

    <v-dialog v-model="correctionOpen" max-width="680">
      <v-card class="wiki-correction-card">
        <v-card-title>Aussage korrigieren</v-card-title>
        <v-card-subtitle>Die Korrektur erzeugt eine neue Revision; die bisherige Aussage bleibt in der Historie.</v-card-subtitle>
        <v-card-text>
          <v-textarea v-model="correction.text" label="Korrigierte Aussage" variant="outlined" rows="4" />
          <v-text-field v-model="correction.reason" label="Grund der Korrektur" variant="outlined" />
          <v-alert type="info" variant="tonal" density="compact">
            Die vorhandenen Originalzitate werden erneut validiert. Passt die neue Aussage nicht zum Beleg, wird sie abgewiesen.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="correctionOpen = false">Abbrechen</v-btn>
          <v-btn color="primary" :loading="savingCorrection" :disabled="!correction.text.trim() || correction.reason.trim().length < 3" @click="saveCorrection">Neue Revision speichern</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="fullBackfillOpen" max-width="520">
      <v-card class="wiki-correction-card">
        <v-card-title>Gesamten Bestand abgleichen?</v-card-title>
        <v-card-subtitle>Für große Bibliotheken sollte zuerst der Testlauf mit 20 Dokumenten erfolgreich sein.</v-card-subtitle>
        <v-card-text>
          PaperMind verarbeitet immer nur ein Dokument und gibt dem normalen Scan- und Indexbetrieb anschließend wieder Vorrang. Der Lauf kann jederzeit pausiert oder abgebrochen werden.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="fullBackfillOpen = false">Zurück</v-btn>
          <v-btn color="primary" @click="runBackfill()">Vollabgleich starten</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import {
  backfillWiki,
  controlWikiBackfill,
  correctWikiClaim,
  getWikiBackfillStatus,
  getWikiOverview,
  getWikiPage,
  lintWiki,
  listWikiPages,
  listWikiProposals,
  retractWikiClaim,
  reviewWikiProposal,
} from '../api/wiki.js';

defineEmits(['open-document', 'show-chat']);

const emptyOverview = () => ({ pages: 0, active_claims: 0, review_claims: 0, disputed_claims: 0, stale_claims: 0, pending_proposals: 0, source_coverage: 0, source_total: 0 });
const overview = ref(emptyOverview());
const pages = ref([]);
const pageTotal = ref(0);
const proposals = ref([]);
const proposalTotal = ref(0);
const pageDetail = ref(null);
const selectedPageId = ref(null);
const search = ref('');
const route = useRoute();
// Deep-Link aus dem Chat-Einstieg: ?tab=review öffnet direkt den Prüfkorb.
const activeTab = ref(route.query.tab === 'review' ? 'review' : 'pages');
const loadingPages = ref(false);
const loadingDetail = ref(false);
const loadingMoreClaims = ref(false);
const loadingProposals = ref(false);
const linting = ref(false);
const backfillRun = ref(null);
const controllingBackfill = ref(null);
const fullBackfillOpen = ref(false);
const reviewingId = ref(null);
const notice = ref(null);
let searchTimer = null;
let backfillPollTimer = null;

const PAGE_BATCH_SIZE = 100;
const PROPOSAL_BATCH_SIZE = 50;
const CLAIM_BATCH_SIZE = 100;

const correctionOpen = ref(false);
const savingCorrection = ref(false);
const correction = ref({ claim: null, text: '', reason: '' });

const visibleClaims = computed(() => pageDetail.value?.claims || []);

// ── Neue Informationsarchitektur: typisierte Navigation + Überblick ─────────────
// Seiten werden nach Art in nutzernahe Rubriken gruppiert statt in einer flachen
// Liste gezeigt. „source"-Seiten (einzelne Dokumente) landen unter „Dokumente".
const PAGE_GROUPS = [
  { key: 'beteiligte', label: 'Beteiligte', kinds: ['entity'] },
  { key: 'vorgaenge', label: 'Verträge & Vorgänge', kinds: ['contract'] },
  { key: 'themen', label: 'Themen', kinds: ['topic', 'timeline', 'comparison'] },
  { key: 'dokumente', label: 'Dokumente', kinds: ['source'] },
  { key: 'notizen', label: 'Arbeitsnotizen', kinds: ['analysis'] },
];
function groupKeyForKind(kind) {
  const group = PAGE_GROUPS.find((entry) => entry.kinds.includes(kind));
  return group ? group.key : 'dokumente';
}

const hideEmptyPages = ref(true);
const claimStatusFilter = ref('all'); // 'all' | 'needs_review'

const visiblePages = computed(() =>
  hideEmptyPages.value
    ? pages.value.filter((page) => (page.active_claim_count || 0) > 0)
    : pages.value,
);
const hiddenEmptyCount = computed(() => pages.value.length - visiblePages.value.length);
const groupedPages = computed(() => {
  const buckets = new Map(PAGE_GROUPS.map((group) => [group.key, []]));
  for (const page of visiblePages.value) buckets.get(groupKeyForKind(page.kind)).push(page);
  return PAGE_GROUPS
    .map((group) => ({ ...group, pages: buckets.get(group.key) }))
    .filter((group) => group.pages.length);
});

// Überblick ist der Standard-Landezustand (keine Seite gewählt).
const showHome = computed(() => !selectedPageId.value && !loadingDetail.value);
function goHome() {
  selectedPageId.value = null;
  pageDetail.value = null;
}

// Cluster-Kacheln des Überblicks – aus den geladenen Seiten abgeleitet.
const homeClusters = computed(() => {
  const buckets = new Map(PAGE_GROUPS.map((group) => [group.key, { ...group, count: 0, facts: 0, review: 0, conflict: 0, top: null }]));
  for (const page of pages.value) {
    if ((page.active_claim_count || 0) === 0) continue;
    const bucket = buckets.get(groupKeyForKind(page.kind));
    bucket.count += 1;
    bucket.facts += page.active_claim_count || 0;
    bucket.review += page.review_claim_count || 0;
    bucket.conflict += page.conflict_claim_count || 0;
    if (!bucket.top || (page.active_claim_count || 0) > (bucket.top.active_claim_count || 0)) bucket.top = page;
  }
  return PAGE_GROUPS.map((group) => buckets.get(group.key)).filter((bucket) => bucket.count > 0);
});

// Detail-Modus: Themen/Zeitachse/Vergleich werden als „Lens" (Quer-Dokumente)
// gerendert, alles andere als „Dossier".
const isLensPage = computed(() => ['topic', 'timeline', 'comparison'].includes(pageDetail.value?.kind));
const filteredDetailClaims = computed(() => {
  const claims = pageDetail.value?.claims || [];
  if (claimStatusFilter.value === 'needs_review') {
    return claims.filter((claim) => ['needs_review', 'disputed', 'stale'].includes(claim.status));
  }
  return claims;
});
const claimNeedsReviewCount = computed(() =>
  (pageDetail.value?.claims || []).filter((claim) => ['needs_review', 'disputed', 'stale'].includes(claim.status)).length,
);
// Dossier: Fakten nach Art gruppieren (belegt / von dir / abgeleitet).
const groupedClaims = computed(() => {
  const order = ['fact', 'user_assertion', 'inference'];
  const labels = { fact: 'Belegte Fakten', user_assertion: 'Von dir bestätigt', inference: 'Abgeleitet (KI-Schluss)' };
  const buckets = {};
  for (const claim of filteredDetailClaims.value) (buckets[claim.claim_type] ||= []).push(claim);
  return order
    .filter((type) => buckets[type]?.length)
    .map((type) => ({ type, label: labels[type], claims: buckets[type] }));
});
// Lens: Anzahl beteiligter Dokumente (aus den Belegen).
const lensDocumentCount = computed(() => {
  const ids = new Set();
  for (const claim of pageDetail.value?.claims || [])
    for (const evidence of claim.evidence || []) if (evidence.document_id) ids.add(evidence.document_id);
  return ids.size;
});
const activeClaimCount = computed(() =>
  (pageDetail.value?.claims || []).filter((claim) => claim.status === 'active').length,
);

// ── Dossier-Profil: aus echten Feldern abgeleitet ──────────────────────────────
function entityInitials(title) {
  const words = String(title || '').replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '·';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
// Viele extrahierte Fakten sind „Label: Wert" – daraus eine kompakte Key-Value-
// Zeile ableiten; ohne sauberes Muster bleibt der ganze Text der Wert.
function splitFact(text) {
  const value = String(text || '').trim();
  const idx = value.indexOf(': ');
  if (idx > 0 && idx <= 34 && !value.slice(0, idx).includes('.')) {
    return { key: value.slice(0, idx), value: value.slice(idx + 2) };
  }
  return { key: '', value };
}
function relationLabel(relation) {
  return ({
    about_topic: 'Thema',
    describes_contract: 'Vorgang',
    mentions_entity: 'Beteiligter',
    part_of: 'Teil von',
    references: 'Verweis',
    same_as: 'Dublette',
    source_of: 'Quelle',
  })[relation] || 'verknüpft';
}
function firstSource(claim) {
  const evidence = claim?.evidence || [];
  return evidence.find((item) => item.valid) || evidence[0] || null;
}
const dossierMeta = computed(() => {
  const page = pageDetail.value;
  if (!page) return [];
  const total = page.claim_total || visibleClaims.value.length;
  return [
    { k: 'Art', v: kindLabel(page.kind) },
    { k: 'Dokumente', v: `${page.source_count || 0} ${page.source_count === 1 ? 'Dokument' : 'Dokumente'}` },
    { k: 'Belegt', v: `${activeClaimCount.value} von ${total}` },
    { k: 'Zuletzt', v: formatDate(page.updated_at) },
  ];
});
const dossierLinks = computed(() => pageDetail.value?.links || []);
const dossierTimeline = computed(() => {
  const out = [];
  for (const claim of pageDetail.value?.claims || []) {
    if (claim.valid_from) out.push({ id: claim.id, date: claim.valid_from, label: splitFact(claim.text).key || claim.text });
  }
  return out.sort((a, b) => String(a.date).localeCompare(String(b.date)));
});

// Inline-„bestätigen": eine Korrektur mit identischem Text + Lock. Der Beleg wird
// dabei erneut validiert; passt er, gilt der Fakt als vom Nutzer belegt.
async function confirmClaim(claim) {
  if (!claim || !pageDetail.value?.current_revision_id) return;
  try {
    const page = await correctWikiClaim(claim.id, {
      expected_revision_id: pageDetail.value.current_revision_id,
      corrected_text: claim.text,
      subject: claim.subject,
      predicate: claim.predicate,
      object_text: claim.object_text,
      claim_type: claim.claim_type,
      valid_from: claim.valid_from,
      valid_to: claim.valid_to,
      evidence: (claim.evidence || []).filter((item) => item.valid).map((item) => ({ document_id: item.document_id, chunk_id: item.chunk_id, quote: item.quote, support_role: item.support_role })),
      lock_after_correction: true,
      reason: 'Vom Nutzer bestätigt',
    });
    if (page.id === selectedPageId.value) pageDetail.value = page;
    else await openPage(selectedPageId.value);
    notice.value = { type: 'success', message: 'Fakt als belegt bestätigt.' };
    await Promise.all([loadOverview(), loadPages()]);
  } catch (error) {
    notice.value = { type: 'error', message: errorMessage(error, 'Fakt konnte nicht bestätigt werden – der Beleg passt nicht mehr exakt.') };
  }
}

const backfillActive = computed(() => ['queued', 'running', 'paused'].includes(backfillRun.value?.status));
const showBackfillProgress = computed(() => ['queued', 'running', 'paused', 'failed'].includes(backfillRun.value?.status));
const backfillProgressLabel = computed(() => {
  const run = backfillRun.value;
  if (!run) return '';
  const label = run.document_limit ? 'Testlauf' : 'Bestandsabgleich';
  return `${label} · ${run.processed_documents} von ${run.total_documents} Dokumenten geprüft · ${run.progress || 0} %`;
});

function kindLabel(value) { return ({ source: 'Quelle', entity: 'Person / Firma', contract: 'Vertrag', topic: 'Thema', timeline: 'Zeitachse', comparison: 'Vergleich', analysis: 'Arbeitsanalyse' })[value] || value; }
function kindIcon(value) { return ({ source: 'mdi-file-document-outline', entity: 'mdi-account-outline', contract: 'mdi-lock-outline', topic: 'mdi-tag-outline', timeline: 'mdi-timeline-text-outline', comparison: 'mdi-source-merge', analysis: 'mdi-robot-outline' })[value] || 'mdi-note-outline'; }
function groupIcon(key) { return ({ beteiligte: 'mdi-account-multiple-outline', vorgaenge: 'mdi-file-sign', themen: 'mdi-tag-multiple-outline', dokumente: 'mdi-file-document-multiple-outline', notizen: 'mdi-robot-outline' })[key] || 'mdi-folder-outline'; }

// Überblick-Streifen „Braucht deine Aufmerksamkeit" – aus dem Overview abgeleitet.
const attentionItems = computed(() => {
  const data = overview.value || {};
  const items = [];
  if (data.pending_proposals) items.push({ key: 'proposals', tone: 'warn', count: data.pending_proposals, label: 'Zu prüfen', hint: 'Vorschläge warten auf deine Bestätigung', action: () => { activeTab.value = 'review'; } });
  if (data.disputed_claims) items.push({ key: 'disputed', tone: 'bad', count: data.disputed_claims, label: 'Widersprüche', hint: 'Fakten stehen im Konflikt – Belege prüfen', action: () => runLint() });
  if (data.stale_claims) items.push({ key: 'stale', tone: 'warn', count: data.stale_claims, label: 'Veraltete Belege', hint: 'Die Quelle hat sich geändert', action: () => runLint() });
  return items;
});
function statusLabel(value) { return ({ active: 'Aktuell', needs_review: 'Zu prüfen', stale: 'Veraltet', archived: 'Archiviert' })[value] || value; }
function claimStatusLabel(value) { return ({ active: 'belegt', needs_review: 'zu prüfen', disputed: 'strittig', superseded: 'ersetzt', retracted: 'zurückgezogen', stale: 'veraltet' })[value] || value; }
function proposalTypeLabel(value) { return ({ chat_analysis: 'Arbeitsnotiz aus Wissen', unverified_document_claims: 'Unbelegter Dokumentvorschlag', document_compile: 'Dokument-Compiler' })[value] || 'Wissensvorschlag'; }
function proposalTitle(proposal) { return proposal.payload?.claims?.[0]?.subject || `${proposal.payload?.claims?.length || 0} vorgeschlagene Aussagen`; }
function formatDate(value) { if (!value) return '–'; return new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); }
function formatDateShort(value) { if (!value) return '–'; return new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(new Date(value)); }
function errorMessage(error, fallback) { return error?.message || fallback; }

async function loadOverview() {
  try { overview.value = await getWikiOverview(); } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Wissensstatus konnte nicht geladen werden.') }; }
}
async function loadPages({ selectFirst = false, append = false } = {}) {
  loadingPages.value = true;
  try {
    const offset = append ? pages.value.length : 0;
    const result = await listWikiPages({
      q: search.value.trim() || undefined,
      limit: PAGE_BATCH_SIZE,
      offset,
    });
    const incoming = result.items || [];
    pages.value = append
      ? [...new Map([...pages.value, ...incoming].map((page) => [page.id, page])).values()]
      : incoming;
    pageTotal.value = result.total || 0;
    if (selectFirst && !selectedPageId.value && pages.value.length) await openPage(pages.value[0].id);
    if (!append && selectedPageId.value && !pages.value.some((page) => page.id === selectedPageId.value)) {
      selectedPageId.value = null;
      pageDetail.value = null;
    }
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Wissensseiten konnten nicht geladen werden.') }; }
  finally { loadingPages.value = false; }
}
async function openPage(pageId) {
  selectedPageId.value = pageId;
  loadingDetail.value = true;
  try { pageDetail.value = await getWikiPage(pageId, { claimLimit: CLAIM_BATCH_SIZE }); }
  catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Wissensseite konnte nicht geladen werden.') }; }
  finally { loadingDetail.value = false; }
}
async function loadMoreClaims() {
  if (!pageDetail.value || loadingMoreClaims.value) return;
  loadingMoreClaims.value = true;
  try {
    const currentPageId = pageDetail.value.id;
    const result = await getWikiPage(currentPageId, {
      claimLimit: CLAIM_BATCH_SIZE,
      claimOffset: pageDetail.value.claims.length,
    });
    if (pageDetail.value?.id === currentPageId) {
      pageDetail.value = {
        ...result,
        claims: [...new Map([...pageDetail.value.claims, ...(result.claims || [])].map((claim) => [claim.id, claim])).values()],
      };
    }
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Weitere Aussagen konnten nicht geladen werden.') }; }
  finally { loadingMoreClaims.value = false; }
}
function scheduleSearch() { window.clearTimeout(searchTimer); searchTimer = window.setTimeout(() => loadPages(), 220); }

async function loadProposals({ append = false } = {}) {
  loadingProposals.value = true;
  try {
    const result = await listWikiProposals({
      limit: PROPOSAL_BATCH_SIZE,
      offset: append ? proposals.value.length : 0,
    });
    const incoming = result.items || [];
    proposals.value = append
      ? [...new Map([...proposals.value, ...incoming].map((proposal) => [proposal.id, proposal])).values()]
      : incoming;
    proposalTotal.value = result.total || 0;
  }
  catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Prüfkorb konnte nicht geladen werden.') }; }
  finally { loadingProposals.value = false; }
}
async function reviewProposal(proposal, action) {
  reviewingId.value = proposal.id;
  try {
    await reviewWikiProposal(proposal.id, { action, note: action === 'accept' ? 'In PaperMind geprüft' : 'Nicht als verlässliches Wissen übernommen' });
    notice.value = { type: 'success', message: action === 'accept' ? 'Vorschlag übernommen.' : 'Vorschlag verworfen.' };
    await Promise.all([loadProposals(), loadOverview(), loadPages()]);
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Vorschlag konnte nicht geprüft werden.') }; }
  finally { reviewingId.value = null; }
}
async function runLint() {
  linting.value = true;
  try {
    const result = await lintWiki({ fix: true });
    notice.value = { type: result.issues.length ? 'warning' : 'success', message: `${result.checked_claims} Aussagen geprüft, ${result.fixed_claims} unsichere Aussagen deaktiviert, ${result.issues.length} Hinweise.` };
    await Promise.all([loadOverview(), loadPages()]);
    if (selectedPageId.value) await openPage(selectedPageId.value);
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Wissensprüfung fehlgeschlagen.') }; }
  finally { linting.value = false; }
}
async function runBackfill({ documentLimit } = {}) {
  try {
    backfillRun.value = await backfillWiki({ batchSize: 1, documentLimit });
    fullBackfillOpen.value = false;
    const runLabel = documentLimit ? 'Testlauf' : 'Bestandsabgleich';
    notice.value = { type: 'info', message: `${runLabel} für ${backfillRun.value.total_documents} Dokumente eingeplant. Er läuft kontrolliert im Hintergrund.` };
    scheduleBackfillPoll();
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Dokumente konnten nicht ins Wiki eingelesen werden.') }; }
}

async function controlBackfill(action) {
  if (!backfillRun.value?.id || controllingBackfill.value) return;
  controllingBackfill.value = action;
  try {
    backfillRun.value = await controlWikiBackfill(backfillRun.value.id, action);
    notice.value = {
      type: action === 'cancel' ? 'warning' : 'info',
      message: ({ pause: 'Bestandsabgleich wird nach dem aktuellen Dokument pausiert.', resume: 'Bestandsabgleich wird fortgesetzt.', cancel: 'Bestandsabgleich wurde abgebrochen.' })[action],
    };
    if (action === 'cancel') await Promise.all([loadOverview(), loadPages(), loadProposals()]);
    scheduleBackfillPoll();
  } catch (error) {
    notice.value = { type: 'error', message: errorMessage(error, 'Bestandsabgleich konnte nicht gesteuert werden.') };
  } finally { controllingBackfill.value = null; }
}

function scheduleBackfillPoll() {
  window.clearTimeout(backfillPollTimer);
  if (backfillActive.value) {
    const delay = backfillRun.value?.status === 'paused' ? 5000 : 1800;
    backfillPollTimer = window.setTimeout(() => loadBackfillStatus(), delay);
  }
}

async function loadBackfillStatus() {
  const previousStatus = backfillRun.value?.status;
  try {
    backfillRun.value = await getWikiBackfillStatus();
    const currentStatus = backfillRun.value?.status;
    if (previousStatus && previousStatus !== currentStatus && ['done', 'failed', 'cancelled'].includes(currentStatus)) {
      const run = backfillRun.value;
      notice.value = {
        type: currentStatus === 'done' && !run.failed_documents ? 'success' : 'warning',
        message: currentStatus === 'done'
          ? `${run.processed_documents} Dokumente geprüft, ${run.updated_documents} aktualisiert, ${run.failed_documents} Fehler.`
          : currentStatus === 'cancelled'
            ? 'Bestandsabgleich wurde abgebrochen.'
            : (run.error_message || 'Bestandsabgleich fehlgeschlagen.'),
      };
      await Promise.all([loadOverview(), loadPages(), loadProposals()]);
    }
  } catch (error) {
    notice.value = { type: 'error', message: errorMessage(error, 'Fortschritt des Bestandsabgleichs konnte nicht geladen werden.') };
  } finally { scheduleBackfillPoll(); }
}

async function startCorrection(claim) {
  let expectedRevisionId = pageDetail.value?.current_revision_id || claim.revision_id;
  if (claim.page_id !== pageDetail.value?.id) {
    try {
      const sourcePage = await getWikiPage(claim.page_id);
      expectedRevisionId = sourcePage.current_revision_id;
    } catch (error) {
      notice.value = { type: 'error', message: errorMessage(error, 'Quellseite der Aussage konnte nicht geladen werden.') };
      return;
    }
  }
  correction.value = {
    claim,
    expectedRevisionId,
    text: claim.evidence.find((item) => item.valid)?.quote || claim.text,
    reason: '',
  };
  correctionOpen.value = true;
}
async function saveCorrection() {
  const claim = correction.value.claim;
  if (!claim || !pageDetail.value?.current_revision_id) return;
  savingCorrection.value = true;
  try {
    const correctedPage = await correctWikiClaim(claim.id, {
      expected_revision_id: correction.value.expectedRevisionId,
      corrected_text: correction.value.text.trim(),
      subject: claim.subject,
      predicate: claim.predicate,
      object_text: claim.object_text,
      claim_type: claim.claim_type,
      valid_from: claim.valid_from,
      valid_to: claim.valid_to,
      evidence: claim.evidence.filter((item) => item.valid).map((item) => ({ document_id: item.document_id, chunk_id: item.chunk_id, quote: item.quote, support_role: item.support_role })),
      lock_after_correction: true,
      reason: correction.value.reason.trim(),
    });
    if (correctedPage.id === selectedPageId.value) pageDetail.value = correctedPage;
    else await openPage(selectedPageId.value);
    correctionOpen.value = false;
    notice.value = { type: 'success', message: 'Korrektur als neue Revision gespeichert.' };
    await Promise.all([loadOverview(), loadPages()]);
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Korrektur passt nicht zu den angegebenen Originalbelegen.') }; }
  finally { savingCorrection.value = false; }
}
async function retractClaim(claim) {
  const reason = window.prompt('Warum soll diese Aussage zurückgezogen werden?', 'Sachlich nicht mehr gültig');
  if (!reason || reason.trim().length < 3 || !pageDetail.value?.current_revision_id) return;
  try {
    const sourcePage = claim.page_id === pageDetail.value.id ? pageDetail.value : await getWikiPage(claim.page_id);
    const retractedPage = await retractWikiClaim(claim.id, { expected_revision_id: sourcePage.current_revision_id, reason: reason.trim() });
    if (retractedPage.id === selectedPageId.value) pageDetail.value = retractedPage;
    else await openPage(selectedPageId.value);
    notice.value = { type: 'success', message: 'Aussage zurückgezogen; die Historie bleibt erhalten.' };
    await Promise.all([loadOverview(), loadPages()]);
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error, 'Aussage konnte nicht zurückgezogen werden.') }; }
}

watch(activeTab, (value) => { if (value === 'review') void loadProposals(); });
onMounted(async () => {
  await Promise.all([loadOverview(), loadProposals(), loadBackfillStatus()]);
  await loadPages();
});
onBeforeUnmount(() => {
  window.clearTimeout(searchTimer);
  window.clearTimeout(backfillPollTimer);
});
</script>

<style scoped>
.wiki-workspace {
  grid-column: 2 / -1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  color: var(--pm-text);
  background: var(--pm-content-surface);
}

.wiki-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  min-height: 57px;
  padding: 8px 14px 8px 18px;
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-app-surface-raised);
}

.wiki-toolbar__back {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 5px 11px 5px 8px;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.14s ease, border-color 0.14s ease;
}

.wiki-toolbar__back:hover {
  color: var(--pm-text);
  border-color: color-mix(in srgb, var(--pm-accent) 40%, var(--pm-divider));
}

.wiki-toolbar__views {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--pm-divider);
  border-radius: 10px;
  background: var(--pm-control-surface, var(--pm-viewer-surface));
}

.wiki-toolbar__views button {
  min-height: 29px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border: 0;
  border-radius: 7px;
  color: var(--pm-muted);
  background: transparent;
  font: inherit;
  font-size: 0.72rem;
  font-weight: 650;
  cursor: pointer;
}

.wiki-toolbar__views button:hover {
  color: var(--pm-text);
  background: var(--pm-row-hover);
}

.wiki-toolbar__views button.active {
  color: var(--pm-text);
  background: var(--pm-app-surface-raised);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.09);
}

.wiki-toolbar__actions,
.wiki-trust-status {
  display: flex;
  align-items: center;
}

.wiki-toolbar__actions {
  justify-content: flex-end;
  gap: 4px;
}

.wiki-trust-status {
  gap: 5px;
  padding: 5px 8px;
  border-radius: 8px;
  color: var(--pm-muted);
  background: color-mix(in srgb, rgb(var(--v-theme-success)) 8%, transparent);
  font-size: 0.66rem;
  font-weight: 650;
}

.wiki-trust-status .v-icon {
  color: rgb(var(--v-theme-success));
}

.wiki-review-count {
  min-width: 18px;
  padding: 1px 5px;
  border-radius: 999px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
  font-size: 0.58rem;
  font-weight: 800;
  text-align: center;
}

.wiki-notice,
.wiki-backfill-progress {
  flex: none;
  width: calc(100% - 28px);
  margin: 10px 14px 0;
}

.wiki-backfill-progress {
  display: grid;
  gap: 7px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-primary), 0.22);
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.06);
}

.wiki-backfill-progress__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-size: 0.68rem;
}

.wiki-backfill-progress__copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.wiki-backfill-progress__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: none;
}

.wiki-backfill-progress span {
  color: var(--pm-muted);
}

.wiki-backfill-progress--paused {
  border-color: rgba(var(--v-theme-warning), 0.28);
  background: rgba(var(--v-theme-warning), 0.07);
}

.wiki-backfill-progress--failed {
  border-color: rgba(var(--v-theme-error), 0.3);
  background: rgba(var(--v-theme-error), 0.07);
}

.wiki-browser,
.wiki-review {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--pm-content-surface);
}

.wiki-browser {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
}

/* ── Typisierte Navigation ── */
.wiki-nav {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--pm-divider);
  background: var(--pm-app-surface-raised);
}

.wiki-nav__head {
  flex: none;
  display: grid;
  gap: 9px;
  padding: 12px 12px 11px;
  border-bottom: 1px solid var(--pm-divider);
}

.wiki-nav__title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  color: var(--pm-text);
  font-size: 0.82rem;
  font-weight: 700;
}

.wiki-nav__title small {
  color: var(--pm-muted);
  font-size: 0.64rem;
  font-weight: 600;
}

.wiki-nav :deep(.v-field) {
  border-radius: 9px;
  color: var(--pm-text);
  background: var(--pm-content-surface);
}

.wiki-nav :deep(.v-field__outline) {
  color: var(--pm-divider);
}

.wiki-nav__filter {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 2px;
  border: 0;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.68rem;
  font-weight: 550;
  cursor: pointer;
}

.wiki-nav__switch {
  position: relative;
  width: 28px;
  height: 16px;
  flex: none;
  border-radius: 999px;
  background: var(--pm-divider);
  transition: background-color 0.15s ease;
}

.wiki-nav__switch::after {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.15s ease;
}

.wiki-nav__switch--on {
  background: var(--pm-accent);
}

.wiki-nav__switch--on::after {
  transform: translateX(12px);
}

.wiki-nav__scroll {
  min-height: 0;
  overflow: auto;
  padding: 8px 8px 16px;
}

.wiki-home-link {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 4px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.14s ease, border-color 0.14s ease;
}

.wiki-home-link:hover {
  background: var(--pm-row-hover);
}

.wiki-home-link.active {
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 30%, transparent);
}

.wiki-home-link__ic {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: 8px;
  color: #04211f;
  background: var(--pm-accent);
}

.wiki-home-link__t {
  min-width: 0;
  display: grid;
}

.wiki-home-link__t strong {
  color: var(--pm-text);
  font-size: 0.78rem;
  font-weight: 650;
}

.wiki-home-link__t small {
  color: var(--pm-muted);
  font-size: 0.63rem;
}

.wiki-nav-group {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 15px 10px 5px;
  color: var(--pm-muted);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.wiki-nav-group span {
  opacity: 0.7;
}

.wiki-knav {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 48px;
  margin-top: 2px;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.14s ease, border-color 0.14s ease;
}

.wiki-knav:hover {
  background: var(--pm-row-hover);
}

.wiki-knav.active {
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 28%, transparent);
}

.wiki-knav__ic {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: none;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  color: var(--pm-muted);
  background: var(--pm-content-surface);
}

.wiki-knav__ic--beteiligte,
.wiki-knav__ic--themen {
  color: var(--pm-accent);
  border-color: color-mix(in srgb, var(--pm-accent) 26%, var(--pm-divider));
  background: color-mix(in srgb, var(--pm-accent) 8%, var(--pm-content-surface));
}

.wiki-knav__t {
  min-width: 0;
  flex: 1;
}

.wiki-knav__t strong,
.wiki-knav__t small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-knav__t strong {
  color: var(--pm-text);
  font-size: 0.76rem;
  font-weight: 620;
}

.wiki-knav__t small {
  margin-top: 2px;
  color: var(--pm-muted);
  font-size: 0.63rem;
}

.wiki-nav-note {
  margin: 12px 4px 0;
  padding: 9px 10px;
  border: 1px dashed var(--pm-divider);
  border-radius: 9px;
  color: var(--pm-muted);
  font-size: 0.64rem;
  text-align: center;
}

.wiki-status-dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--pm-muted);
}

.wiki-status-dot--active {
  background: rgb(var(--v-theme-success));
}

.wiki-status-dot--needs_review {
  background: rgb(var(--v-theme-warning));
}

.wiki-status-dot--stale,
.wiki-status-dot--archived {
  background: rgb(var(--v-theme-error));
}

.wiki-detail {
  min-width: 0;
  min-height: 0;
  padding: 28px clamp(22px, 4vw, 58px) 48px;
  overflow: auto;
  background: var(--pm-content-surface);
}

.wiki-detail__loading,
.wiki-loading {
  display: grid;
  place-items: center;
  min-height: 180px;
}

.wiki-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  max-width: 880px;
  margin: 0 auto;
  padding-bottom: 19px;
  border-bottom: 1px solid var(--pm-divider);
}

.wiki-detail__header h2 {
  margin: 6px 0 5px;
  color: var(--pm-text);
  font-size: 1.38rem;
  letter-spacing: -0.025em;
}

.wiki-detail__header p,
.wiki-review header p {
  margin: 0;
  color: var(--pm-muted);
  font-size: 0.67rem;
}

.wiki-detail__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--pm-muted);
  font-size: 0.66rem;
}

.wiki-state {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--pm-row-hover);
  color: var(--pm-muted);
  font-size: 0.59rem;
  font-weight: 750;
}

.wiki-state--active {
  background: rgba(var(--v-theme-success), .13);
  color: var(--pm-text);
}

.wiki-state--needs_review {
  background: rgba(var(--v-theme-warning), .15);
  color: var(--pm-text);
}

.wiki-state--disputed,
.wiki-state--stale,
.wiki-state--archived {
  background: rgba(var(--v-theme-error), .13);
  color: var(--pm-text);
}

.wiki-claims {
  max-width: 880px;
  margin: 22px auto 0;
}

.wiki-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.wiki-section-title h3 {
  margin: 0;
  color: var(--pm-text);
  font-size: 0.8rem;
}

.wiki-section-title span {
  color: var(--pm-muted);
  font-size: 0.64rem;
}

.wiki-claim {
  margin-bottom: 10px;
  padding: 14px 15px;
  border: 1px solid var(--pm-divider);
  border-radius: 11px;
  background: var(--pm-app-surface-raised);
  box-shadow: 0 4px 15px rgba(15, 23, 42, 0.035);
}

.wiki-claim--needs_review {
  border-color: rgba(var(--v-theme-warning), 0.32);
}

.wiki-claim--stale,
.wiki-claim--disputed {
  border-color: rgba(var(--v-theme-error), 0.32);
}

.wiki-claim__head {
  display: flex;
  align-items: center;
  gap: 7px;
}

.wiki-claim__spacer {
  flex: 1;
}

.wiki-claim__text {
  margin: 10px 0 0;
  color: var(--pm-text);
  font-size: 0.84rem;
  line-height: 1.55;
}

.wiki-evidence-disclosure {
  margin-top: 11px;
  border-top: 1px solid var(--pm-divider);
}

.wiki-evidence-disclosure summary {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 2px 0;
  color: var(--pm-muted);
  font-size: 0.66rem;
  font-weight: 650;
  cursor: pointer;
  list-style: none;
}

.wiki-evidence-disclosure summary::-webkit-details-marker {
  display: none;
}

.wiki-evidence-disclosure summary span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.wiki-evidence-disclosure__chevron {
  transition: transform 0.16s ease;
}

.wiki-evidence-disclosure[open] .wiki-evidence-disclosure__chevron {
  transform: rotate(180deg);
}

.wiki-evidence-list {
  display: grid;
  gap: 6px;
  padding-top: 4px;
}

.wiki-evidence {
  display: block;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: var(--pm-content-surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.wiki-evidence:hover {
  border-color: color-mix(in srgb, var(--pm-accent) 30%, var(--pm-divider));
  background: var(--pm-row-hover);
}

.wiki-evidence__source {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 4px;
  color: var(--pm-accent);
  font-size: 0.61rem;
  font-weight: 750;
}

.wiki-evidence q {
  display: block;
  color: var(--pm-muted);
  font-size: 0.68rem;
  line-height: 1.45;
}

.wiki-evidence--invalid {
  border-color: rgba(var(--v-theme-error), 0.22);
  background: rgba(var(--v-theme-error), 0.06);
}

.wiki-evidence__warning,
.wiki-no-evidence {
  display: block;
  margin-top: 5px;
  color: rgb(var(--v-theme-error));
  font-size: 0.61rem;
}

.wiki-load-more {
  width: 100%;
  margin-top: 8px;
  padding: 9px 12px;
  border: 1px solid var(--pm-divider);
  border-radius: 9px;
  background: transparent;
  color: var(--pm-accent);
  font: inherit;
  font-size: 0.7rem;
  font-weight: 700;
  cursor: pointer;
}

.wiki-load-more:hover {
  background: var(--pm-row-hover);
}

.wiki-load-more:disabled {
  opacity: .55;
  cursor: wait;
}

.wiki-load-more--claims {
  margin-top: 14px;
}

.wiki-load-more--review {
  display: block;
  max-width: 520px;
  margin: 14px auto 0;
}

.wiki-empty-detail,
.wiki-review__empty {
  display: flex;
  min-height: 280px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--pm-muted);
  font-size: 0.72rem;
  text-align: center;
}

.wiki-empty-detail strong,
.wiki-review__empty strong {
  color: var(--pm-text);
  font-size: 0.84rem;
}

.wiki-empty-list {
  padding: 30px 10px;
  color: var(--pm-muted);
  font-size: 0.7rem;
  text-align: center;
}

.wiki-review {
  padding: 28px clamp(18px, 4vw, 56px) 48px;
  overflow: auto;
}

.wiki-review__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  max-width: 900px;
  margin: 0 auto 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--pm-divider);
}

.wiki-review h2 {
  margin: 0 0 3px;
  color: var(--pm-text);
  font-size: 1.18rem;
  letter-spacing: -0.02em;
}

.wiki-proposal {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  max-width: 900px;
  margin: 0 auto 10px;
  padding: 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 11px;
  background: var(--pm-app-surface-raised);
}

.wiki-proposal__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.12);
}

.wiki-proposal__body > span {
  color: var(--pm-muted);
  font-size: 0.61rem;
}

.wiki-proposal__body h3 {
  margin: 3px 0 6px;
  color: var(--pm-text);
  font-size: 0.83rem;
}

.wiki-proposal__body p,
.wiki-proposal__body li {
  color: var(--pm-muted);
  font-size: 0.7rem;
  line-height: 1.45;
}

.wiki-proposal__content {
  max-height: 120px;
  overflow: auto;
  white-space: pre-wrap;
}

.wiki-proposal__errors {
  display: inline-block;
  margin-top: 6px;
  padding: 5px 8px;
  border-radius: 7px;
  background: rgba(var(--v-theme-error), 0.1);
  color: rgb(var(--v-theme-error));
  font-size: 0.61rem;
}

.wiki-proposal__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.wiki-correction-card {
  border-radius: 16px !important;
}

/* ── Detail-Kopf ── */
.wiki-detail__headmain {
  min-width: 0;
}

.wiki-detail__kind {
  font-weight: 650;
}

/* ── Überblick (Zuhause) ── */
.wiki-home {
  max-width: 880px;
  margin: 0 auto;
}

.wiki-home__ask {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  background: var(--pm-app-surface-raised);
  box-shadow: 0 4px 15px rgba(15, 23, 42, 0.035);
}

.wiki-home__ask-ic {
  flex: none;
  color: var(--pm-accent);
}

.wiki-home__ask-text {
  flex: 1;
  min-width: 0;
  color: var(--pm-muted);
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-home__knows {
  margin: 16px 2px 4px;
  color: var(--pm-muted);
  font-size: 0.86rem;
  line-height: 1.55;
}

.wiki-home__knows strong {
  color: var(--pm-text);
  font-weight: 650;
}

.wiki-home__empty {
  min-height: 200px;
}

.wiki-cluster-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

@media (max-width: 620px) {
  .wiki-cluster-grid { grid-template-columns: 1fr; }
}

.wiki-cluster {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 15px 16px;
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  background: var(--pm-app-surface-raised);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.wiki-cluster:hover {
  border-color: color-mix(in srgb, var(--pm-accent) 40%, var(--pm-divider));
  transform: translateY(-2px);
}

.wiki-cluster__top {
  display: flex;
  align-items: center;
  gap: 9px;
}

.wiki-cluster__ic {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: none;
  border-radius: 8px;
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--pm-accent) 26%, var(--pm-divider));
}

.wiki-cluster__title {
  color: var(--pm-text);
  font-size: 0.92rem;
  font-weight: 660;
  letter-spacing: -0.01em;
}

.wiki-cluster__meta {
  margin-left: auto;
  color: var(--pm-muted);
  font-family: var(--pm-font-mono, ui-monospace, "SFMono-Regular", Menlo, monospace);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}

.wiki-cluster__lead {
  margin: 0;
  color: var(--pm-muted);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.wiki-cluster__lead strong { color: var(--pm-text); font-weight: 600; }

.wiki-cluster__chips { display: flex; gap: 5px; flex-wrap: wrap; }

.wiki-minichip {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: 5px;
  font-size: 0.66rem;
  font-weight: 600;
}

.wiki-minichip--warn { color: var(--pm-text); background: rgba(var(--v-theme-warning), 0.16); }
.wiki-minichip--bad { color: var(--pm-text); background: rgba(var(--v-theme-error), 0.14); }
.wiki-minichip--ok { color: var(--pm-muted); background: rgba(var(--v-theme-success), 0.13); }

/* ── Statuschip (belegt / zu prüfen / verworfen …) ── */
.wiki-spill {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: 5px;
  font-size: 0.66rem;
  font-weight: 600;
  white-space: nowrap;
  background: var(--pm-row-hover);
  color: var(--pm-muted);
}

.wiki-spill--active { color: rgb(var(--v-theme-success)); background: rgba(var(--v-theme-success), 0.14); }
.wiki-spill--needs_review { color: rgb(var(--v-theme-warning)); background: rgba(var(--v-theme-warning), 0.16); }
.wiki-spill--disputed { color: rgb(var(--v-theme-error)); background: rgba(var(--v-theme-error), 0.14); }
.wiki-spill--stale,
.wiki-spill--superseded { color: rgb(var(--v-theme-warning)); background: rgba(var(--v-theme-warning), 0.13); }
.wiki-spill--retracted { color: rgb(var(--v-theme-error)); background: rgba(var(--v-theme-error), 0.12); }

/* ── Dossier: Profil + Steckbrief ── */
.wiki-dossier__profile {
  margin: 0 0 16px;
  max-width: 680px;
  color: var(--pm-muted);
  font-size: 0.95rem;
  line-height: 1.6;
}

.wiki-steckbrief {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin-bottom: 22px;
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  overflow: hidden;
  background: var(--pm-app-surface-raised);
}

.wiki-steckbrief__cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-right: 1px solid var(--pm-divider);
}

.wiki-steckbrief__cell:last-child { border-right: 0; }

.wiki-steckbrief__k {
  font-size: 0.6rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pm-muted);
}

.wiki-steckbrief__v { font-size: 0.84rem; color: var(--pm-text); }

@media (max-width: 640px) {
  .wiki-steckbrief { grid-template-columns: 1fr 1fr; }
  .wiki-steckbrief__cell:nth-child(2) { border-right: 0; }
}

/* ── Dossier: Key-Value-Faktenzeilen ── */
.wiki-factrows {
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  overflow: hidden;
  background: var(--pm-app-surface-raised);
}

.wiki-factrow {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 11px 16px;
  border-top: 1px solid var(--pm-divider);
}

.wiki-factrow:first-child { border-top: 0; }

.wiki-factrow--needs_review,
.wiki-factrow--disputed,
.wiki-factrow--stale { background: rgba(var(--v-theme-warning), 0.05); }

.wiki-factrow__key {
  width: 124px;
  flex: none;
  font-size: 0.72rem;
  color: var(--pm-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-factrow__val {
  flex: 1 1 auto;
  min-width: 96px;
  font-size: 0.84rem;
  color: var(--pm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-factrow__src {
  flex: 0 1 190px;
  min-width: 0;
  text-align: right;
  font-size: 0.72rem;
  color: var(--pm-accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wiki-factrow__src--invalid { color: rgb(var(--v-theme-error)); }
.wiki-factrow__src--none { color: var(--pm-muted); cursor: default; }

.wiki-factrow__acts {
  display: flex;
  gap: 5px;
  width: 62px;
  flex: none;
  justify-content: flex-end;
}

.wiki-qa {
  width: 26px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  border: 1px solid var(--pm-divider);
  background: var(--pm-content-surface);
  font-size: 0.85rem;
  cursor: pointer;
}

.wiki-qa--yes { color: rgb(var(--v-theme-success)); }
.wiki-qa--yes:hover { border-color: rgba(var(--v-theme-success), 0.5); background: rgba(var(--v-theme-success), 0.1); }
.wiki-qa--no { color: rgb(var(--v-theme-error)); }
.wiki-qa--no:hover { border-color: rgba(var(--v-theme-error), 0.5); background: rgba(var(--v-theme-error), 0.1); }

/* ── Dossier: Verbindungen + Zeitleiste ── */
.wiki-connect-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 22px;
}

@media (max-width: 640px) {
  .wiki-connect-grid { grid-template-columns: 1fr; }
}

.wiki-connect-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
  background: var(--pm-app-surface-raised);
}

.wiki-connect-card__label {
  font-size: 0.6rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pm-muted);
}

.wiki-connect-row {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  font-size: 0.84rem;
}

.wiki-connect-row__ic {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex: none;
  border-radius: 5px;
  background: color-mix(in srgb, var(--pm-accent) 10%, var(--pm-content-surface));
  border: 1px solid color-mix(in srgb, var(--pm-accent) 22%, var(--pm-divider));
  color: var(--pm-accent);
  font-family: var(--pm-font-mono, ui-monospace, "SFMono-Regular", Menlo, monospace);
  font-size: 0.6rem;
  font-weight: 700;
}

.wiki-connect-row__t {
  flex: 1;
  min-width: 0;
  color: var(--pm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-connect-row:hover .wiki-connect-row__t { color: var(--pm-accent); }
.wiki-connect-row__rel { flex: none; font-size: 0.72rem; color: var(--pm-muted); }

.wiki-timeline-row {
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 0.84rem;
  color: var(--pm-text);
}

.wiki-timeline-row__date {
  width: 92px;
  flex: none;
  font-family: var(--pm-font-mono, ui-monospace, "SFMono-Regular", Menlo, monospace);
  font-size: 0.72rem;
  color: var(--pm-muted);
}

/* ── Lens: Tabelle ── */
.wiki-ltable-wrap {
  overflow-x: auto;
  border: 1px solid var(--pm-divider);
  border-radius: 14px;
}

.wiki-ltable {
  min-width: 560px;
  background: var(--pm-app-surface-raised);
}

.wiki-ltable__head,
.wiki-ltable__row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 16px;
}

.wiki-ltable__head {
  border-bottom: 1px solid var(--pm-divider);
  background: var(--pm-content-surface);
  font-size: 0.6rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--pm-muted);
}

.wiki-ltable__row {
  border-top: 1px solid var(--pm-divider);
  font-size: 0.84rem;
  cursor: pointer;
}

.wiki-ltable__row:first-of-type { border-top: 0; }
.wiki-ltable__row:hover { background: var(--pm-row-hover); }
.wiki-ltable__row--needs_review,
.wiki-ltable__row--disputed,
.wiki-ltable__row--stale { background: rgba(var(--v-theme-warning), 0.05); }

.wiki-ltable__c-fact { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--pm-text); }
.wiki-ltable__c-src { width: 190px; flex: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--pm-accent); font-size: 0.76rem; }
.wiki-ltable__head .wiki-ltable__c-src { color: var(--pm-muted); }
.wiki-ltable__c-date { width: 96px; flex: none; text-align: right; font-family: var(--pm-font-mono, ui-monospace, "SFMono-Regular", Menlo, monospace); font-size: 0.74rem; color: var(--pm-muted); }
.wiki-ltable__c-status { width: 90px; flex: none; display: flex; justify-content: flex-end; }

.wiki-attn {
  margin-top: 20px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  overflow: hidden;
  background: var(--pm-app-surface-raised);
}

.wiki-attn__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-bottom: 1px solid var(--pm-divider);
  color: var(--pm-muted);
  font-size: 0.63rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.wiki-attn__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--v-theme-warning));
}

.wiki-attn__row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 11px 14px;
  border: 0;
  border-bottom: 1px solid var(--pm-divider);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.wiki-attn__row:last-child {
  border-bottom: 0;
}

.wiki-attn__row:hover {
  background: var(--pm-row-hover);
}

.wiki-attn__pill {
  flex: none;
  min-width: 26px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 700;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.wiki-attn__pill--warn {
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.14);
}

.wiki-attn__pill--bad {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.12);
}

.wiki-attn__txt {
  flex: 1;
  min-width: 0;
  color: var(--pm-text);
  font-size: 0.8rem;
  font-weight: 550;
}

.wiki-attn__txt span {
  color: var(--pm-muted);
  font-weight: 400;
}

.wiki-attn__chev {
  flex: none;
  color: var(--pm-muted);
}

.wiki-attn--clear {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 13px 14px;
  color: var(--pm-muted);
  font-size: 0.76rem;
}

.wiki-attn--clear .v-icon {
  color: rgb(var(--v-theme-success));
}

/* ── Dossier & Lens: Fakten-Leiste + Filter ── */
.wiki-dossier,
.wiki-lens {
  max-width: 880px;
  margin: 22px auto 0;
}

.wiki-claims__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.wiki-claims__bar h3 {
  margin: 0;
  color: var(--pm-text);
  font-size: 0.82rem;
}

.wiki-claim-filters {
  display: flex;
  gap: 6px;
}

.wiki-fbtn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.68rem;
  font-weight: 650;
  cursor: pointer;
}

.wiki-fbtn span {
  font-variant-numeric: tabular-nums;
}

.wiki-fbtn:hover {
  color: var(--pm-text);
}

.wiki-fbtn.active {
  color: var(--pm-accent);
  border-color: color-mix(in srgb, var(--pm-accent) 40%, var(--pm-divider));
  background: color-mix(in srgb, var(--pm-accent) 8%, transparent);
}

.wiki-fbtn--warn.active {
  color: rgb(var(--v-theme-warning));
  border-color: rgba(var(--v-theme-warning), 0.4);
  background: rgba(var(--v-theme-warning), 0.1);
}

/* ── Dossier: Faktengruppen ── */
.wiki-fgroup {
  margin-top: 16px;
}

.wiki-fgroup__label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--pm-muted);
  font-size: 0.63rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.wiki-fgroup__label span {
  opacity: 0.7;
}

/* ── Themen-Lens ── */
.wiki-kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.wiki-kpi {
  padding: 12px 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 11px;
  background: var(--pm-app-surface-raised);
}

.wiki-kpi__k {
  color: var(--pm-muted);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.wiki-kpi__v {
  margin-top: 6px;
  color: var(--pm-text);
  font-size: 1.35rem;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}

.wiki-kpi__s {
  margin-top: 4px;
  color: var(--pm-muted);
  font-size: 0.68rem;
}

.wiki-kpi--warn .wiki-kpi__v {
  color: rgb(var(--v-theme-warning));
}

.wiki-claim__srcchip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 220px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--pm-divider);
  background: var(--pm-content-surface);
  color: var(--pm-accent);
  font-size: 0.63rem;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wiki-claim__srcchip:hover {
  border-color: color-mix(in srgb, var(--pm-accent) 40%, var(--pm-divider));
}

.wiki-lens__legend {
  margin-top: 18px;
  color: var(--pm-muted);
  font-size: 0.7rem;
  line-height: 1.5;
}

@media (max-width: 1050px) {
  .wiki-browser {
    grid-template-columns: 250px minmax(0, 1fr);
  }

  .wiki-detail {
    padding: 20px;
  }
}

@media (max-width: 760px) {
  .wiki-workspace {
    grid-column: 1 / -1;
  }

  .wiki-toolbar {
    grid-template-columns: auto 1fr auto;
    gap: 8px;
    padding-inline: 14px;
  }

  .wiki-trust-status {
    display: none;
  }

  .wiki-toolbar__views button {
    padding-inline: 8px;
  }

  .wiki-backfill-progress__head {
    align-items: flex-start;
    flex-direction: column;
    gap: 7px;
  }

  .wiki-backfill-progress__actions {
    align-self: flex-end;
  }

  .wiki-browser {
    display: block;
    overflow: auto;
  }

  .wiki-nav {
    max-height: 300px;
    border-right: 0;
    border-bottom: 1px solid var(--pm-divider);
  }

  .wiki-proposal {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .wiki-proposal__actions {
    grid-column: 2;
  }
}

@media (prefers-reduced-motion: reduce) {
  .wiki-knav,
  .wiki-home-link,
  .wiki-cluster,
  .wiki-nav__switch,
  .wiki-nav__switch::after,
  .wiki-evidence-disclosure__chevron {
    transition-duration: 0ms;
  }
}
</style>
