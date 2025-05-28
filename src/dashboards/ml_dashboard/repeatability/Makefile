# Makefile to prepare and run hygiene test configurations

prepare-test:
	@echo "🛠️  Generating configuration JSON files..."
	python prepare_test_configurations.py

run-test:
	@echo "🚀 Running test configurations..."
	python run_test_configurations.py

validate-test:
	@echo "🚀 Validating CSV Files..."
	python validate_test_reports.py

all: prepare-test run-test
	@echo "✅ All tests prepared and executed successfully."
