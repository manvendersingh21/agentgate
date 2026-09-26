"""
AgentGate Dashboard Server
Live updates via Server-Sent Events (SSE)
"""
import asyncio
import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import threading
from queue import Queue
from typing import Any

app = FastAPI()

# Event queue for SSE
event_queue = Queue()

# Current run state
def _startup_mode() -> str:
    """Match create_adapters before the loop runs, so the badge is right at page load."""
    if os.getenv("GITHUB_TOKEN"):
        return "live"
    if os.getenv("JEV_API_KEY") or os.getenv("TYPESAFE_API_KEY"):
        return "hybrid"
    return "offline"


current_state = {
    "mode": _startup_mode(),
    "pr_number": 0,
    "status": "idle",
    "events": []
}


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve dashboard UI"""
    html_path = Path(__file__).parent / "index.html"
    with open(html_path, "r") as f:
        return f.read()


@app.get("/api/state")
async def get_state():
    """Get current state"""
    return current_state


@app.post("/api/start")
async def start_demo():
    """Start a demo run"""
    global current_state
    if current_state["status"] == "running":
        return {"success": False, "message": "Demo already running"}
    current_state = {
        "mode": current_state.get("mode", "offline"),
        "pr_number": 0,
        "status": "running",
        "events": []
    }
    while not event_queue.empty():
        try:
            event_queue.get_nowait()
        except Exception:
            break

    threading.Thread(target=run_demo_loop, daemon=True).start()
    return {"success": True, "message": "Demo started"}


@app.get("/api/events")
async def stream_events(request: Request):
    """SSE endpoint for live events"""
    
    async def event_generator():
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            # Get event from queue (non-blocking)
            try:
                event = event_queue.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
            except:
                await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


def emit_event(event: Any):
    """Emit event to SSE clients"""
    event_data = {
        "type": event.type,
        "pr_number": event.pr_number,
        "data": event.data,
        "timestamp": event.timestamp
    }
    
    # Add to queue
    event_queue.put(event_data)
    
    # Update state
    current_state["events"].append(event_data)
    current_state["pr_number"] = event.pr_number


def run_demo_loop():
    """Run the orchestrator loop"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.adapters import create_adapters
    from src.agents import BuilderAgent, FixerAgent
    from src.orchestrator import Orchestrator
    
    # Create adapters
    repo_path = os.getenv("REPO_PATH", str(Path(__file__).resolve().parents[2]))
    adapters = create_adapters(repo_path)
    
    current_state["mode"] = adapters["mode"]
    
    # Create agents
    builder = BuilderAgent(
        adapters["llm"],
        adapters["github"],
        repo_path
    )
    fixer = FixerAgent(adapters["llm"], repo_path)
    
    # Create orchestrator
    orchestrator = Orchestrator(
        builder=builder,
        fixer=fixer,
        github=adapters["github"],
        coderabbit=adapters["coderabbit"],
        jev=adapters["jev"],
        repo_path=repo_path,
        event_callback=emit_event
    )
    
    # Run loop
    issue = "Create a refund endpoint"
    branch = "agentgate/add-refund-endpoint"
    
    try:
        result = orchestrator.run_loop(issue, branch)
    except Exception as exc:
        current_state["status"] = "failed"
        current_state["result"] = {"success": False, "error": str(exc)}
        failed = {
            "type": "loop_failed",
            "pr_number": current_state.get("pr_number", 0),
            "data": {"error": str(exc)},
            "timestamp": "",
        }
        event_queue.put(failed)
        current_state["events"].append(failed)
        return

    current_state["status"] = "complete" if result["success"] else "failed"
    current_state["result"] = result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
