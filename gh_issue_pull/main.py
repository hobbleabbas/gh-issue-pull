from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from gh_issue_pull.classes import SWEBenchEntry, ProblemStatement
from gh_issue_pull.helpers import fetch_unused_issue, convert_swebench_entry_to_problem_statement
import asyncio
import bittensor

UPDATING_PROBLEM_STATEMENT: bool = False
CURRENT_SWEBENCH_ENTRY: SWEBenchEntry | None = None
CURRENT_PROBLEM_STATEMENT: ProblemStatement | None = None
UPDATE_LENGTH: int = 5

subtensor = bittensor.subtensor(network='finney')  # Connect to the 'finney' network

async def block_listener():
    previous_block = 0

    while True:
        try:
            current_block = subtensor.get_current_block()

            # If the number of blocks elapsed is greater than UPDATE_LENGTH, update the problem statement
            if current_block != previous_block and current_block - previous_block >= UPDATE_LENGTH:
                print(f"New block mined: {current_block}")
                previous_block = current_block
                await update_current_problem_statement()

            # Sleep for a short period to avoid overloading the network with requests
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error in block listener: {e}")
            await asyncio.sleep(5)  # Wait longer if there's an error


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    task = asyncio.create_task(block_listener())
    try:
        yield
    finally:
        # Shutdown code
        task.cancel()
        await task

app = FastAPI(lifespan=lifespan)

async def update_current_problem_statement():
    """
    Updates current problem statement status to used, and fetches another problem, then obfuscate problem statement
    """
    global UPDATING_PROBLEM_STATEMENT
    global CURRENT_SWEBENCH_ENTRY
    global CURRENT_PROBLEM_STATEMENT

    while True:
        if UPDATING_PROBLEM_STATEMENT:
            print("Already updating problem statement. Waiting for completion...")
            return

        print("Updating problem statement...")

        UPDATING_PROBLEM_STATEMENT = True

        # Select new SWE bench entry
        CURRENT_SWEBENCH_ENTRY = fetch_unused_issue()

        # Obfuscate and update the statement
        CURRENT_PROBLEM_STATEMENT = convert_swebench_entry_to_problem_statement(CURRENT_SWEBENCH_ENTRY)

        UPDATING_PROBLEM_STATEMENT = False
        print(f"Updated problem statement. Current instance id: {CURRENT_SWEBENCH_ENTRY.instance_id}")
        return


@app.get("/task")
async def get_task(validator_id: str):
    """
    Gets the current problem to be solved by validators, as a ProblemStatement object
    """
    try:
        # Validate validator uid: todo
        if validator_id == "":
            raise HTTPException(status_code=403, detail="Unauthorized")

        if UPDATING_PROBLEM_STATEMENT:
            raise HTTPException(status_code=503, detail="Updating problem statement. Please try again.")

        # Retrieve the current epoch problem instance
        return CURRENT_PROBLEM_STATEMENT.model_dump()
    except Exception as e:
        print("Internal server error:", e)
        raise HTTPException(status_code=500)

if __name__ == "__main__":
    # Set up initial problem statement
    update_current_problem_statement()

    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

# Authenticate validator uid
# Pull codebases to provide oracle files