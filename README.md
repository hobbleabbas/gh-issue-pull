# gh-issue-pull

Stateless endpoint to sample obfuscated issues from SWEBench.

## Running
First, set your `.env` using the `.env.example` file. Then:
```shell
poetry install
poetry shell
cd gh_issue_pull
uvicorn main:app --reload
```
The server will take a while to start up as it has to pull all the SWEBench issues and save them to a local db.

Test the program by running
```shell
curl "http://127.0.0.1:8000/task" | jq
```

If you want to quickly make the endpoint publicly available, the easiest way is to use localtunnel:
```shell
lt --port 8000
```