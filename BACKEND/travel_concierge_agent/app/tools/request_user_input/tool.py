# Control tool: the engine intercepts calls to request_user_input and pauses the
# pipeline — run() is never actually invoked. Present for registry uniformity.
def run(question: str, options: list | None = None) -> dict:
    return {"_pause": True, "question": question, "options": options or []}
