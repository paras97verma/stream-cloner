# ==============================================================================
# Stream Cloner — Makefile
# Professional build, packaging, and local execution manager.
#
# Usage:
#   make              Run app locally (starts Vue.js + Python desktop app)
#   make run          Run app locally
#   make build-fe     Build Vue.js production frontend assets
#   make dmg          Generate macOS DMG standalone installer
#   make exe          Generate Windows EXE standalone installer
#   make test         Run test suite with pytest
#   make clean        Clean build artifacts, caches, and distributions
#   make help         Display available make targets
# ==============================================================================

SHELL := /usr/bin/env bash
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: all run build-fe dmg mac macos exe win windows msi test clean help

# Default target: Run local application directly
all: run

# Run local desktop application
run:
	@chmod +x $(PROJECT_ROOT)/run.sh
	@$(PROJECT_ROOT)/run.sh

# Build Vue.js frontend production bundle
build-fe:
	@echo "Building Vue.js production bundle..."
	@cd $(PROJECT_ROOT)/frontend && npm install && npm run build

# Generate macOS DMG installer
dmg: build-fe
mac: dmg
macos: dmg
	@echo "Generating standalone macOS DMG installer..."
	@bash $(PROJECT_ROOT)/scripts/build/build-macos-dmg.sh

# Generate Windows EXE / MSI
exe: build-fe
win: exe
windows: exe
msi: exe
	@echo "Generating Windows standalone executable..."
	@if [ -f "$(PROJECT_ROOT)/scripts/build/build-windows-exe.bat" ] && [ -n "$$WINDIR" ]; then \
		cmd.exe /c $(PROJECT_ROOT)/scripts/build/build-windows-exe.bat; \
	elif [ -x "$(PROJECT_ROOT)/.venv/bin/python" ]; then \
		$(PROJECT_ROOT)/.venv/bin/python $(PROJECT_ROOT)/scripts/build/build_installer.py; \
	else \
		python3 $(PROJECT_ROOT)/scripts/build/build_installer.py; \
	fi

# Run pytest test suite
test:
	@echo "Executing pytest suite..."
	@if [ -x "$(PROJECT_ROOT)/.venv/bin/pytest" ]; then \
		$(PROJECT_ROOT)/.venv/bin/pytest $(PROJECT_ROOT)/tests -v; \
	else \
		pytest $(PROJECT_ROOT)/tests -v; \
	fi

# Clean build artifacts, caches, and bundles
clean:
	@echo "Cleaning build artifacts, caches, and temporary files..."
	@rm -rf $(PROJECT_ROOT)/build \
	        $(PROJECT_ROOT)/dist \
	        $(PROJECT_ROOT)/*.spec \
	        $(PROJECT_ROOT)/.pytest_cache \
	        $(PROJECT_ROOT)/src/stream_cloner/web/dist \
	        $(PROJECT_ROOT)/assets/StreamCloner.iconset \
	        $(PROJECT_ROOT)/assets/*.icns \
	        $(PROJECT_ROOT)/assets/*.ico \
	        $(PROJECT_ROOT)/assets/*.png \
	        $(PROJECT_ROOT)/.venv/app.pid
	@find $(PROJECT_ROOT) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(PROJECT_ROOT) -type f -name "*.py[cod]" -delete 2>/dev/null || true
	@echo "Cleanup completed successfully."

# Help summary
help:
	@echo "=============================================================="
	@echo " Stream Cloner — Makefile Targets"
	@echo "=============================================================="
	@echo "  make (or make run)   Start app locally via Vue.js & pywebview"
	@echo "  make build-fe        Compile Vue.js 3 + Tailwind CSS frontend"
	@echo "  make dmg             Generate macOS DMG standalone installer"
	@echo "  make exe             Generate Windows standalone EXE installer"
	@echo "  make test            Run pytest test suite"
	@echo "  make clean           Remove build/, dist/, caches"
	@echo "  make help            Show this command summary"
	@echo "=============================================================="
