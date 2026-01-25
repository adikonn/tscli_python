"""Data models for TestSys entities."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Problem:
    """Represents a problem in a contest."""

    problem_id: str
    problem_name: str


@dataclass
class Compiler:
    """Represents a compiler/language option."""

    compiler_id: str
    compiler_name: str
    compiler_lang: str


@dataclass
class Test:
    """Represents a test case result."""

    test_id: str
    result: str
    time: str
    memory: str
    comment: str


@dataclass
class Submission:
    """Represents a solution submission."""

    id: str
    problem: str
    compiler: str
    result: str
    time: str


@dataclass
class Contest:
    """Represents a contest."""

    id: str
    name: str
    status: str
    statement_url: Optional[str] = None
