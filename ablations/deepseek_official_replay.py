"""Replay a published example against DeepSeek without executing model-generated code.

The two calls mirror main.py: the unchanged main prompt as a system message,
then the published detect_object printout as a user message. Responses are data.
"""

import argparse
import ast
import hashlib
import json
import re
import runpy
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = "place_apple_in_bowl"
COMMAND = "place the apple in the bowl"
MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/chat/completions"
KEY_FILE = Path("D:/Simpler/deepseek_api_key.txt")
OFFICIAL = ROOT / "outputs" / f"{CASE}.txt"
RESULTS = ROOT / "ablations" / "results"


def sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def prompt_and_detection():
    main_prompt = runpy.run_path(str(ROOT / "prompts" / "main_prompt.py"))["MAIN_PROMPT"]
    prompt = main_prompt.replace("[INSERT EE POSITION]", str([0.0, 0.6, 0.55]))
    prompt = prompt.replace("[INSERT TASK]", COMMAND)
    official = OFFICIAL.read_text(encoding="utf-8")
    match = re.search(
        r"/{10} PRINT OUTPUT /{10}\s+(Print statement output:\s+.*?)\s+/{10} GPT-4 /{10}",
        official,
        re.S,
    )
    if match is None:
        raise ValueError("Published detection printout was not found")
    detection = match.group(1).strip() + "\n"
    return prompt, detection, official


def inspect_code(content):
    blocks = re.findall(r"```python\s*\n(.*?)```", content, re.S | re.I)
    parsed = []
    for block in blocks:
        try:
            tree = ast.parse(block)
        except SyntaxError as exc:
            parsed.append({"syntax_ok": False, "error": str(exc)})
            continue
        calls = [node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        detected = [node.args[0].value for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "detect_object" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)]
        parsed.append({"syntax_ok": True, "calls": calls, "detected_objects": detected})
    return parsed


def call_api(messages, reasoning_effort):
    key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("API key file must contain one nonempty key")
    request_body = {
        "model": MODEL,
        "temperature": 0,
        "reasoning_effort": reasoning_effort,
        "max_tokens": 8000 if reasoning_effort != "none" else 5000,
        "stream": False,
        "messages": messages,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # HTTPError bodies can include account details; keep only status.
        raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from None
    content = payload["choices"][0]["message"]["content"]
    return {
        "requested_model": MODEL,
        "returned_model": payload.get("model"),
        "response_id": payload.get("id"),
        "finish_reason": payload["choices"][0].get("finish_reason"),
        "usage": payload.get("usage"),
        "content": content,
        "code_analysis": inspect_code(content),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["first", "continue"])
    parser.add_argument("--reasoning", choices=["none", "low", "high"], default="low")
    args = parser.parse_args()
    result_path = RESULTS / f"{CASE}_deepseek_flash_{args.reasoning}.json"
    prompt, detection, official = prompt_and_detection()
    metadata = {
        "case": CASE,
        "command": COMMAND,
        "source": str(OFFICIAL.relative_to(ROOT)).replace("\\", "/"),
        "official_sha256": sha256(official),
        "prompt_sha256": sha256(prompt),
        "detection_sha256": sha256(detection),
        "method": "Original main prompt, repository default EE pose, published detection printout; generated code never executed",
        "temperature": 0,
        "reasoning_effort": args.reasoning,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    if args.phase == "first":
        if result_path.exists():
            raise FileExistsError(f"Result already exists: {result_path}")
        result = {"metadata": metadata}
        messages = [{"role": "system", "content": prompt}]
        result["first"] = call_api(messages, args.reasoning)
    else:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("metadata", {}).get("prompt_sha256") != metadata["prompt_sha256"]:
            raise ValueError("Prompt changed since first call")
        if "second" in result:
            raise ValueError("Second call already recorded")
        first = result["first"]["content"]
        detected = {name for block in inspect_code(first) for name in block.get("detected_objects", [])}
        if not {"apple", "bowl"}.issubset(detected):
            raise ValueError("First response did not detect both apple and bowl; refusing oracle replay")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": first},
            {"role": "user", "content": detection},
        ]
        result["second"] = call_api(messages, args.reasoning)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    last = result["first"] if args.phase == "first" else result["second"]
    print(json.dumps({
        "phase": args.phase,
        "result": str(result_path),
        "requested_model": last["requested_model"],
        "returned_model": last["returned_model"],
        "finish_reason": last["finish_reason"],
        "usage": last["usage"],
        "code_analysis": last["code_analysis"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print urllib request headers or API response bodies.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
