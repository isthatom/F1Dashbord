.PHONY: install test lint typecheck run preview refresh

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy config src main.py

run:
	python main.py

preview:
	streamlit run app.py

refresh: lint typecheck test run
	@echo "Data refreshed. Hit Refresh in Power BI."