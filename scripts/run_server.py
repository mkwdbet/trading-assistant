import sys
import traceback
from pathlib import Path

import uvicorn


if __name__ == "__main__":
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)

    with (log_dir / "server.stdout.log").open("a", encoding="utf-8") as stdout:
        with (log_dir / "server.stderr.log").open("a", encoding="utf-8") as stderr:
            sys.stdout = stdout
            sys.stderr = stderr
            try:
                uvicorn.run(
                    "app.main:app",
                    host="0.0.0.0",
                    port=8000,
                    log_level="info",
                    access_log=True,
                )
            except Exception:
                traceback.print_exc(file=stderr)
                raise
