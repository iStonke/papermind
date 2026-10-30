import unittest
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import Column, DateTime, JSON, MetaData, SmallInteger, Table, Uuid, create_engine
from sqlalchemy.orm import Session

from app.schemas.related_preferences import RelatedPreferences
from app.schemas.settings import AppSettingsRead
from app.services.settings import SettingsService


class RelatedPreferencesTest(unittest.TestCase):
    def test_old_settings_default_to_the_existing_balanced_ranking(self):
        self.assertEqual(AppSettingsRead().ui.related_documents.factors(), dict(series=1, title=1, tags=1, correspondent=1, type=1))

    def test_profiles_are_canonical_and_invalid_weights_are_rejected(self):
        self.assertEqual(RelatedPreferences(profile='process', weights={'series': 'low'}).weights.series, 'high')
        for value in [{'profile': 'unknown'}, {'profile': 'custom', 'weights': {'tags': 'extreme'}}, {'weights': {'content': 'high'}}]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RelatedPreferences.model_validate(value)

    def test_api_uses_personal_defaults_and_validated_preview_overrides(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.documents import router, get_db, get_current_user
        from app.schemas.documents import RelatedDocumentListResponse
        app = FastAPI()
        app.include_router(router)
        owner = uuid.uuid4()
        app.dependency_overrides[get_db] = lambda: None
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=owner)
        settings = AppSettingsRead.model_validate({'ui': {'related_documents': {'profile': 'process'}}})
        with patch('app.routers.documents.SettingsService') as settings_service, patch('app.routers.documents.RelatedDocumentService') as recommendations:
            settings_service.return_value.get_settings.return_value = settings
            recommendations.return_value.list.return_value = RelatedDocumentListResponse()
            with TestClient(app) as client:
                path = f'/api/documents/{uuid.uuid4()}/related'
                self.assertEqual(client.get(path).status_code, 200)
                settings_service.assert_called_with(None, owner)
                recommendations.assert_called_with(None, owner)
                self.assertEqual(recommendations.return_value.list.call_args.args[-1].profile, 'process')
                self.assertEqual(client.get(path + '?profile=thematic').status_code, 200)
                self.assertEqual(recommendations.return_value.list.call_args.args[-1].factors()['tags'], 2)
                self.assertEqual(client.get(path + '?profile=custom&series_weight=low&tags_weight=high').status_code, 200)
                self.assertEqual(recommendations.return_value.list.call_args.args[-1].factors()['series'], .5)
                for query in ['profile=unknown', 'tags_weight=99']:
                    self.assertEqual(client.get(path + '?' + query).status_code, 422)
                self.assertEqual(settings.ui.related_documents.profile, 'process')

    def test_non_admin_preferences_persist_per_user_without_changing_global_settings(self):
        engine = create_engine('sqlite://')
        metadata = MetaData()
        for name, key in [('global_settings', Column('id', SmallInteger, primary_key=True)),
                          ('user_settings', Column('user_id', Uuid, primary_key=True))]:
            Table(name, metadata, key, Column('settings_json', JSON),
                  Column('created_at', DateTime, default=datetime.now), Column('updated_at', DateTime, default=datetime.now))
        metadata.create_all(engine)
        try:
            with Session(engine) as db:
                owner, other = uuid.uuid4(), uuid.uuid4()
                service = SettingsService(db, owner)
                baseline = SettingsService(db).get_settings().model_dump(mode='json')
                service.apply_patch({'ui': {'related_documents': {'profile': 'process'}}}, is_admin=False)
                self.assertEqual(SettingsService(db, owner).get_settings().ui.related_documents.profile, 'process')
                self.assertEqual(SettingsService(db, other).get_settings().ui.related_documents.profile, 'balanced')
                self.assertEqual(SettingsService(db).get_settings().model_dump(mode='json'), baseline)
                service.apply_patch({'ui': {'related_documents': {'profile': 'balanced'}}}, is_admin=False)
                self.assertEqual(service.get_settings().ui.related_documents.factors()['series'], 1)
        finally:
            engine.dispose()
