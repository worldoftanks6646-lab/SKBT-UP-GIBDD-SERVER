import os


os.environ.setdefault(
    "DATABASE_URL", "postgresql://gibdd:gibdd@localhost:5432/gibdd_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")
