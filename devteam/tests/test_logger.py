"""Tests for the logging configuration utility module."""

import logging

import pytest

from devteam.utils.logger import get_logger, setup_logging


# ── setup_logging Tests ──────────────────────────────────────────────────


def test_setup_logging():
    """setup_logging should configure the root logger."""
    setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_default_level():
    """setup_logging with no args should default to INFO."""
    setup_logging()
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_suppresses_noisy_loggers():
    """setup_logging should suppress httpx, httpcore, and langchain loggers."""
    setup_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("langchain").level == logging.WARNING


# ── get_logger Tests ─────────────────────────────────────────────────────


def test_get_logger():
    """get_logger should return a logger under the devteam namespace."""
    logger = get_logger("pm")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "devteam.pm"


def test_get_logger_different_names():
    """Different names should produce different loggers."""
    logger_a = get_logger("agents.pm")
    logger_b = get_logger("agents.architect")
    assert logger_a.name != logger_b.name


def test_get_logger_is_usable():
    """The returned logger should be able to log messages without error."""
    setup_logging("DEBUG")
    logger = get_logger("test")
    # Should not raise
    logger.info("Test message from test_logger")
    logger.debug("Debug message")
    logger.warning("Warning message")
