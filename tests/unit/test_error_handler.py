"""Unit tests for infrastructure.error_handler utilities"""
import pytest
from pydantic import BaseModel, ValidationError

from infrastructure import error_handler
from domain.exceptions import PipelineException


class DummyModel(BaseModel):
    value: int


def _make_validation_error():
    with pytest.raises(ValidationError) as exc:
        DummyModel(value="not-an-int")
    return exc.value


@pytest.mark.unit
def test_handle_errors_validation_error_returns_formatted_message():
    """Decorator should catch ValidationError and return formatted message."""

    @error_handler.handle_errors("Default message")
    def run():
        raise _make_validation_error()

    result = run()
    assert "Validierungsfehler" in result
    assert "❌" in result


@pytest.mark.unit
def test_handle_errors_validation_error_return_tuple():
    """Validation errors should be returned as tuple when requested."""

    @error_handler.handle_errors("Default message", return_tuple=True)
    def run():
        raise _make_validation_error()

    result, err = run()
    assert result is None
    assert "Validierungsfehler" in err


@pytest.mark.unit
def test_handle_errors_pipeline_exception_tuple_return():
    """Should wrap PipelineException and return tuple when requested."""

    @error_handler.handle_errors("Default", return_tuple=True)
    def run():
        raise PipelineException("boom")

    result, err = run()
    assert result is None
    assert "boom" in err


@pytest.mark.unit
def test_handle_errors_unexpected_without_traceback():
    """Should include error type and default message without traceback logging."""

    @error_handler.handle_errors("Something bad", log_traceback=False)
    def run():
        raise RuntimeError("oops")

    result = run()
    assert "RuntimeError" in result
    assert "Something bad" in result


@pytest.mark.unit
def test_handle_errors_return_tuple_passthrough(monkeypatch):
    """Should wrap result into tuple when return_tuple is True."""

    @error_handler.handle_errors("ignored", return_tuple=True)
    def run():
        return 123

    result = run()
    assert result == (123, None)


@pytest.mark.unit
def test_handle_errors_unexpected_with_traceback_tuple():
    """Should include default message and wrap into tuple when log_traceback=True."""

    @error_handler.handle_errors("Tracebacked", return_tuple=True)
    def run():
        raise RuntimeError("explode")

    result, err = run()
    assert result is None
    assert "Tracebacked" in err
    assert "explode" in err


@pytest.mark.unit
def test_safe_execute_variants():
    """safe_execute should wrap success, validation, and pipeline errors."""
    ok_result, ok_err = error_handler.safe_execute(lambda: 42, "err")
    assert ok_result == 42
    assert ok_err is None

    validation_error = _make_validation_error()
    _, val_err = error_handler.safe_execute(lambda: (_ for _ in ()).throw(validation_error), "err")
    assert "Validierungsfehler" in val_err

    _, pipe_err = error_handler.safe_execute(lambda: (_ for _ in ()).throw(PipelineException("x")), "err")
    assert "err" in pipe_err
    assert "x" in pipe_err

    _, unexpected = error_handler.safe_execute(lambda: (_ for _ in ()).throw(RuntimeError("kaput")), "oops")
    assert "kaput" in unexpected
    assert "oops" in unexpected


@pytest.mark.unit
def test_format_and_log_error_variants():
    """format_error/log_and_format_error should branch by exception type."""
    val_err = _make_validation_error()
    formatted = error_handler.format_error(val_err)
    assert "Validierungsfehler" in formatted

    pipe_err = error_handler.format_error(PipelineException("bad"))
    assert "bad" in pipe_err

    generic = error_handler.format_error(ValueError("nope"))
    assert "nope" in generic

    # log_and_format_error should log and return formatted string
    message = error_handler.log_and_format_error(ValueError("logged"), context="ctx")
    assert "logged" in message

    message_pipeline = error_handler.log_and_format_error(PipelineException("pipe"), context="ctx")
    assert "pipe" in message_pipeline

    message_validation = error_handler.log_and_format_error(_make_validation_error(), context="ctx")
    assert "Validierungsfehler" in message_validation


@pytest.mark.unit
def test_handle_errors_multiple_validation_errors():
    """Multiple validation errors should be joined into bullet list."""

    class DuoModel(BaseModel):
        a: int
        b: int

    @error_handler.handle_errors("Default message")
    def run():
        with pytest.raises(ValidationError) as exc:
            DuoModel(a="x", b="y")
        raise exc.value

    result = run()
    assert "- a:" in result
    assert "- b:" in result


@pytest.mark.unit
def test_safe_execute_return_tuple_flag_passthrough():
    """When safe_execute succeeds, return_tuple semantics are preserved."""
    def func():
        return (1, 2)

    result, err = error_handler.safe_execute(func, "ignored")
    assert result == (1, 2)
    assert err is None
