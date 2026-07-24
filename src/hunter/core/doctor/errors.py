"""Shared exceptions for the SPEC-077 doctor/update framework."""


class DoctorError(Exception):
    """Base error for the doctor/update framework.

    The framework is designed to degrade gracefully; this error type is
    reserved for programming-level misuse (e.g. a disallowed git
    subcommand requested directly) and is never raised for environmental
    conditions, which are reported as check results instead.
    """
