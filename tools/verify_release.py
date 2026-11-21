"""Verify the shipped source, then run the suite against the extracted ZIP."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    archive = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / 'release' / f'privacy-data-agent-local-v{version}.zip'
    prefix = 'privacy-data-agent-local/'
    forbidden = {'.venv', 'venv', '.claude', 'node_modules', '__pycache__', 'runs', 'pda_inbox', 'pda_outbox'}
    with ZipFile(archive) as source:
        assert source.testzip() is None, 'ZIP integrity check failed'
        assert len(source.namelist()) == len(set(source.namelist())), 'Duplicate ZIP entries'
        for name in source.namelist():
            path = Path(name)
            assert name.startswith(prefix) and '..' not in path.parts, f'Unexpected ZIP path: {name}'
            if path.name == '.gitkeep' or name.endswith('/'):
                continue
            assert not (set(path.parts) & forbidden), f'Runtime/private file in ZIP: {name}'
            assert not path.name.startswith('.env') and path.suffix not in {'.pyc', '.pyo'}, name
        config = tomllib.loads(source.read(prefix + 'pyproject.toml').decode())
        assert config['project']['version'] == version, 'Package version differs'
        assert source.read(prefix + '.streamlit/config.toml') == (root / 'release/privacy-data-agent-local/.streamlit/config.toml').read_bytes(), 'Missing/stale local server config'
        local = {path.relative_to(root / 'src').as_posix(): path for path in (root / 'src/privacy_data_agent').rglob('*.py')}
        packaged = {name.removeprefix(prefix + 'src/') for name in source.namelist()
                    if name.startswith(prefix + 'src/') and name.endswith('.py')}
        assert packaged == set(local), 'Packaged source file set differs'
        for name, path in local.items():
            assert source.read(prefix + 'src/' + name) == path.read_bytes(), f'Stale packaged source: {name}'
        checksum = archive.with_suffix(archive.suffix + '.sha256')
        if checksum.exists():
            assert checksum.read_text().split()[0] == hashlib.sha256(archive.read_bytes()).hexdigest(), 'Checksum mismatch'
        with tempfile.TemporaryDirectory(prefix='pda-release-verification-') as temporary:
            source.extractall(temporary)
            package = Path(temporary) / prefix / 'src'
            environment = {**os.environ, 'PYTHONPATH': str(package)}
            probe = 'import pathlib,sys,privacy_data_agent as p; assert pathlib.Path(p.__file__).is_relative_to(pathlib.Path(sys.argv[1])); assert p.__version__==sys.argv[2]; print("Verified package version:",p.__version__)'
            subprocess.run([sys.executable, '-c', probe, str(package), version], cwd=temporary, env=environment, check=True)
            subprocess.run([sys.executable, '-m', 'pytest', str(root / 'tests'), '-c', str(root / 'pyproject.toml'),
                            '-o', f'pythonpath={package}', '-q'], cwd=root, env=environment, check=True)
    print(f'PASS: {archive.name} matches source and passes packaged-code tests')


if __name__ == '__main__':
    main()
