"""Tests for UpdaterService - Update checking, verification and safe extraction."""
import os
import json
import tarfile
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import pytest

from infrastructure.updater_service import (
    UpdaterService,
    VersionInfo,
    BackupInfo,
)


class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_version_info_required_fields(self):
        """Test creating VersionInfo with required fields."""
        info = VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://github.com/example/releases/v0.7.0",
            tarball_url="https://github.com/example/releases/download/v0.7.0/update_0.7.0.tar.gz",
        )
        assert info.version == "0.7.0"
        assert info.sha256_url is None
        assert info.minisig_url is None

    def test_version_info_with_verification_urls(self):
        """Test VersionInfo with SHA256 and minisig URLs."""
        info = VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com",
            tarball_url="https://example.com/update.tar.gz",
            sha256_url="https://example.com/update.sha256",
            minisig_url="https://example.com/update.tar.gz.minisig",
            minisig_name="update_0.7.0.tar.gz.minisig",
        )
        assert info.sha256_url == "https://example.com/update.sha256"
        assert info.minisig_url == "https://example.com/update.tar.gz.minisig"
        assert info.minisig_name == "update_0.7.0.tar.gz.minisig"


class TestSelectUpdateAssets:
    """Test _select_update_assets - Asset URL selection from release."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        return UpdaterService(app_dir=tmp_path)

    def test_select_assets_with_all_files(self, service):
        """Test asset selection with tarball, sha256, and minisig."""
        assets = [
            {
                "name": "update_0.7.0.tar.gz",
                "browser_download_url": "https://example.com/update_0.7.0.tar.gz"
            },
            {
                "name": "update_0.7.0.sha256",
                "browser_download_url": "https://example.com/update_0.7.0.sha256"
            },
            {
                "name": "update_0.7.0.tar.gz.minisig",
                "browser_download_url": "https://example.com/update_0.7.0.tar.gz.minisig"
            },
        ]

        tarball_url, tarball_name, sha256_url, minisig_url, minisig_name = service._select_update_assets(
            assets, "0.7.0"
        )

        assert tarball_url == "https://example.com/update_0.7.0.tar.gz"
        assert tarball_name == "update_0.7.0.tar.gz"
        assert sha256_url == "https://example.com/update_0.7.0.sha256"
        assert minisig_url == "https://example.com/update_0.7.0.tar.gz.minisig"
        assert minisig_name == "update_0.7.0.tar.gz.minisig"

    def test_select_assets_tarball_only(self, service):
        """Test asset selection with only tarball (no verification files)."""
        assets = [
            {
                "name": "update_0.7.0.tar.gz",
                "browser_download_url": "https://example.com/update_0.7.0.tar.gz"
            },
        ]

        tarball_url, tarball_name, sha256_url, minisig_url, minisig_name = service._select_update_assets(
            assets, "0.7.0"
        )

        assert tarball_url == "https://example.com/update_0.7.0.tar.gz"
        assert tarball_name == "update_0.7.0.tar.gz"
        assert sha256_url is None
        assert minisig_url is None
        assert minisig_name is None

    def test_select_assets_empty_list(self, service):
        """Test asset selection with empty asset list."""
        tarball_url, tarball_name, sha256_url, minisig_url, minisig_name = service._select_update_assets(
            [], "0.7.0"
        )

        assert tarball_url is None
        assert tarball_name is None
        assert sha256_url is None
        assert minisig_url is None
        assert minisig_name is None

    def test_select_assets_ignores_unrelated_files(self, service):
        """Test that unrelated assets are ignored."""
        assets = [
            {
                "name": "update_0.7.0.tar.gz",
                "browser_download_url": "https://example.com/update_0.7.0.tar.gz"
            },
            {
                "name": "README.md",
                "browser_download_url": "https://example.com/README.md"
            },
            {
                "name": "other_file.zip",
                "browser_download_url": "https://example.com/other_file.zip"
            },
        ]

        tarball_url, tarball_name, sha256_url, minisig_url, minisig_name = service._select_update_assets(
            assets, "0.7.0"
        )

        assert tarball_url == "https://example.com/update_0.7.0.tar.gz"
        assert sha256_url is None
        assert minisig_url is None


class TestMinisignVerification:
    """Test _verify_minisign - Minisign signature verification."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        return UpdaterService(app_dir=tmp_path)

    def test_verify_minisign_no_minisign_installed(self, service, tmp_path):
        """Test verification fails when minisign is not installed."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test data")
        minisig_path = tmp_path / "update.tar.gz.minisig"
        minisig_path.write_bytes(b"signature")

        with patch('shutil.which', return_value=None):
            success, msg = service._verify_minisign(download_path, minisig_path)

        assert success is False
        assert "minisign nicht installiert" in msg

    def test_verify_minisign_missing_signature_file(self, service, tmp_path):
        """Test verification fails when signature file is missing."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test data")

        success, msg = service._verify_minisign(download_path, None)
        assert success is False
        assert "Signaturdatei fehlt" in msg

    def test_verify_minisign_missing_public_key(self, service, tmp_path):
        """Test verification fails when public key is missing."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test data")
        minisig_path = tmp_path / "update.tar.gz.minisig"
        minisig_path.write_bytes(b"signature")

        with patch('shutil.which', return_value='/usr/bin/minisign'):
            success, msg = service._verify_minisign(download_path, minisig_path)

        assert success is False
        assert "Public-Key fehlt" in msg

    def test_verify_minisign_success(self, service, tmp_path):
        """Test successful minisign verification."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test data")
        minisig_path = tmp_path / "update.tar.gz.minisig"
        minisig_path.write_bytes(b"signature")

        # Create public key
        pubkey_dir = tmp_path / "config"
        pubkey_dir.mkdir()
        pubkey_path = pubkey_dir / "update_public_key.pub"
        pubkey_path.write_text("untrusted comment: test key\nRWTest==")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch('shutil.which', return_value='/usr/bin/minisign'):
            with patch('subprocess.run', return_value=mock_result):
                success, msg = service._verify_minisign(download_path, minisig_path)

        assert success is True
        assert msg == "OK"

    def test_verify_minisign_failure(self, service, tmp_path):
        """Test minisign verification failure."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test data")
        minisig_path = tmp_path / "update.tar.gz.minisig"
        minisig_path.write_bytes(b"bad signature")

        # Create public key
        pubkey_dir = tmp_path / "config"
        pubkey_dir.mkdir()
        pubkey_path = pubkey_dir / "update_public_key.pub"
        pubkey_path.write_text("untrusted comment: test key\nRWTest==")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Signature verification failed"
        mock_result.stdout = ""

        with patch('shutil.which', return_value='/usr/bin/minisign'):
            with patch('subprocess.run', return_value=mock_result):
                success, msg = service._verify_minisign(download_path, minisig_path)

        assert success is False
        assert "Signature verification failed" in msg


class TestSHA256Verification:
    """Test _verify_sha256 - SHA256 hash verification."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        return UpdaterService(app_dir=tmp_path)

    def test_verify_sha256_success(self, service, tmp_path):
        """Test successful SHA256 verification."""
        # Create test file with known content
        download_path = tmp_path / "update.tar.gz"
        content = b"test content for sha256"
        download_path.write_bytes(content)

        # Calculate expected hash
        expected_hash = hashlib.sha256(content).hexdigest()

        # Mock URL response
        mock_response = Mock()
        mock_response.read.return_value = f"{expected_hash}  update.tar.gz".encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, msg = service._verify_sha256(download_path, "https://example.com/update.sha256")

        assert success is True
        assert msg == "OK"

    def test_verify_sha256_mismatch(self, service, tmp_path):
        """Test SHA256 verification with hash mismatch."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test content")

        # Mock URL response with wrong hash
        mock_response = Mock()
        mock_response.read.return_value = b"0000000000000000000000000000000000000000000000000000000000000000  update.tar.gz"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, msg = service._verify_sha256(download_path, "https://example.com/update.sha256")

        assert success is False
        assert "stimmt nicht ueberein" in msg

    def test_verify_sha256_invalid_file(self, service, tmp_path):
        """Test SHA256 verification with invalid hash file."""
        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test content")

        # Mock URL response with invalid/short hash
        mock_response = Mock()
        mock_response.read.return_value = b"short"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, msg = service._verify_sha256(download_path, "https://example.com/update.sha256")

        assert success is False
        assert "ungueltig" in msg

    def test_verify_sha256_network_error(self, service, tmp_path):
        """Test SHA256 verification with network error."""
        import urllib.error

        download_path = tmp_path / "update.tar.gz"
        download_path.write_bytes(b"test content")

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection failed")):
            success, msg = service._verify_sha256(download_path, "https://example.com/update.sha256")

        assert success is False
        assert "Connection failed" in msg


class TestDownloadFlow:
    """Test download_update - Full download flow with verification."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        return UpdaterService(app_dir=tmp_path)

    @pytest.fixture
    def version_info(self):
        """Create test VersionInfo."""
        return VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com",
            tarball_url="https://example.com/update_0.7.0.tar.gz",
            tarball_name="update_0.7.0.tar.gz",
        )

    def test_download_success_no_verification(self, service, version_info):
        """Test successful download without verification files."""
        # Mock tarball download
        mock_response = Mock()
        mock_response.read.return_value = b"fake tarball content"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, msg, path = service.download_update(version_info)

        assert success is True
        assert "Download abgeschlossen" in msg
        assert path is not None
        assert path.exists()

    def test_download_fails_on_sha256_mismatch(self, service, tmp_path):
        """Test download fails when SHA256 verification fails."""
        version_info = VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com",
            tarball_url="https://example.com/update.tar.gz",
            tarball_name="update_0.7.0.tar.gz",
            sha256_url="https://example.com/update.sha256",
        )

        # Mock tarball download
        mock_tarball_response = Mock()
        mock_tarball_response.read.return_value = b"fake tarball"
        mock_tarball_response.__enter__ = Mock(return_value=mock_tarball_response)
        mock_tarball_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_tarball_response):
            with patch.object(service, '_verify_sha256', return_value=(False, "Hash mismatch")):
                success, msg, path = service.download_update(version_info)

        assert success is False
        assert "Hash-Check fehlgeschlagen" in msg
        assert path is None

    def test_download_fails_on_signature_check(self, service, tmp_path):
        """Test download fails when signature verification fails."""
        version_info = VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com",
            tarball_url="https://example.com/update.tar.gz",
            tarball_name="update_0.7.0.tar.gz",
            minisig_url="https://example.com/update.tar.gz.minisig",
            minisig_name="update_0.7.0.tar.gz.minisig",
        )

        # Mock tarball download
        mock_tarball_response = Mock()
        mock_tarball_response.read.return_value = b"fake tarball"
        mock_tarball_response.__enter__ = Mock(return_value=mock_tarball_response)
        mock_tarball_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_tarball_response):
            with patch.object(service, '_download_asset', return_value=(True, "OK")):
                with patch.object(service, '_verify_minisign', return_value=(False, "Invalid signature")):
                    success, msg, path = service.download_update(version_info)

        assert success is False
        assert "Signatur-Check fehlgeschlagen" in msg
        assert path is None

    def test_download_fails_on_minisig_download_error(self, service, tmp_path):
        """Test download fails when minisig file cannot be downloaded."""
        version_info = VersionInfo(
            version="0.7.0",
            tag_name="v0.7.0",
            name="Version 0.7.0",
            body="Release notes",
            published_at="2025-01-01T00:00:00Z",
            download_url="https://example.com",
            tarball_url="https://example.com/update.tar.gz",
            tarball_name="update_0.7.0.tar.gz",
            minisig_url="https://example.com/update.tar.gz.minisig",
            minisig_name="update_0.7.0.tar.gz.minisig",
        )

        # Mock tarball download
        mock_tarball_response = Mock()
        mock_tarball_response.read.return_value = b"fake tarball"
        mock_tarball_response.__enter__ = Mock(return_value=mock_tarball_response)
        mock_tarball_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_tarball_response):
            with patch.object(service, '_download_asset', return_value=(False, "Network error")):
                success, msg, path = service.download_update(version_info)

        assert success is False
        assert "Signatur-Download fehlgeschlagen" in msg
        assert path is None


class TestSafeExtract:
    """Test _safe_extract - Safe tar extraction with path traversal prevention."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        return UpdaterService(app_dir=tmp_path)

    def test_safe_extract_valid_tar(self, service, tmp_path):
        """Test extraction of valid tar archive."""
        # Create a valid tar file
        tar_path = tmp_path / "valid.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "w:gz") as tar:
            # Add a regular file
            file_content = b"test content"
            info = tarfile.TarInfo(name="test.txt")
            info.size = len(file_content)
            tar.addfile(info, fileobj=__import__('io').BytesIO(file_content))

        with tarfile.open(tar_path, "r:gz") as tar:
            service._safe_extract(tar, extract_dir)

        assert (extract_dir / "test.txt").exists()
        assert (extract_dir / "test.txt").read_bytes() == b"test content"

    def test_safe_extract_rejects_path_traversal(self, service, tmp_path):
        """Test that path traversal attacks are rejected."""
        import io

        # Create tar with malicious path
        tar_path = tmp_path / "evil.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "w:gz") as tar:
            # Add file with path traversal
            info = tarfile.TarInfo(name="../../../evil.txt")
            info.size = 4
            tar.addfile(info, fileobj=io.BytesIO(b"evil"))

        with tarfile.open(tar_path, "r:gz") as tar:
            with pytest.raises(Exception) as exc_info:
                service._safe_extract(tar, extract_dir)

        assert "Path traversal" in str(exc_info.value)

    def test_safe_extract_rejects_symlinks(self, service, tmp_path):
        """Test that symlinks are rejected."""
        import io

        # Create tar with symlink
        tar_path = tmp_path / "symlink.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "w:gz") as tar:
            # Add a symlink
            info = tarfile.TarInfo(name="link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)

        with tarfile.open(tar_path, "r:gz") as tar:
            with pytest.raises(Exception) as exc_info:
                service._safe_extract(tar, extract_dir)

        assert "Symlink" in str(exc_info.value)

    def test_safe_extract_rejects_hardlinks(self, service, tmp_path):
        """Test that hardlinks are rejected."""
        import io

        # Create tar with hardlink
        tar_path = tmp_path / "hardlink.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "w:gz") as tar:
            # Add a hardlink
            info = tarfile.TarInfo(name="hardlink")
            info.type = tarfile.LNKTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)

        with tarfile.open(tar_path, "r:gz") as tar:
            with pytest.raises(Exception) as exc_info:
                service._safe_extract(tar, extract_dir)

        assert "Symlink" in str(exc_info.value)  # Both are treated the same

    def test_safe_extract_nested_directories(self, service, tmp_path):
        """Test extraction of nested directories."""
        import io

        tar_path = tmp_path / "nested.tar.gz"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "w:gz") as tar:
            # Add directory with proper mode
            dir_info = tarfile.TarInfo(name="subdir")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            # Add file in directory with proper mode
            file_content = b"nested file"
            file_info = tarfile.TarInfo(name="subdir/file.txt")
            file_info.size = len(file_content)
            file_info.mode = 0o644
            tar.addfile(file_info, fileobj=io.BytesIO(file_content))

        with tarfile.open(tar_path, "r:gz") as tar:
            service._safe_extract(tar, extract_dir)

        assert (extract_dir / "subdir" / "file.txt").exists()


class TestCheckForUpdates:
    """Test check_for_updates - UI hints and status messages."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with temp directory."""
        svc = UpdaterService(app_dir=tmp_path)
        # Create VERSION file
        (tmp_path / "VERSION").write_text("0.6.0\n")
        return svc

    def test_check_for_updates_with_all_verification(self, service):
        """Test update check returns info with verification URLs."""
        api_response = {
            "tag_name": "v0.7.0",
            "name": "Version 0.7.0",
            "body": "New features!",
            "published_at": "2025-01-01T00:00:00Z",
            "html_url": "https://github.com/example/releases/v0.7.0",
            "tarball_url": "https://api.github.com/repos/example/tarball/v0.7.0",
            "assets": [
                {
                    "name": "update_0.7.0.tar.gz",
                    "browser_download_url": "https://example.com/update_0.7.0.tar.gz"
                },
                {
                    "name": "update_0.7.0.sha256",
                    "browser_download_url": "https://example.com/update_0.7.0.sha256"
                },
                {
                    "name": "update_0.7.0.tar.gz.minisig",
                    "browser_download_url": "https://example.com/update_0.7.0.tar.gz.minisig"
                },
            ],
        }

        mock_response = Mock()
        mock_response.read.return_value = json.dumps(api_response).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            has_update, version_info, msg = service.check_for_updates()

        assert has_update is True
        assert version_info is not None
        assert version_info.version == "0.7.0"
        assert version_info.sha256_url == "https://example.com/update_0.7.0.sha256"
        assert version_info.minisig_url == "https://example.com/update_0.7.0.tar.gz.minisig"
        assert "0.7.0" in msg

    def test_check_for_updates_without_verification(self, service):
        """Test update check when no verification files available."""
        api_response = {
            "tag_name": "v0.7.0",
            "name": "Version 0.7.0",
            "body": "New features!",
            "published_at": "2025-01-01T00:00:00Z",
            "html_url": "https://github.com/example/releases/v0.7.0",
            "tarball_url": "https://api.github.com/repos/example/tarball/v0.7.0",
            "assets": [],  # No assets
        }

        mock_response = Mock()
        mock_response.read.return_value = json.dumps(api_response).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            has_update, version_info, msg = service.check_for_updates()

        assert has_update is True
        assert version_info is not None
        assert version_info.sha256_url is None
        assert version_info.minisig_url is None

    def test_check_for_updates_no_update_available(self, service, tmp_path):
        """Test when already on latest version."""
        # Set current version to latest
        (tmp_path / "VERSION").write_text("0.7.0\n")

        api_response = {
            "tag_name": "v0.7.0",
            "name": "Version 0.7.0",
            "body": "Current version",
            "published_at": "2025-01-01T00:00:00Z",
            "html_url": "https://github.com/example/releases/v0.7.0",
            "tarball_url": "https://api.github.com/repos/example/tarball/v0.7.0",
            "assets": [],
        }

        mock_response = Mock()
        mock_response.read.return_value = json.dumps(api_response).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            has_update, version_info, msg = service.check_for_updates()

        assert has_update is False
        assert "aktuell" in msg

    def test_check_for_updates_network_error(self, service):
        """Test handling of network errors."""
        import urllib.error

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Network unreachable")):
            has_update, version_info, msg = service.check_for_updates()

        assert has_update is False
        assert version_info is None
        assert "Netzwerkfehler" in msg


class TestVersionCompare:
    """Test _version_compare - Version string comparison."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService."""
        return UpdaterService(app_dir=tmp_path)

    def test_version_compare_greater(self, service):
        """Test v1 > v2."""
        assert service._version_compare("1.0.0", "0.9.0") == 1
        assert service._version_compare("1.1.0", "1.0.0") == 1
        assert service._version_compare("1.0.1", "1.0.0") == 1

    def test_version_compare_less(self, service):
        """Test v1 < v2."""
        assert service._version_compare("0.9.0", "1.0.0") == -1
        assert service._version_compare("1.0.0", "1.1.0") == -1
        assert service._version_compare("1.0.0", "1.0.1") == -1

    def test_version_compare_equal(self, service):
        """Test v1 == v2."""
        assert service._version_compare("1.0.0", "1.0.0") == 0
        assert service._version_compare("0.6.0", "0.6.0") == 0

    def test_version_compare_different_lengths(self, service):
        """Test versions with different number of parts."""
        assert service._version_compare("1.0", "1.0.0") == 0
        assert service._version_compare("1.0.0.1", "1.0.0") == 1
        assert service._version_compare("1.0", "1.0.1") == -1


class TestBackupOperations:
    """Test backup and rollback operations."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService with test files and isolated backup dir."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "VERSION").write_text("0.6.0\n")
        (app_dir / "main.py").write_text("print('hello')")
        (app_dir / "config").mkdir()
        (app_dir / "config" / "settings.json").write_text("{}")

        svc = UpdaterService(app_dir=app_dir)
        # Use temp backup directory instead of real one
        svc.backup_dir = tmp_path / "backups"
        svc.backup_dir.mkdir()
        return svc

    def test_create_backup(self, service):
        """Test backup creation."""
        success, msg = service.create_backup()

        assert success is True
        assert "Backup erstellt" in msg

        # Check backup file exists
        backups = list(service.backup_dir.glob("*.tar.gz"))
        assert len(backups) == 1

    def test_get_available_backups(self, service):
        """Test listing available backups."""
        # Create backup
        service.create_backup()

        backups = service.get_available_backups()
        assert len(backups) == 1
        assert backups[0].version == "0.6.0"

    def test_should_exclude_venv(self, service, tmp_path):
        """Test that .venv is excluded from backup."""
        venv_dir = service.app_dir / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin")

        assert service._should_exclude(venv_dir) is True

    def test_should_exclude_pycache(self, service):
        """Test that __pycache__ is excluded."""
        cache_dir = service.app_dir / "__pycache__"
        cache_dir.mkdir()

        assert service._should_exclude(cache_dir) is True

    def test_should_not_exclude_source(self, service):
        """Test that source files are not excluded."""
        assert service._should_exclude(service.app_dir / "main.py") is False
        assert service._should_exclude(service.app_dir / "config") is False


class TestDownloadAsset:
    """Test _download_asset helper."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService."""
        return UpdaterService(app_dir=tmp_path)

    def test_download_asset_success(self, service, tmp_path):
        """Test successful asset download."""
        dest_path = tmp_path / "asset.txt"

        mock_response = Mock()
        mock_response.read.return_value = b"asset content"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            success, msg = service._download_asset("https://example.com/asset.txt", dest_path)

        assert success is True
        assert msg == "OK"
        assert dest_path.exists()
        assert dest_path.read_bytes() == b"asset content"

    def test_download_asset_network_error(self, service, tmp_path):
        """Test asset download with network error."""
        import urllib.error

        dest_path = tmp_path / "asset.txt"

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            success, msg = service._download_asset("https://example.com/asset.txt", dest_path)

        assert success is False
        assert "Connection refused" in msg


class TestSHA256File:
    """Test _sha256_file helper."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create UpdaterService."""
        return UpdaterService(app_dir=tmp_path)

    def test_sha256_file(self, service, tmp_path):
        """Test SHA256 hash calculation."""
        test_file = tmp_path / "test.txt"
        content = b"hello world"
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = service._sha256_file(test_file)

        assert actual_hash == expected_hash

    def test_sha256_large_file(self, service, tmp_path):
        """Test SHA256 for larger file (chunked reading)."""
        test_file = tmp_path / "large.bin"
        # 5MB file
        content = b"x" * (5 * 1024 * 1024)
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = service._sha256_file(test_file)

        assert actual_hash == expected_hash
