"""A room: several agents talk about one topic, in turns, as ordinary A2A conversations. Every turn is a SendMessage to that agent in one shared contextId, so the whole
discussion is stored as that agent's tasks and shows up in ListTasks(contextId).

Bounded on purpose, because every turn costs a model call: at most `rounds` rounds (default 3), at most `max_calls` turns in all, and the room ends early when every member
opens a round with AGREE after at least `min_rounds` rounds (two voices agreeing at once in round one is flattery, not a decision). An agent that cannot take part ends the room
and the reason is returned, never papered over. Nothing in a room can post, spend beyond the model calls counted here, or change a setting: members only talk."""
import uuid

from . import a2a


def _reply_text(task: dict) -> str:
    msg = (task.get("status") or {}).get("message") or {}
    return " ".join(p.get("text", "") for p in msg.get("parts", []))


def run_room(agents: dict, account_id: str, topic: str, members: list[str], rounds: int = 3, min_rounds: int = 2, max_calls: int = 12, llm=None) -> dict:
    members = [m for m in dict.fromkeys(members) if m in agents]
    if len(members) < 2:
        return {"ok": False, "error": "a room needs at least two known agents"}
    context_id, transcript, calls, stopped = uuid.uuid4().hex, [], 0, "round_limit"
    topic = str(topic or "")[:1000]
    for r in range(1, max(1, min(rounds, 6)) + 1):
        agreed = 0
        for m in members:
            if calls >= max_calls:
                stopped = "call_limit"
                break
            so_far = "\n".join(f"{who}: {text}" for who, text in transcript[-8:])
            prompt = (f"Room topic: {topic}\n\nSo far:\n{so_far or '(nothing yet)'}\n\nYou are {m}, round {r}. Add your view in a few sentences. "
                      "If you agree with the current plan, begin your reply with the single word AGREE.")
            task = a2a.send(agents, account_id, m, {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER", "contextId": context_id,
                                                                "parts": [{"text": prompt}], "metadata": {"room": True, "round": r}}}, llm)
            calls += 1
            state = task["status"]["state"]
            if state != a2a.WIRE["completed"]:
                return {"ok": True, "contextId": context_id, "transcript": transcript, "stopped": f"{m} could not take part ({state[11:].lower()}): {_reply_text(task)}", "calls": calls, "decision": ""}
            text = _reply_text(task)
            transcript.append((m, text))
            agreed += text.lstrip().upper().startswith("AGREE")
        if stopped == "call_limit":
            break
        if agreed == len(members) and r >= min_rounds:
            stopped = "agreed"
            break
    return {"ok": True, "contextId": context_id, "transcript": transcript, "stopped": stopped, "calls": calls, "decision": transcript[-len(members)][1] if transcript else ""}
