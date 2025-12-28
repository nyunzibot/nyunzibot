
import sys
import pytest

if __name__ == "__main__":
    # Run pytest on all tests folder
    # -v: verbose
    # -s: capture=no (print output directly)
    # -p no:warnings to reduce noise
    ret = pytest.main(["tests", "-v", "-p", "no:warnings"])
    sys.exit(ret)
