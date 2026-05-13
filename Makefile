.PHONY: help tei-prefetch tei-up tei-down tei-doctor tei-restart

help:
	@echo "TEI Development Targets:"
	@echo "  make tei-prefetch  - Download models to .cache/tei/"
	@echo "  make tei-up        - Start TEI containers"
	@echo "  make tei-down      - Stop TEI containers"
	@echo "  make tei-doctor    - Run diagnostics"
	@echo "  make tei-restart   - Restart TEI services"

tei-prefetch:
	.venv/bin/python scripts/dev/tei-prefetch.py

tei-up:
	bash scripts/dev/tei-up.sh

tei-down:
	bash scripts/dev/tei-down.sh

tei-doctor:
	.venv/bin/python scripts/dev/tei-doctor.py

tei-restart: tei-down tei-up
