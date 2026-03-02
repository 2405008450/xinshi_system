from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from routers import users, roles, translation_projects, user_roles, project_files, auth, clients, translators, workflow, schedule, leave

app = FastAPI()

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(translation_projects.router)
app.include_router(user_roles.router)
app.include_router(project_files.router)
app.include_router(clients.router)
app.include_router(translators.router)
app.include_router(workflow.router)
app.include_router(schedule.router)
app.include_router(leave.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
                         

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/health/db")
def db_healthcheck(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
