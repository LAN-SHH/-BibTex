from __future__ import annotations

from bibtex_mvp.license_gate.bootstrap import AppBootstrap


def main() -> int:
    bootstrap = AppBootstrap()
    return bootstrap.run()


if __name__ == "__main__":
    raise SystemExit(main())
