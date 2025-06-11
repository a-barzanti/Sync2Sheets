.PHONY: venv install start help clean

VENV_DIR = .venv
UV = uv

# Default target when 'make' is run without arguments
.DEFAULT_GOAL := help

venv:
	@echo "🐍 Creating virtual environment in $(VENV_DIR)..."
	$(UV) venv $(VENV_DIR)

install:
	@echo "🔄 Syncing dependencies from pyproject.toml..."
	$(UV) sync -p $(VENV_DIR)

# Main application start
start:
	@echo "🚀 Running the Flet app..."
	flet run main.py

# Clean Python artifacts
clean:
	@echo "🧼 Cleaning virtual environment and caches..."
	rm -rf $(VENV_DIR) __pycache__ .pytest_cache *.pyc *.pyo .mypy_cache .DS_Store uv.lock
	@echo "✅ Cleaned up successfully!"


help:
	@echo ""
	@echo "🛠️  Available make commands:"
	@echo "  make venv     - Create a virtual environment using uv"
	@echo "  make install  - Sync dependencies from pyproject.toml into .venv"
	@echo "  make start    - Launch the tool"
	@echo "  make clean    - Remove virtualenv and Python cache files"
	@echo ""
	@echo "🧙 Activate your virtual environment with:"
	@echo ""
	@echo "    source $(VENV_DIR)/bin/activate"
	@echo ""
	@echo "💤 To deactivate, just run:"
	@echo ""
	@echo "    deactivate"
	@echo ""