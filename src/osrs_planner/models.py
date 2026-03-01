from enum import Enum
from pydantic import BaseModel


class AccountMode(Enum):
    normal = "Normal"
    ironman = "Ironman"
    hardcore_ironman = "Hardcore Ironman"
    ultimate_ironman = "Ultimate Ironman"
    group_ironman = "Group Ironman"
    hardcore_group_ironman = "Hardcore Group Ironman"


class Skill(BaseModel):
    name: str
    level: int
    xp: int


class Account(BaseModel):
    rsn: str                                            # OldSchool RuneScape Username (ex. "Tiger0295")
    mode: AccountMode                                   # Gamemode of your account (ex. Ironman)
    skills: dict[str, Skill]                            # Dictionary to map all 24 Skills in the game
    is_skiller: bool = False                            # Is account a Level 3 Skiller? - Defaults to False if not set to True
    is_pure: bool = False                               # Is account a Level 1 Defence Pure? - Defaults to False if not set to True


class Task(BaseModel):
    task_type: str
    skill: str
    name: str
    from_level: int
    to_level: int
    xp_per_hour: float
    marks_per_hour: float
    combat_requirement: bool = False


class Goal(BaseModel):
    id: str
    name: str
    description: str
    target_marks: int
    tasks: list[Task]
