"""Initialize the local-private Personal OS runtime database."""
from __future__ import annotations

from personal_os.runtime import initialize_runtime


def main() -> int:
    runtime=initialize_runtime()
    runtime.engine.dispose()
    print(runtime.database_path)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
