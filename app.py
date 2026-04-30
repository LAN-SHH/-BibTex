from __future__ import annotations

from bibtex_mvp.license_gate.bootstrap import AppBootstrap

AUTO_ACCEPT_THRESHOLD = 0.92
CANDIDATE_FLOOR_THRESHOLD = 0.80


def main() -> int:
    bootstrap = AppBootstrap(
        auto_accept_threshold=AUTO_ACCEPT_THRESHOLD,
        candidate_floor_threshold=CANDIDATE_FLOOR_THRESHOLD,
    )
    return bootstrap.run()


if __name__ == "__main__":
    raise SystemExit(main())
