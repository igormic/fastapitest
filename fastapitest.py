from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    status = Column(String)

class PomodoroSession(Base):
    __tablename__ = "pomodoro_sessions"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    completed = Column(Boolean)

Base.metadata.create_all(bind=engine)

app = FastAPI()

class TaskModel(BaseModel):
    id: int
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: str = Field("TODO", pattern="^(TODO|in_progress|done)$")

class PomodoroSessionModel(BaseModel):
    task_id: int
    start_time: datetime
    end_time: datetime
    completed: bool

@app.post("/tasks", response_model=TaskModel)
def create_task(task: TaskModel):
    db = SessionLocal()
    if db.query(Task).filter(Task.title == task.title).first():
        raise HTTPException(status_code=400, detail="Tytuł zadania musi być unikalny.")
    db_task = Task(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks", response_model=List[TaskModel])
def get_tasks(status: Optional[str] = Query(None, pattern="^(TODO|in_progress|done)$")):
    db = SessionLocal()
    if status:
        return db.query(Task).filter(Task.status == status).all()
    return db.query(Task).all()

@app.get("/tasks/{task_id}", response_model=TaskModel)
def get_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    return task

@app.put("/tasks/{task_id}", response_model=TaskModel)
def update_task(task_id: int, updated_task: TaskModel):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    if db.query(Task).filter(Task.title == updated_task.title, Task.id != task_id).first():
        raise HTTPException(status_code=400, detail="Tytuł zadania musi być unikalny.")
    task.title = updated_task.title
    task.description = updated_task.description
    task.status = updated_task.status
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    db.delete(task)
    db.commit()
    return {"message": "Zadanie zostało usunięte."}

@app.post("/pomodoro", response_model=PomodoroSessionModel)
def create_pomodoro(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    if db.query(PomodoroSession).filter(PomodoroSession.task_id == task_id, PomodoroSession.completed == False).first():
        raise HTTPException(status_code=400, detail="Zadanie już ma aktywny timer.")
    start_time = datetime.now()
    session = PomodoroSession(task_id=task_id, start_time=start_time, end_time=start_time + timedelta(minutes=25), completed=False)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@app.post("/pomodoro/{task_id}/stop")
def stop_pomodoro(task_id: int):
    db = SessionLocal()
    session = db.query(PomodoroSession).filter(PomodoroSession.task_id == task_id, PomodoroSession.completed == False).first()
    if not session:
        raise HTTPException(status_code=400, detail="Brak aktywnego timera dla zadania.")
    session.completed = True
    session.end_time = datetime.now()
    db.commit()
    db.refresh(session)
    return {"message": "Timer został zatrzymany."}

@app.get("/pomodoro/stats")
def get_pomodoro_stats():
    db = SessionLocal()
    stats = {}
    total_time = timedelta()
    for session in db.query(PomodoroSession).filter(PomodoroSession.completed == True).all():
        stats[session.task_id] = stats.get(session.task_id, 0) + 1
        total_time += session.end_time - session.start_time
    return {"sessions_per_task": stats, "total_time": str(total_time)}
