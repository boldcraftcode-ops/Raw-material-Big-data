"""Tests Python portion of the self-contained .bat. Windows CMD execution not claimed."""
import json
import os
from pathlib import Path
import socket
import sys
import threading
import types

import pytest

LAUNCHER=Path(__file__).resolve().parents[2]/'start.bat'

@pytest.fixture
def launcher():
    data=LAUNCHER.read_bytes()
    assert data.startswith(b'@echo off\r\n') and b'\n' not in data.replace(b'\r\n',b'')
    source=data.decode('utf-8').split('\n',1)[1]
    namespace={'__name__':'launcher_test','__file__':str(LAUNCHER)}
    exec(compile(source,str(LAUNCHER),'exec'),namespace)
    return namespace

@pytest.fixture
def app_root(tmp_path,monkeypatch):
    root=tmp_path/'folder with spaces'/'app'
    (root/'backend').mkdir(parents=True);(root/'backend/app.py').write_text('# app')
    (root/'frontend/dist').mkdir(parents=True);(root/'frontend/dist/index.html').write_text('<html></html>')
    monkeypatch.chdir(root)
    return root


def test_polyglot_locator_supports_root_and_app_locations(launcher,app_root):
    find=launcher['find_app_root']
    assert find(app_root.parent/'start.bat')==app_root
    assert find(app_root/'start.bat')==app_root


def test_env_handles_bom_quotes_equals_but_not_secrets_in_stdout(launcher,tmp_path,monkeypatch,capsys):
    # Register original values even when absent; loader changes must be undone.
    for key in ('RUBBER_DATA_DIR','AWS_SECRET_ACCESS_KEY'):
        monkeypatch.setenv(key,'test-placeholder');monkeypatch.delenv(key)

    monkeypatch.setenv('PORT','8000');old_path=os.environ.get('PATH')
    file=tmp_path/'.env';file.write_text('\ufeff# config\nRUBBER_DATA_DIR="C:\\Karet Data"\nAWS_SECRET_ACCESS_KEY=testing=only\nPORT=8001\nPATH=do-not-replace\n',encoding='utf-8')
    launcher['load_local_env'](file)
    assert os.environ['RUBBER_DATA_DIR']=='C:\\Karet Data'
    assert os.environ['AWS_SECRET_ACCESS_KEY']=='testing=only' and os.environ['PORT']=='8000'
    assert os.environ.get('PATH')==old_path and capsys.readouterr().out==''


def test_env_rejects_shell_expansion_without_executing_it(launcher,tmp_path,monkeypatch):
    file=tmp_path/'.env';file.write_text('RUBBER_DATA_DIR=$(do-not-execute)')
    with pytest.raises(ValueError,match='literal'):launcher['load_local_env'](file)


def test_existing_application_reused_without_new_server(launcher,app_root,monkeypatch):
    opened=[];monkeypatch.setenv('PORT','8000')
    launcher['find_app_root']=lambda _:app_root
    launcher['port_in_use']=lambda _:True;launcher['application_ready']=lambda _:True
    monkeypatch.setattr(launcher['webbrowser'],'open',lambda url,**kw:opened.append(url))
    assert launcher['main']([])==0 and opened==['http://127.0.0.1:8000']


def test_other_application_port_not_killed(launcher,app_root,monkeypatch):
    monkeypatch.setenv('PORT','8000');launcher['find_app_root']=lambda _:app_root
    launcher['port_in_use']=lambda _:True;launcher['application_ready']=lambda _:False
    with pytest.raises(ValueError,match='program lain'):launcher['main'](['--no-browser'])


def test_new_server_loopback_single_worker(launcher,app_root,monkeypatch):
    calls=[];launcher['find_app_root']=lambda _:app_root;launcher['port_in_use']=lambda _:False
    monkeypatch.setitem(sys.modules,'uvicorn',types.SimpleNamespace(run=lambda *a,**k:calls.append((a,k))))
    assert launcher['main'](['--port','8001','--no-browser'])==0
    assert calls==[(('backend.app:app',),{'host':'127.0.0.1','port':8001,'workers':1})]


def test_browser_waits_for_ready_and_stop_signal_respected(launcher,monkeypatch):
    opened=[];launcher['application_ready']=lambda _:True
    monkeypatch.setattr(launcher['webbrowser'],'open',lambda url,**kw:opened.append(url))
    launcher['open_browser_when_ready'](8000,threading.Event())
    assert opened==['http://127.0.0.1:8000']
    stop=threading.Event();stop.set();launcher['open_browser_when_ready'](8001,stop)
    assert len(opened)==1


def test_indexer_windows_paths_retained_without_storage_credentials(monkeypatch):
    from backend.archive import indexer_environment
    monkeypatch.setenv('SystemRoot','C:\\Windows');monkeypatch.setenv('TEMP','C:\\Temp')
    monkeypatch.setenv('RUBBER_DATABASE_URL','testing-only');monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','testing-only')
    env=indexer_environment()
    assert env['SystemRoot']=='C:\\Windows' and env['TEMP']=='C:\\Temp' and env['PYTHONUTF8']=='1'
    assert 'RUBBER_DATABASE_URL' not in env and 'AWS_SECRET_ACCESS_KEY' not in env
