from pathlib import Path
import importlib.util
import subprocess
import sys

import pytest


def packager_module():
    script = Path(__file__).resolve().parents[1] / 'scripts/package_release.py'
    spec = importlib.util.spec_from_file_location('rubber_release_packager', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packager_requires_explicit_release_confirmation(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/package_release.py'
    archive = tmp_path / 'must-not-exist.zip'
    result = subprocess.run([sys.executable, str(script), '--output', str(archive)], capture_output=True, text=True)
    assert result.returncode != 0 and '--confirm-release' in result.stderr
    assert not archive.exists()


def test_packager_rejects_private_credentials_databases_dependencies_and_runtime(tmp_path):
    module = packager_module()
    for relative in ['.env', '.env.production', '.dev.vars', '.dev.vars.production', '.ENV',
                     'runtime/objects/source.py', 'runtime-old/source.py', 'Runtime/source.py',
                     'node_modules/lib.js', '.wrangler/state.json', 'workspace.sqlite3',
                     'private.pem', 'id_rsa', 'credentials.json', 'tsconfig.tsbuildinfo']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic forbidden fixture')
        with pytest.raises(SystemExit):
            module.validate_source_path(path, tmp_path)


def test_packager_allows_only_named_configuration_examples(tmp_path):
    module = packager_module()
    for name in ['.env.example', '.dev.vars.example', 'wrangler.jsonc', 'README.md']:
        path = tmp_path / name
        path.write_text('synthetic safe fixture')
        module.validate_source_path(path, tmp_path)


def test_packager_rejects_file_and_directory_symlinks(tmp_path):
    module = packager_module()
    target = tmp_path / 'target.py'
    target.write_text('# synthetic source')
    symlink = tmp_path / 'alias.py'
    try:
        symlink.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip('Creating symlinks is not permitted on this platform')
    with pytest.raises(SystemExit):
        module.validate_source_path(symlink, tmp_path)
    folder = tmp_path / 'real'
    folder.mkdir()
    (folder / 'source.py').write_text('# synthetic source')
    alias = tmp_path / 'alias'
    alias.symlink_to(folder, target_is_directory=True)
    with pytest.raises(SystemExit):
        module.validate_source_path(alias / 'source.py', tmp_path)


def test_complete_distribution_contains_cloudflare_backend_and_prebuilt_ui():
    module = packager_module()
    if not (module.ROOT / 'app/frontend/dist/index.html').is_file():
        pytest.skip('Optional release contents check needs the frontend build')
    names = {path.relative_to(module.ROOT).as_posix() for path in module.collect_files()}
    assert {'README.md', '.gitattributes', 'wrangler.jsonc', 'package.json', 'package-lock.json',
            'render.yaml', 'start.bat', 'render_blueprint.py', 'DEPLOY_CLOUDFLARE.md',
            'deployment/worker.mjs', 'deployment/verify-live.mjs', 'deployment/tests/worker.test.mjs',
            'app/backend/app.py', 'app/backend/intake_breakdown.py', 'app/backend/breakdown_service.py',
            'app/backend/schema_v02.sql', 'app/frontend/dist/index.html', 'app/frontend/dist/_headers',
            'app/frontend/public/_headers', 'app/Dockerfile', 'app/.env.example'} <= names
