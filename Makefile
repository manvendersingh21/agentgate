.PHONY: demo install test clean

demo: install
	@echo "🚀 Starting AgentGate Demo (offline mode)"
	@echo "Dashboard will be available at http://localhost:8000"
	@cd dashboard && python3 server.py

install:
	@echo "📦 Installing dependencies..."
	@pip install -q -r requirements.txt
	@pip install -q -r demo-target/requirements.txt

test:
	@echo "🧪 Running tests..."
	@python3 -m pytest -q

test-jev:
	@echo "🔑 Testing Jev API connection..."
	@python3 scripts/jev_smoke.py

clean:
	@echo "🧹 Cleaning up..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

help:
	@echo "AgentGate - Autonomous PR Safety Loop"
	@echo ""
	@echo "Commands:"
	@echo "  make demo      - Start offline demo (no API keys needed)"
	@echo "  make install   - Install dependencies"
	@echo "  make test      - Run test suite"
	@echo "  make test-jev  - Test Jev API connection (requires JEV_API_KEY)"
	@echo "  make clean     - Clean build artifacts"
