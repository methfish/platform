web: cd backend && gunicorn -w 4 -k uvicorn.workers.UvicornWorker --timeout 60 app.main:app
release: cd backend && alembic upgrade head
