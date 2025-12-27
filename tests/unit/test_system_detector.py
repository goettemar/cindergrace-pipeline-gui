"""Tests for SystemDetector service."""
import platform
import subprocess
from unittest.mock import Mock, patch, MagicMock

import pytest

from services.system_detector import SystemDetector, DependencyStatus


class TestDependencyStatus:
    """Tests for DependencyStatus dataclass."""

    def test_default_values(self):
        """Test default values."""
        status = DependencyStatus(name="Test", installed=False)
        assert status.name == "Test"
        assert status.installed is False
        assert status.version is None
        assert status.path is None
        assert status.required is True
        assert status.message == ""

    def test_all_values(self):
        """Test with all values set."""
        status = DependencyStatus(
            name="Python",
            installed=True,
            version="3.11.0",
            path="/usr/bin/python3",
            required=True,
            message="OK"
        )
        assert status.name == "Python"
        assert status.installed is True
        assert status.version == "3.11.0"
        assert status.path == "/usr/bin/python3"
        assert status.required is True
        assert status.message == "OK"


class TestSystemDetector:
    """Tests for SystemDetector class."""

    @pytest.fixture
    def detector(self):
        """Create SystemDetector instance."""
        return SystemDetector()

    # ========================================================================
    # OS Detection Tests
    # ========================================================================

    def test_get_os_linux(self, detector):
        """Test OS detection on Linux."""
        with patch.object(platform, 'system', return_value='Linux'):
            assert detector.get_os() == "linux"

    def test_get_os_windows(self, detector):
        """Test OS detection on Windows."""
        with patch.object(platform, 'system', return_value='Windows'):
            assert detector.get_os() == "windows"

    def test_get_os_macos(self, detector):
        """Test OS detection on macOS."""
        with patch.object(platform, 'system', return_value='Darwin'):
            assert detector.get_os() == "macos"

    def test_get_os_version(self, detector):
        """Test OS version detection."""
        with patch.object(platform, 'version', return_value='5.15.0-generic'):
            assert detector.get_os_version() == "5.15.0-generic"

    def test_get_architecture(self, detector):
        """Test architecture detection."""
        with patch.object(platform, 'machine', return_value='x86_64'):
            assert detector.get_architecture() == "x86_64"

    def test_get_architecture_arm(self, detector):
        """Test ARM architecture detection."""
        with patch.object(platform, 'machine', return_value='arm64'):
            assert detector.get_architecture() == "arm64"

    # ========================================================================
    # Python Check Tests
    # ========================================================================

    def test_check_python_returns_dependency_status(self, detector):
        """Test that check_python returns DependencyStatus."""
        result = detector.check_python()
        assert isinstance(result, DependencyStatus)
        assert result.name == "Python"
        assert result.installed is True

    def test_check_python_has_version(self, detector):
        """Test that Python version is detected."""
        result = detector.check_python()
        assert result.version is not None
        assert "." in result.version  # e.g., "3.11.0"

    def test_check_python_old_version_message(self, detector):
        """Test warning message for old Python version."""
        with patch.object(platform, 'python_version', return_value='3.8.0'):
            result = detector.check_python()
            assert "3.10+" in result.message
            assert "empfohlen" in result.message

    def test_check_python_current_version_ok(self, detector):
        """Test OK message for current Python version."""
        with patch.object(platform, 'python_version', return_value='3.11.0'):
            result = detector.check_python()
            assert result.message == "OK"

    # ========================================================================
    # NVIDIA Check Tests
    # ========================================================================

    def test_check_nvidia_not_found(self, detector):
        """Test when nvidia-smi is not found."""
        with patch('shutil.which', return_value=None):
            result = detector.check_nvidia()
            assert result.installed is False
            assert "nicht gefunden" in result.message

    def test_check_nvidia_success(self, detector):
        """Test successful nvidia-smi detection."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "NVIDIA GeForce RTX 3080, 535.129.03"

        with patch('shutil.which', return_value='/usr/bin/nvidia-smi'):
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_nvidia()
                assert result.installed is True
                assert result.version == "535.129.03"
                assert "RTX 3080" in result.message

    def test_check_nvidia_timeout(self, detector):
        """Test nvidia-smi timeout handling."""
        with patch('shutil.which', return_value='/usr/bin/nvidia-smi'):
            with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("nvidia-smi", 10)):
                result = detector.check_nvidia()
                assert result.installed is False
                assert "Timeout" in result.message

    def test_check_nvidia_error(self, detector):
        """Test nvidia-smi error handling."""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch('shutil.which', return_value='/usr/bin/nvidia-smi'):
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_nvidia()
                assert result.installed is False

    # ========================================================================
    # CUDA Check Tests
    # ========================================================================

    def test_check_cuda_via_nvcc(self, detector):
        """Test CUDA detection via nvcc."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Cuda compilation tools, release 12.1, V12.1.66"

        with patch('shutil.which', return_value='/usr/local/cuda/bin/nvcc'):
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_cuda()
                assert result.installed is True
                assert "12.1" in result.version

    def test_check_cuda_via_nvidia_smi(self, detector):
        """Test CUDA detection via nvidia-smi fallback."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "| NVIDIA-SMI 535.129.03   Driver Version: 535.129.03   CUDA Version: 12.2     |"

        with patch('shutil.which', return_value=None):  # No nvcc
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_cuda()
                assert result.installed is True
                assert "12.2" in result.version

    def test_check_cuda_not_found(self, detector):
        """Test when CUDA is not found."""
        with patch('shutil.which', return_value=None):
            with patch('subprocess.run', side_effect=FileNotFoundError()):
                result = detector.check_cuda()
                assert result.installed is False
                assert "nicht gefunden" in result.message

    # ========================================================================
    # Git Check Tests
    # ========================================================================

    def test_check_git_not_found(self, detector):
        """Test when git is not installed."""
        with patch('shutil.which', return_value=None):
            result = detector.check_git()
            assert result.installed is False
            assert result.required is False  # Git is optional
            assert "optional" in result.message.lower()

    def test_check_git_success(self, detector):
        """Test successful git detection."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "git version 2.34.1"

        with patch('shutil.which', return_value='/usr/bin/git'):
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_git()
                assert result.installed is True
                assert result.version == "2.34.1"

    # ========================================================================
    # FFmpeg Check Tests
    # ========================================================================

    def test_check_ffmpeg_not_found(self, detector):
        """Test when ffmpeg is not installed."""
        with patch('shutil.which', return_value=None):
            result = detector.check_ffmpeg()
            assert result.installed is False
            assert result.required is True

    def test_check_ffmpeg_success(self, detector):
        """Test successful ffmpeg detection."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c) 2000-2021"

        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            with patch('subprocess.run', return_value=mock_result):
                result = detector.check_ffmpeg()
                assert result.installed is True
                assert "4.4.2" in result.version

    # ========================================================================
    # ComfyUI Connection Tests
    # ========================================================================

    def test_check_comfyui_connection_success(self, detector):
        """Test successful ComfyUI connection."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = detector.check_comfyui_connection()
            assert result.installed is True
            assert "Verbunden" in result.message

    def test_check_comfyui_connection_failed(self, detector):
        """Test failed ComfyUI connection."""
        import urllib.error

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            result = detector.check_comfyui_connection()
            assert result.installed is False
            assert "Keine Verbindung" in result.message

    def test_check_comfyui_custom_url(self, detector):
        """Test ComfyUI connection with custom URL."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response) as mock_open:
            result = detector.check_comfyui_connection("http://custom:9000")
            assert result.path == "http://custom:9000"

    # ========================================================================
    # System Summary Tests
    # ========================================================================

    def test_get_system_summary_structure(self, detector):
        """Test system summary structure."""
        with patch.object(detector, 'check_python') as mock_py:
            with patch.object(detector, 'check_nvidia') as mock_nv:
                with patch.object(detector, 'check_cuda') as mock_cuda:
                    with patch.object(detector, 'check_git') as mock_git:
                        with patch.object(detector, 'check_ffmpeg') as mock_ff:
                            with patch.object(detector, 'check_comfyui_connection') as mock_comfy:
                                # Setup mocks
                                mock_py.return_value = DependencyStatus("Python", True)
                                mock_nv.return_value = DependencyStatus("NVIDIA", True)
                                mock_cuda.return_value = DependencyStatus("CUDA", True)
                                mock_git.return_value = DependencyStatus("Git", True, required=False)
                                mock_ff.return_value = DependencyStatus("ffmpeg", True)
                                mock_comfy.return_value = DependencyStatus("ComfyUI", True)

                                summary = detector.get_system_summary()

                                # Check structure
                                assert "os" in summary
                                assert "dependencies" in summary
                                assert "stats" in summary
                                assert "ready" in summary

    def test_get_system_summary_os_info(self, detector):
        """Test OS info in summary."""
        with patch.object(platform, 'system', return_value='Linux'):
            with patch.object(detector, 'check_python', return_value=DependencyStatus("Python", True)):
                with patch.object(detector, 'check_nvidia', return_value=DependencyStatus("NVIDIA", True)):
                    with patch.object(detector, 'check_cuda', return_value=DependencyStatus("CUDA", True)):
                        with patch.object(detector, 'check_git', return_value=DependencyStatus("Git", True)):
                            with patch.object(detector, 'check_ffmpeg', return_value=DependencyStatus("ffmpeg", True)):
                                with patch.object(detector, 'check_comfyui_connection', return_value=DependencyStatus("ComfyUI", True)):
                                    summary = detector.get_system_summary()
                                    assert summary["os"]["name"] == "linux"
                                    assert summary["os"]["display_name"] == "Linux"

    def test_get_system_summary_ready_when_all_required_installed(self, detector):
        """Test ready=True when all required deps are installed."""
        with patch.object(detector, 'check_python', return_value=DependencyStatus("Python", True)):
            with patch.object(detector, 'check_nvidia', return_value=DependencyStatus("NVIDIA", True)):
                with patch.object(detector, 'check_cuda', return_value=DependencyStatus("CUDA", True)):
                    with patch.object(detector, 'check_git', return_value=DependencyStatus("Git", False, required=False)):
                        with patch.object(detector, 'check_ffmpeg', return_value=DependencyStatus("ffmpeg", True)):
                            with patch.object(detector, 'check_comfyui_connection', return_value=DependencyStatus("ComfyUI", True)):
                                summary = detector.get_system_summary()
                                assert summary["ready"] is True

    def test_get_system_summary_not_ready_when_required_missing(self, detector):
        """Test ready=False when required dep is missing."""
        with patch.object(detector, 'check_python', return_value=DependencyStatus("Python", True)):
            with patch.object(detector, 'check_nvidia', return_value=DependencyStatus("NVIDIA", False, required=True)):
                with patch.object(detector, 'check_cuda', return_value=DependencyStatus("CUDA", True)):
                    with patch.object(detector, 'check_git', return_value=DependencyStatus("Git", True)):
                        with patch.object(detector, 'check_ffmpeg', return_value=DependencyStatus("ffmpeg", True)):
                            with patch.object(detector, 'check_comfyui_connection', return_value=DependencyStatus("ComfyUI", True)):
                                summary = detector.get_system_summary()
                                assert summary["ready"] is False
                                assert summary["stats"]["missing_required"] == 1

    # ========================================================================
    # Status Icon & Formatting Tests
    # ========================================================================

    def test_get_status_icon_installed(self, detector):
        """Test status icon for installed dependency."""
        dep = DependencyStatus("Test", installed=True)
        assert detector.get_status_icon(dep) == "OK"

    def test_get_status_icon_missing_required(self, detector):
        """Test status icon for missing required dependency."""
        dep = DependencyStatus("Test", installed=False, required=True)
        assert detector.get_status_icon(dep) == "FEHLT"

    def test_get_status_icon_missing_optional(self, detector):
        """Test status icon for missing optional dependency."""
        dep = DependencyStatus("Test", installed=False, required=False)
        assert detector.get_status_icon(dep) == "Optional"

    def test_format_dependency_line_basic(self, detector):
        """Test basic dependency line formatting."""
        dep = DependencyStatus("Python", installed=True, version="3.11.0")
        line = detector.format_dependency_line(dep)
        assert "[OK]" in line
        assert "Python" in line
        assert "(3.11.0)" in line

    def test_format_dependency_line_with_message(self, detector):
        """Test dependency line with message."""
        dep = DependencyStatus("CUDA", installed=False, message="nicht gefunden")
        line = detector.format_dependency_line(dep)
        assert "[FEHLT]" in line
        assert "CUDA" in line
        assert "nicht gefunden" in line

    def test_format_dependency_line_ok_message_hidden(self, detector):
        """Test that 'OK' message is not shown in formatting."""
        dep = DependencyStatus("Python", installed=True, version="3.11.0", message="OK")
        line = detector.format_dependency_line(dep)
        assert line.count("OK") == 1  # Only in [OK], not as message
