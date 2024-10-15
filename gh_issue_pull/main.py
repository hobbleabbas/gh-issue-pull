from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from gh_issue_pull.helpers import fetch_unused_issue, pull_all_swebench_entries, SWEBENCH_DB_PATH, obfuscate


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App is starting up")
    if not SWEBENCH_DB_PATH.exists():
        pull_all_swebench_entries()

    yield  # The app runs between startup and shutdown here

    print("App is shutting down")


app = FastAPI(lifespan=lifespan)


@app.get("/task")
async def get_task():
    """
    Gets the current problem to be solved by validators, as a ProblemStatement object
    """
    try:
        unused_issue = fetch_unused_issue()
        unused_issue.problem_statement = obfuscate(unused_issue)
        return unused_issue.model_dump()
    except Exception as e:
        print("Internal server error:", e)
        raise HTTPException(status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

# Pull codebases to provide oracle files
