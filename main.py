from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine, get_db
from models import AppNotification, ClientContact
from routers import users, roles, translation_projects, user_roles, project_files, auth, clients, client_contacts, translators, workflow, schedule, leave, consultations, finance, sub_orders, notifications

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(translation_projects.router)
app.include_router(user_roles.router)
app.include_router(project_files.router)
app.include_router(clients.router)
app.include_router(client_contacts.router)
app.include_router(translators.router)
app.include_router(workflow.router)
app.include_router(schedule.router)
app.include_router(leave.router)
app.include_router(consultations.router)
app.include_router(finance.router)
app.include_router(sub_orders.router)
app.include_router(notifications.router)


@app.on_event("startup")
def ensure_runtime_tables():
    ClientContact.__table__.create(bind=engine, checkfirst=True)
    AppNotification.__table__.create(bind=engine, checkfirst=True)


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
