from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.models import Job
import app.main as main


@pytest.mark.parametrize('status,creator', [('customer_declined','web:client'),('cancelled','web:client'),('cancelled','api:key'),('failed','api:key'),('running','api:key')])
@pytest.mark.parametrize('kind', [None,'suppliers','admin_supplement'])
def test_cancelled_or_unsettled_direct_results_are_not_downloadable(monkeypatch,tmp_path,status,creator,kind):
    job=Job(id='test-job',client_id='test-client',mode='supplier_search',status=status,created_by_telegram_id=creator)
    db=Mock();db.get.return_value=job
    context=SimpleNamespace(user=SimpleNamespace(client_id='test-client'))
    path=tmp_path/'report.xlsx';path.write_bytes(b'synthetic')
    package=Mock(return_value=path);items=Mock(return_value=[{'kind':'suppliers','path':str(path)}]);charge=Mock()
    monkeypatch.setattr(main,'package_job_outputs',package)
    monkeypatch.setattr(main,'package_job_output_items',items)
    monkeypatch.setattr(main,'charge_job_reservation',charge)
    with pytest.raises(HTTPException) as error:
        if kind is None:main.download_customer_job_api(job.id,context=context,db=db)
        else:main.download_customer_job_file_api(job.id,kind,context=context,db=db)
    assert error.value.status_code==409
    package.assert_not_called();items.assert_not_called();charge.assert_not_called()
