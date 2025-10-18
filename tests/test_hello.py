import subprocess
import sys
from io import StringIO
import contextlib

from hello import main

@contextlib.contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    with contextlib.redirect_stdout(new_out), contextlib.redirect_stderr(new_err):
        yield new_out, new_err

def test_main(capsys):
    with captured_output() as (out, err):
        main()
    assert out.getvalue().strip() == "Hello, World!"
    assert err.getvalue() == ""