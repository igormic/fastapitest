from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta

app = FastAPI()

class Task(BaseModel):
    id: int
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: str = Field("TODO", pattern="^(TODO|in_progress|done)$")

class PomodoroSession(BaseModel):
    task_id: int
    start_time: datetime
    end_time: datetime
    completed: bool

tasks = []
pomodoro_sessions = []

@app.post("/tasks", response_model=Task)
def create_task(task: Task):
    if any(existing_task.title == task.title for existing_task in tasks):
        raise HTTPException(status_code=400, detail="Tytuł zadania musi być unikalny.")
    task.id = len(tasks) + 1
    tasks.append(task)
    return task

@app.get("/tasks", response_model=List[Task])
def get_tasks(status: Optional[str] = Query(None, pattern="^(TODO|in_progress|done)$")):
    if status:
        return [task for task in tasks if task.status == status]
    return tasks

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    task = next((task for task in tasks if task.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, updated_task: Task):
    task = next((task for task in tasks if task.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    if any(existing_task.title == updated_task.title and existing_task.id != task_id for existing_task in tasks):
        raise HTTPException(status_code=400, detail="Tytuł zadania musi być unikalny.")
    task.title = updated_task.title
    task.description = updated_task.description
    task.status = updated_task.status
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    global tasks
    task = next((task for task in tasks if task.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    tasks = [task for task in tasks if task.id != task_id]
    return {"message": "Zadanie zostało usunięte."}

@app.post("/pomodoro", response_model=PomodoroSession)
def create_pomodoro(task_id: int):
    task = next((task for task in tasks if task.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie o podanym ID nie istnieje.")
    if any(session.task_id == task_id and not session.completed for session in pomodoro_sessions):
        raise HTTPException(status_code=400, detail="Zadanie już ma aktywny timer.")
    start_time = datetime.now()
    session = PomodoroSession(task_id=task_id, start_time=start_time, end_time=start_time + timedelta(minutes=25), completed=False)
    pomodoro_sessions.append(session)
    return session

@app.post("/pomodoro/{task_id}/stop")
def stop_pomodoro(task_id: int):
    session = next((session for session in pomodoro_sessions if session.task_id == task_id and not session.completed), None)
    if not session:
        raise HTTPException(status_code=400, detail="Brak aktywnego timera dla zadania.")
    session.completed = True
    session.end_time = datetime.now()
    return {"message": "Timer został zatrzymany."}

@app.get("/pomodoro/stats")
def get_pomodoro_stats():
    stats = {}
    total_time = timedelta()
    for session in pomodoro_sessions:
        if session.completed:
            stats[session.task_id] = stats.get(session.task_id, 0) + 1
            total_time += session.end_time - session.start_time
    return {"sessions_per_task": stats, "total_time": str(total_time)}