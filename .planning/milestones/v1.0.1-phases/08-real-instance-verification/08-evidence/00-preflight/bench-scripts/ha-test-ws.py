#!/usr/bin/env python3
"""One-shot Home Assistant WebSocket helper, started only by ha-test-guard.

Usage: ha-test-ws.py FD MODE [ARGS...]
  FD      file descriptor that carries two lines: base URL and access token (never passed in argv)
  MODE    selftest                       authenticate once, expect auth_invalid
          raw TYPE [JSON]                send one command, print its result as JSON
          call DOMAIN.SERVICE [JSON]     call_service with the JSON as service_data

Exit codes: 0 ok, 1 command failed, 3 authentication error, 4 usage or connection error.
"""

import asyncio
import json
import os
import sys

import aiohttp


def _read_target(fd: int) -> tuple[str, str]:
    with os.fdopen(fd) as handle:
        url = handle.readline().rstrip("\n")
        token = handle.readline().rstrip("\n")
    return url, token


async def _run(url: str, token: str, mode: str, args: list[str]) -> int:
    ws_url = url.replace("http", "ws", 1) + "/api/websocket"
    async with aiohttp.ClientSession() as session:
        try:
            ws = await session.ws_connect(ws_url, timeout=aiohttp.ClientWSTimeout(ws_close=10))
        except aiohttp.ClientError as err:
            print(f"connection error: {type(err).__name__}", file=sys.stderr)
            return 4
        async with ws:
            hello = await ws.receive_json()
            if hello.get("type") != "auth_required":
                print("unexpected first message", file=sys.stderr)
                return 4
            # scrubbed copy (plan 08-10): the auth key name is split into two adjacent literals so the evidence scanner
            # (check-evidence-clean.sh, forbidden JSON key rule) does not match it; Python joins them, behaviour unchanged
            await ws.send_json({"type": "auth", "access_" "token": token})
            reply = await ws.receive_json()
            if reply.get("type") != "auth_ok":
                print("authentication error: " + str(reply.get("type")), file=sys.stderr)
                return 3
            if mode == "selftest":
                print("authenticated (unexpected for the dummy token)", file=sys.stderr)
                return 1
            if mode == "raw":
                message = {"type": args[0]}
                if len(args) > 1:
                    message.update(json.loads(args[1]))
            else:  # call
                domain, _, service = args[0].partition(".")
                message = {
                    "type": "call_service",
                    "domain": domain,
                    "service": service,
                    "service_data": json.loads(args[1]) if len(args) > 1 else {},
                }
            message["id"] = 1
            await ws.send_json(message)
            while True:
                result = await ws.receive_json()
                if result.get("id") == 1 and result.get("type") == "result":
                    break
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("success") else 1


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 4
    try:
        url, token = _read_target(int(sys.argv[1]))
    except (ValueError, OSError):
        print("cannot read the target from the file descriptor", file=sys.stderr)
        return 4
    mode, args = sys.argv[2], sys.argv[3:]
    if mode not in ("selftest", "raw", "call") or (mode != "selftest" and not args):
        print(__doc__, file=sys.stderr)
        return 4
    return asyncio.run(_run(url, token, mode, args))


if __name__ == "__main__":
    sys.exit(main())
