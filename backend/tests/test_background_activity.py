import threading
import uuid
from unittest.mock import patch

from app.services import background_activity as activity
from app.core.errors import NotFoundError
import pytest


def test_cancel_restart_and_owner_scope(tmp_path):
    owner = uuid.uuid4()
    entered, release = threading.Event(), threading.Event()
    calls = []

    @activity.tracked('preanalysis', 'Importanalyse')
    def work(sources, owner_id):
        calls.append(sources)
        entered.set()
        release.wait(5)
        activity.checkpoint()

    with patch.object(activity, '_root', return_value=tmp_path):
        thread = threading.Thread(target=work, args=(['source'], owner))
        thread.start()
        assert entered.wait(5)
        item = activity.activity(owner)[0]
        assert 'args' not in item and 'kwargs' not in item
        with pytest.raises(NotFoundError):
            activity.control(item['id'], 'restart', uuid.uuid4())
        activity.control(item['id'], 'restart', owner)
        assert activity.claim_queued(['preanalysis']) is None
        release.set()
        thread.join(5)
        assert not thread.is_alive()
        pending = activity.claim_queued(['preanalysis'])
        assert pending['id'] == item['id']
        activity.execute(pending, work.activity_function)
        assert len(calls) == 2
        assert activity.activity(owner) == []
