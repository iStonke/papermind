import tempfile
import unittest
import uuid
import shutil
import json
import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.core.errors import StorageError
from app.schemas.import_staging import ImportCommitRequest, ImportCommitPageInput
from app.services import import_staging
from app.services.import_staging import ImportStagingService
from app.services.import_metadata_heuristics import normalize_subject, detect_subject_heuristic, extract_subject_rich
from app.services.import_metadata_response import safe_float
from app.services.import_analysis_quality import date_supported, grounded_summary, amount_supported


class ImportWorkflowRobustnessTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous_storage = import_staging.settings.storage_path
        import_staging.settings.storage_path = self.directory.name
        self.service = ImportStagingService(db=None)
        self.service._scan_cleanup_settings = lambda: (None, 300)

    def tearDown(self):
        import_staging.settings.storage_path = self.previous_storage
        self.directory.cleanup()

    def source(self, width=2480, height=3508, pages=1):
        source_id = str(uuid.uuid4())
        path = self.service._source_pdf_path(source_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGB', (width, height), (220, 40, 20))
        image.save(path, format='PDF', resolution=300, save_all=True, append_images=[image] * (pages - 1))
        image.close()
        return source_id, path

    def test_empty_subjects_cannot_be_promoted_to_a_title(self):
        for value in [None, '', ' ', 'Ohne Betreff', 'Unbekannt', 'null', 'n/a']:
            self.assertEqual(normalize_subject(value), '')
        self.assertEqual(detect_subject_heuristic('Beliebiger unbekannter Brief'), '')

    def test_letter_heading_before_salutation_is_preserved(self):
        result = extract_subject_rich('Dataport\nHamburg, 15.10.2026\nRücknahme der Zuordnung Arbeitsstätte\nSehr geehrter Herr Beispiel,\nText', 'Brief')
        self.assertIn('Rücknahme', result)

    def test_non_finite_model_amounts_are_rejected(self):
        for value in ['NaN', 'Infinity', '-inf']:
            self.assertIsNone(safe_float(value))

    def test_ocr_failures_never_publish_internal_diagnostic_strings(self):
        diagnostic = 'source=5d5c3d0d-c509-4ada-ba18-56ebdfb329ba page=0 psm=6: Die PDF-Seite konnte nicht verarbeitet werden.'
        for status in ['ocr_failed', 'ocr_unavailable', 'low_text']:
            with self.subTest(status=status):
                diagnostics = {'status': status, 'errors': [diagnostic], 'attempts': [], 'chars': 0}
                result = self.service._build_stage_title_result(extracted_text='', normalized_scope='first_page',
                    page_refs=[], ocr_pending=True, ocr_diagnostics=diagnostics, use_ollama=False)
                self.assertNotIn('analysis_error', result['meta'])
                self.assertNotIn('errors', result['meta']['ocr'])
                self.assertEqual(result['meta']['ocr']['error_count'], 1)
                self.assertNotIn(diagnostic, json.dumps(result))
                self.assertEqual(diagnostics['errors'], [diagnostic])

    def test_success_after_an_ocr_retry_does_not_publish_previous_errors(self):
        diagnostics = {'status': 'ready', 'errors': ['source=internal page=0 psm=6: private diagnostic'], 'chars': 150}
        self.service.settings_service.get_settings = MagicMock(return_value=SimpleNamespace(model_dump=lambda **kwargs: {'ollama': {'enabled': False}}))
        self.service._load_existing_tag_names = MagicMock(return_value=[])
        self.service._resolve_correspondent = MagicMock(return_value=None)
        with patch.object(import_staging, 'load_active_document_type_vocab', return_value=[]):
            result = self.service._build_stage_title_result(extracted_text='Dies ist ein ausreichend langer synthetischer Brief mit einer lesbaren Betreffzeile und einem erfolgreichen OCR-Ergebnis.',
                normalized_scope='first_page', page_refs=[], ocr_pending=False, ocr_diagnostics=diagnostics, use_ollama=False)
        self.assertEqual(result['status'], 'ready')
        self.assertNotIn('errors', result['meta']['ocr'])
        self.assertEqual(result['meta']['ocr']['error_count'], 1)
        self.assertNotIn('private diagnostic', json.dumps(result))

    def test_model_dates_and_summary_numbers_need_document_evidence(self):
        self.assertTrue(date_supported('2026-10-15', 'Hamburg, 15. Oktober 2026'))
        self.assertTrue(date_supported('1985-02-01', 'Briefdatum 1.2.1985'))
        self.assertFalse(date_supported('2026-10-31', 'Briefdatum 15.10.2026'))
        self.assertIsNone(grounded_summary('Zahlbar bis 31.10.2026, Betrag 1500 EUR.', 'Brief vom 15.10.2026 ohne Zahlungsaufforderung.'))
        self.assertEqual(grounded_summary('Rechnungsbetrag 12,50 EUR.', 'Gesamtbetrag 12,50 EUR.'), 'Rechnungsbetrag 12,50 EUR.')
        self.assertTrue(amount_supported(1250.50, 'Gesamtbetrag 1.250,50 EUR'))
        self.assertFalse(amount_supported(2026, 'Briefdatum 15.10.2026'))
        self.assertFalse(amount_supported(1500, 'Gesamtbetrag 12,50 EUR'))

    def test_document_date_is_not_replaced_by_a_payment_deadline(self):
        text = 'Rechnungsdatum: 15.10.2026\nZahlbar bis: 31.10.2026\nDies ist eine ausführliche synthetische Rechnung für den Regressionstest.'
        self.service.settings_service.get_settings = MagicMock(return_value=SimpleNamespace(model_dump=lambda **kwargs: {'ollama': {'enabled': False}}))
        self.service._load_existing_tag_names = MagicMock(return_value=[])
        self.service._extract_rich_metadata = MagicMock(return_value={'doc_type': 'Rechnung', 'subject': 'Testrechnung', 'date': '2026-10-31'})
        self.service._resolve_correspondent = MagicMock(return_value=None)
        with patch.object(import_staging, 'load_active_document_type_vocab', return_value=[]):
            result = self.service._build_stage_title_result(extracted_text=text, normalized_scope='first_page', page_refs=[], ocr_pending=False, ocr_diagnostics={'status': 'ready'}, use_ollama=False)
        self.assertEqual(result['meta']['date'], '2026-10-15')
        self.assertIn('due_date', [candidate['kind'] for candidate in result['meta']['date_candidates']])

    def test_realistic_a4_multipage_grayscale_preserves_count_size_and_rotation(self):
        source_id, _ = self.source(pages=2)
        pages = [ImportCommitPageInput(source_file_id=source_id, page_index=index, color_mode='grayscale', rotation=90 if index == 1 else 0) for index in range(2)]
        path, count = self.service._build_document_pdf('A4', pages, {})
        reader = PdfReader(str(path))
        self.assertEqual(count, 2)
        self.assertEqual(len(reader.pages), 2)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.2, delta=2)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.92, delta=2)
        self.assertEqual(reader.pages[1].rotation, 90)

    def test_conversion_failure_retains_source_and_reports_page_and_cause(self):
        source_id, source = self.source(100, 100)
        original = source.read_bytes()
        with patch.object(import_staging, 'build_grayscale_pdf', side_effect=StorageError('PDF-Verarbeitung ist ausgelastet.', details={'kind': 'busy', 'retryable': True})):
            with self.assertRaises(StorageError) as caught:
                self.service._build_document_pdf('Test', [ImportCommitPageInput(source_file_id=source_id, page_index=0, color_mode='grayscale')], {})
        self.assertEqual(caught.exception.details['kind'], 'busy')
        self.assertEqual(caught.exception.details['page_index'], 0)
        self.assertIn('Seite 1', caught.exception.message)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(list(source.parent.glob('color-*.pdf')))

    def test_already_bilevel_scan_is_not_converted_again_for_grayscale(self):
        source_id, _ = self.source(100, 100)
        self.service._write_source_scan_cleanup(source_id, status='ready', mode='bw')
        with patch.object(import_staging, 'build_grayscale_pdf') as convert:
            path, count = self.service._build_document_pdf('Test', [ImportCommitPageInput(source_file_id=source_id, page_index=0, color_mode='grayscale')], {})
        self.assertEqual(count, 1)
        convert.assert_not_called()

    def test_committed_request_is_replayed_without_reading_deleted_sources(self):
        source_id = str(uuid.uuid4())
        request = ImportCommitRequest.model_validate({'request_id': 'attempt', 'documents': [{'client_document_id': 'draft-1', 'title': 'Brief', 'date': '2026-10-20', 'document_type': 'Brief', 'correspondent_id': str(uuid.uuid4()), 'tag_ids': [str(uuid.uuid4())], 'pages': [{'source_file_id': source_id, 'page_index': 0}]}]})
        service = ImportStagingService(MagicMock(), uuid.uuid4())
        service._validate_requested_tags = MagicMock()
        service._validate_requested_correspondents = MagicMock()
        service.get_source_scan_cleanup_response = MagicMock(return_value=None)
        assembled = Path(self.directory.name) / 'assembled.pdf'
        assembled.write_bytes(b'%PDF-fake-for-upload-mock')
        service._build_document_pdf = MagicMock(return_value=(assembled, 1))
        service._cleanup_source_files = MagicMock()
        document = SimpleNamespace(id=uuid.uuid4(), flags={}, document_type=None, correspondent_id=None, page_count=1, original_filename='Brief.pdf', display_name=None, ocr_status='queued')
        service._committed_import = MagicMock(return_value=None)
        def upload(*args, **kwargs):
            kwargs['finalize_import'](document)
            return document
        service.document_service.upload_document = MagicMock(side_effect=upload)
        with patch('app.services.storage_owner.lock_storage_owner'):
            first = service.commit(request)
            service._committed_import.return_value = document
            second = service.commit(request)
        self.assertFalse(first.errors)
        self.assertFalse(second.errors)
        self.assertTrue(second.created[0].replayed)
        self.assertEqual(first.created[0].doc_id, second.created[0].doc_id)
        service._build_document_pdf.assert_called_once()
        service.document_service.upload_document.assert_called_once()

    def test_changed_source_revision_stops_before_creating_document(self):
        source_id, source = self.source(100, 100)
        service = self.service
        service.db = MagicMock()
        service._validate_requested_tags = MagicMock()
        service._validate_requested_correspondents = MagicMock()
        service.document_service.upload_document = MagicMock()
        request = ImportCommitRequest.model_validate({'documents': [{'title': 'Brief', 'date': '2026-10-20', 'document_type': 'Brief', 'correspondent_id': str(uuid.uuid4()), 'tag_ids': [str(uuid.uuid4())], 'pages': [{'source_file_id': source_id, 'page_index': 0, 'source_revision': 'old'}]}]})
        with patch('app.services.storage_owner.lock_storage_owner'):
            result = service.commit(request)
        self.assertEqual(result.errors[0].code, 'CONFLICT')
        service.document_service.upload_document.assert_not_called()
        self.assertTrue(source.exists())

    def test_legacy_receipt_can_be_replayed_without_the_new_required_metadata(self):
        request = ImportCommitRequest.model_validate({'request_id': 'legacy', 'documents': [{
            'client_document_id': 'old-draft', 'title': 'Altbestand',
            'pages': [{'source_file_id': str(uuid.uuid4()), 'page_index': 0}]}]})
        fingerprint = hashlib.sha256(json.dumps({
            'document': request.documents[0].model_dump(mode='json'),
            'options': request.options.model_dump(mode='json'),
        }, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        document = SimpleNamespace(id=uuid.uuid4(), flags={'import_commit': {'fingerprint': fingerprint}},
                                   display_name='Altbestand', original_filename='Altbestand.pdf', page_count=1)
        service = ImportStagingService(MagicMock(), uuid.uuid4())
        service._committed_import = MagicMock(return_value=document)
        service._build_document_pdf = MagicMock()
        service._cleanup_source_files = MagicMock()
        with patch('app.services.storage_owner.lock_storage_owner'):
            response = service.commit(request)
        self.assertFalse(response.errors)
        self.assertTrue(response.created[0].replayed)
        service._build_document_pdf.assert_not_called()

    def test_selection_analysis_reads_selected_page_not_source_first_page(self):
        source_id, _ = self.source(100, 100, pages=3)
        with patch.object(import_staging, 'run_ocr_lite', return_value='Dies ist ausschließlich der Inhalt der ausgewählten zweiten Dokumentseite.'), patch.object(self.service, '_build_stage_title_result', return_value={'status': 'ready', 'suggestion': 'Zweite Seite', 'meta': {}}) as build:
            result = self.service.suggest_stage_title([source_id], pages=[ImportCommitPageInput(source_file_id=source_id, page_index=1)], document_revision='selected-2')
        self.assertEqual(build.call_args.kwargs['page_refs'], [f'{source_id}:1'])
        self.assertEqual(result['meta']['document_revision'], 'selected-2')
        self.assertEqual(result['meta']['pages_analyzed'], 1)

    def test_source_replacement_invalidates_cached_metadata(self):
        source_id, source = self.source(100, 100)
        self.service.store_source_analysis(source_id, {'status': 'ready', 'suggestion': 'Alt', 'meta': {}})
        self.assertIsNotNone(self.service.get_source_analysis(source_id))
        source.write_bytes(source.read_bytes() + b'\n% changed')
        self.assertIsNone(self.service.get_source_analysis(source_id))

    def test_force_analysis_bypasses_an_existing_cache(self):
        source_id, _ = self.source(100, 100)
        self.service.get_source_analysis = MagicMock(return_value={'status': 'ready', 'suggestion': 'Alt'})
        self.service._extract_text_for_title_suggestion = MagicMock(return_value=('Vorhandener lesbarer Text mit ausreichender Qualität und einer eindeutigen Betreffzeile.', 1, [f'{source_id}:0']))
        self.service._build_stage_title_result = MagicMock(return_value={'status': 'ready', 'suggestion': 'Neu', 'meta': {}})
        result = self.service.suggest_stage_title([source_id], force=True)
        self.assertEqual(result['suggestion'], 'Neu')
        self.service.get_source_analysis.assert_not_called()

    def test_grayscale_keeps_embedded_text_or_fails_without_destroying_it(self):
        source_id = str(uuid.uuid4())
        path = self.service._source_pdf_path(source_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 14 Tf 50 750 Td 1 0 0 rg (Searchable invoice) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(content)
        writer.write(str(path))
        selection = [ImportCommitPageInput(source_file_id=source_id, page_index=0, color_mode='grayscale')]
        if shutil.which('gs'):
            output, _ = self.service._build_document_pdf('Text', selection, {})
            self.assertIn('Searchable invoice', PdfReader(str(output)).pages[0].extract_text())
        else:
            with self.assertRaises(StorageError):
                self.service._build_document_pdf('Text', selection, {})
        self.assertIn('Searchable invoice', PdfReader(str(path)).pages[0].extract_text())
