import textwrap

import pytest

from jupythunder2.kernel import KernelSession


@pytest.fixture(scope="module")
def kernel_session():
    with KernelSession() as session:
        yield session


def test_execute_simple_expression(kernel_session):
    code = "sum(range(5))"
    result = kernel_session.execute(code)

    assert result.succeeded
    assert result.result == "10"
    assert result.stderr == ""
    assert result.stdout == ""


def test_execute_with_stdout(kernel_session):
    code = textwrap.dedent(
        """
        for i in range(3):
            print(i)
        """
    ).strip()

    result = kernel_session.execute(code)

    assert result.succeeded
    assert result.stdout == "0\n1\n2\n"


def test_execute_error(kernel_session):
    result = kernel_session.execute("1 / 0")

    assert not result.succeeded
    assert result.error is not None
    assert "ZeroDivisionError" in result.error.name or result.error.value
    assert result.error.traceback
