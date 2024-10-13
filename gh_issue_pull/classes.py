from pydantic import BaseModel
from typing import Optional

class SWEBenchEntry(BaseModel):
    instance_id: str
    text: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: Optional[str]
    created_at: str
    patch: str
    used: bool

class ProblemStatement(BaseModel):
    problem_statement: str
    repo: str
    repo_download_url: str
    base_commit: str
    hints_text: str