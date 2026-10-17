"""Build an explicitly authorized, allowlisted source+frontend ZIP; never include private runtime or credentials."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import tempfile
import zipfile

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
PREFIX = 'rubber-intelligence/'
FORBIDDEN_PARTS = {'runtime', 'node_modules', '.venv', '.cache', '__pycache__',
                   '.pytest_cache', '.git', '.wrangler', '.npm', '.local'}
EXAMPLES = {'.env.example', '.dev.vars.example'}


def validate_source_path(path, root=ROOT):
    relative = path.relative_to(root)
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise SystemExit('Non-regular or unsafe source path in release: ' + relative.as_posix())
    if any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(root) and parent != root):
        raise SystemExit('Symlink directory in release: ' + relative.as_posix())
    if any(part.lower() in FORBIDDEN_PARTS or part.lower().startswith('runtime-') for part in relative.parts):
        raise SystemExit('Private runtime/dependency path in release: ' + relative.as_posix())
    if (path.name.lower().startswith(('.env', '.dev.vars')) and path.name not in EXAMPLES
            or path.suffix.lower() in {'.sqlite3', '.sqlite', '.db', '.pem', '.key', '.zip', '.tsbuildinfo'}
            or path.name.lower() in {'id_rsa', 'id_ed25519', '.git-credentials', '.netrc', 'credentials.json'}):
        raise SystemExit('Credential/database/generated path in release: ' + relative.as_posix())


def collect_files():
    files = set()
    root_files = ('README.md', 'blueprint.md', 'blueprint.html', 'render_blueprint.py', 'START_HERE.md',
                  'start.bat', 'WINDOWS_11.md', 'DEPLOY_CLOUDFLARE.md', 'package.json', 'package-lock.json',
                  'wrangler.jsonc', 'render.yaml', '.node-version', '.gitignore', '.gitattributes', '.dev.vars.example')
    for relative in root_files:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit('Missing root release file: ' + relative)
        files.add(path)
    for path in (ROOT / 'deployment').rglob('*'):
        if path.is_file() and path.suffix in {'.mjs', '.md', '.json'}:
            files.add(path)
    for relative in ('.gitignore', '.dockerignore', '.env.example', 'Dockerfile', 'compose.yaml', 'README.md',
                     'RELEASE_NOTES.md', 'THIRD_PARTY_NOTICES.txt', 'requirements.txt', 'requirements-tested.txt',
                     'prepare.sh', 'run.sh', 'pytest.ini', 'template_pembelian_karet.csv'):
        path = APP / relative
        if not path.is_file():
            raise SystemExit('Missing required application file: ' + relative)
        files.add(path)
    for folder, extensions in [('backend', {'.py', '.sql'}), ('tests', {'.py'}), ('scripts', {'.py'}),
                               ('docs', {'.md', '.json', '.html', '.png'})]:
        for path in (APP / folder).rglob('*'):
            if path.is_file() and path.suffix in extensions and '__pycache__' not in path.parts:
                files.add(path)
    for relative in ('index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', 'public/_headers'):
        path = APP / 'frontend' / relative
        if not path.is_file():
            raise SystemExit('Missing frontend source file: ' + relative)
        files.add(path)
    for path in (APP / 'frontend' / 'src').rglob('*'):
        if path.is_file() and path.suffix in {'.ts', '.tsx', '.css'}:
            files.add(path)
    for path in (APP / 'frontend' / 'tests').rglob('*.mjs'):
        if path.is_file():
            files.add(path)
    for path in (APP / 'frontend' / 'dist').rglob('*'):
        if path.is_file():
            files.add(path)
    for relative in ('app/frontend/dist/index.html', 'app/frontend/dist/_headers', 'deployment/worker.mjs',
                     'deployment/verify-live.mjs', 'app/backend/intake_breakdown.py', 'app/backend/breakdown_service.py'):
        if not (ROOT / relative).is_file():
            raise SystemExit('Complete frontend build/source required; missing ' + relative)
    for path in files:
        validate_source_path(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'Rubber-Intelligence-GitHub-Cloudflare.zip')
    parser.add_argument('--confirm-release', action='store_true',
                        help='Hanya gunakan setelah pengguna secara eksplisit meminta paket download.')
    args = parser.parse_args()
    if not args.confirm_release:
        raise SystemExit('ZIP tidak dibuat: perlu permintaan download eksplisit dari pengguna. Gunakan --confirm-release hanya setelah ada permintaan tersebut.')
    destination = args.output.resolve()
    if destination.suffix.lower() != '.zip':
        raise SystemExit('Release output must be a .zip file.')
    files = collect_files()
    now = datetime.now(timezone.utc)
    manifest = {
        'release': 'Rubber Intelligence — Full MVP source, frontend build and Cloudflare gateway configuration',
        'version': '0.2.0', 'date': now.date().isoformat(), 'created_at_utc': now.isoformat(),
        'status': 'source_distribution_on_explicit_user_request', 'archive_created': True,
        'archive_generation': 'only_on_explicit_user_download_request', 'archive_root': PREFIX.rstrip('/'),
        'github_upload': 'Extract ZIP, then upload the contents of rubber-intelligence to repository root. Do not commit only the ZIP.',
        'runtime_data_included': False, 'credentials_or_workspace_tokens_included': False,
        'frontend_build_included': True, 'manifest_excludes_self': True, 'windows_launcher_included': True,
        'galaxy_motion_included': True, 'mode': 'local_rules_no_external_ai',
        'current_features': ['raw_intake', 'automatic_public_collectors', 'bounded_galaxy_motion', 'local_excel_assistant',
                             'general_intake_breakdown', 'business_dataset_and_column_classification',
                             'version_bound_explicit_metadata_review', 'cloudflare_asset_build_and_python_api_gateway_config'],
        'cloudflare_deployed': False, 'backend_cloud_deployed': False, 'paid_cloud_resources_created': False,
        'persistent_https_python_backend_required': True, 'backend_origin_runtime_binding_required': 'BACKEND_ORIGIN',
        'deployment_guide': '../DEPLOY_CLOUDFLARE.md', 'validation_reference': 'docs/INTAKE_BREAKDOWN.md',
        'windows_native_execution_tested': False, 'postgresql_retested_for_intake_breakdown': False,
        'files': {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.rubber-package-', suffix='.tmp', dir=destination.parent, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                archive.write(path, arcname=PREFIX + path.relative_to(ROOT).as_posix())
            archive.writestr(PREFIX + 'app/RELEASE_MANIFEST.json', manifest_bytes)
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None, 'ZIP CRC verification failed.'
            assert len(archive.namelist()) == len(set(archive.namelist())) == len(files) + 1
            for relative, digest in manifest['files'].items():
                assert hashlib.sha256(archive.read(PREFIX + relative)).hexdigest() == digest, relative
            assert archive.read(PREFIX + 'app/RELEASE_MANIFEST.json') == manifest_bytes
        temporary.replace(destination)
        (APP / 'RELEASE_MANIFEST.json').write_bytes(manifest_bytes)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({'archive': str(destination), 'files': len(files) + 1,
                      'size_bytes': destination.stat().st_size,
                      'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                      'runtime_or_real_secrets_included': False}, indent=2))


if __name__ == '__main__':
    main()
