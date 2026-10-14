from secrets import randbelow

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Personal Website API", version="0.1.0")

class Project(BaseModel):
    name: str
    description: str

class Profile(BaseModel):
    name: str
    title: str
    introduction: str
    skills: list[str]
    projects: list[Project]

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/profile", response_model=Profile)
def profile():
    return Profile(
        name="你的名字",
        title="保持好奇，认真创造。",
        introduction="欢迎来到我的个人网站。这里将记录我的学习、项目与思考。这是初版默认内容，之后会逐步替换为真实介绍。",
        skills=["Python", "FastAPI", "Vue 3"],
        projects=[Project(name="个人网站", description="从一个简单的页面开始，搭建属于自己的数字空间。")],
    )


class DiceResult(BaseModel):
    value: int = Field(ge=1, le=6)


@app.post("/api/dice/roll", response_model=DiceResult)
def roll_dice():
    return DiceResult(value=randbelow(6) + 1)
