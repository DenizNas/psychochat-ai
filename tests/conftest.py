import os
import sys

# Isolate all tests to a separate test database file, keeping development database intact
os.environ["DATABASE_URL"] = "sqlite:///data/psikochat_test.db"
