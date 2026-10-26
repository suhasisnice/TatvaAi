.PHONY: up seed demo-local test verify evaluate tamper down

up:            ## build and start everything
	docker compose up --build -d
seed:          ## generate synthetic data, seed the database, run the pipeline on every application
	docker compose exec backend python scripts/seed.py --reset
test:          ## backend + frontend tests (no Docker needed)
	python -m pytest tests -q
	cd frontend && npm test
verify:        ## prove every planted flag is caught
	python scripts/verify_planted.py
evaluate:      ## write reports/evaluation.md
	python scripts/evaluate.py
tamper:        ## live demo: break the audit chain (undo with: python scripts/tamper_audit_demo.py --restore)
	docker compose exec backend python scripts/tamper_audit_demo.py
down:
	docker compose down
