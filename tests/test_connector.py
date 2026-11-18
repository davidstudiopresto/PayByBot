"""PayByBot in Claude: the OAuth way in (client, « Autoriser », code with PKCE, tokens) and the MCP tools, which go
through the site's own routes. Nothing stored: each piece is sealed; « Déconnecter Claude » refuses the old ones."""
import asyncio
import base64
import hashlib
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import HTTPException
from starlette.requests import Request

from paybybot3 import connector, web

REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 50
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
STATE = {"u": "+33612345678", "d": False, "t": "Bearer h.e.s", "r": "refresh", "iat": 1}


def request(method="GET", path="/", query=None, body=b"", headers=None):
    scope = {"type": "http", "method": method, "path": path, "query_string": urlencode(query or {}).encode(),
             "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
             "scheme": "http", "server": ("localhost", 8765), "root_path": ""}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return Request(scope, receive)


def run(coro):
    return asyncio.run(coro)


def body(response):
    return json.loads(response.body)


class Flow(unittest.TestCase):
    def setUp(self):
        os.environ["PAYBYBOT_SECRET"] = "t"
        self.hosted = patch.object(web, "HOSTED", False)
        self.hosted.start()

    def tearDown(self):
        self.hosted.stop()

    def client_id(self):
        r = run(connector.register(request("POST", body=json.dumps({"client_name": "Claude", "redirect_uris": [REDIRECT]}).encode())))
        self.assertEqual(r.status_code, 201)
        return body(r)["client_id"]

    def code(self, cid):
        r = connector.authorize(request(query={"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
                                               "state": "xyz", "code_challenge": CHALLENGE, "code_challenge_method": "S256"}))
        self.assertEqual(r.status_code, 302)
        pending = r.headers["location"].split("r=", 1)[1]
        self.assertEqual(connector.describe(pending), {"client": "Claude"})
        s = web.UserSession.from_state(STATE)
        with patch.object(web, "current", return_value=s), patch.object(web, "save_account"), \
                patch.object(web, "record_activity"):
            back = connector.approve(connector.Approval(r=pending, allow=True), "cookie")["redirect"]
        q = parse_qs(urlsplit(back).query)
        self.assertTrue(back.startswith(REDIRECT))
        self.assertEqual(q["state"], ["xyz"])
        return q["code"][0]

    def exchange(self, form):
        return run(connector.token(request("POST", body=urlencode(form).encode())))

    def test_the_whole_way_in_then_a_tool(self):
        cid = self.client_id()
        code = self.code(cid)
        bad = self.exchange({"grant_type": "authorization_code", "code": code, "client_id": cid, "redirect_uri": REDIRECT,
                             "code_verifier": "wrong" * 10})
        self.assertEqual(body(bad)["error"], "invalid_grant")
        got = body(self.exchange({"grant_type": "authorization_code", "code": code, "client_id": cid,
                                  "redirect_uri": REDIRECT, "code_verifier": VERIFIER}))
        self.assertEqual(got["token_type"], "Bearer")

        def mcp(msg):
            return run(connector.mcp(request("POST", "/mcp", body=json.dumps(msg).encode(),
                                             headers={"authorization": "Bearer " + got["access_token"]})))
        init = body(mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}))
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code, 202)
        names = [t["name"] for t in body(mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))["result"]["tools"]]
        self.assertIn("get_account", names)
        overview = {"sessions": [{"plate": "AB123CD", "location": "75001", "start": "a", "expire": "b", "resident": True,
                                  "stopped": False}], "vehicles": [{"plate": "AB123CD", "type": "Car", "zone": "75001"}],
                    "autopilots": [{"id": "r1", "plate": "AB123CD", "enabled": True}], "payments": [{"id": "p"}]}
        seen = []
        with patch.object(web, "overview", side_effect=lambda token: seen.append(web.current(token)) or overview):
            call = body(mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_account", "arguments": {}}}))
        self.assertFalse(call["result"].get("isError"))
        self.assertEqual(call["result"]["structuredContent"]["tickets_en_cours"][0]["plate"], "AB123CD")
        self.assertEqual(seen[0].username, STATE["u"])  # the site's route got the user's own session

        again = body(self.exchange({"grant_type": "refresh_token", "refresh_token": got["refresh_token"], "client_id": cid}))
        self.assertIn("access_token", again)

    def test_no_token_asks_to_connect(self):
        r = run(connector.mcp(request("POST", "/mcp", body=b"{}")))
        self.assertEqual(r.status_code, 401)
        self.assertIn("resource_metadata=", r.headers["www-authenticate"])

    def test_unknown_redirect_or_plain_http_refused(self):
        r = run(connector.register(request("POST", body=json.dumps({"redirect_uris": ["http://evil.example/cb"]}).encode())))
        self.assertEqual(r.status_code, 400)
        cid = self.client_id()
        r = connector.authorize(request(query={"client_id": cid, "redirect_uri": "https://evil.example/cb",
                                               "response_type": "code", "code_challenge": CHALLENGE,
                                               "code_challenge_method": "S256"}))
        self.assertEqual(r.status_code, 400)

    def test_refused_goes_back_with_access_denied(self):
        cid = self.client_id()
        r = connector.authorize(request(query={"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
                                               "state": "s", "code_challenge": CHALLENGE, "code_challenge_method": "S256"}))
        back = connector.approve(connector.Approval(r=r.headers["location"].split("r=", 1)[1], allow=False), None)["redirect"]
        self.assertIn("error=access_denied", back)

    def test_a_tool_error_is_said_not_raised(self):
        with patch.object(web, "overview", side_effect=HTTPException(400, "PayByPhone ne répond pas.")):
            out = connector.call_tool(STATE, "get_account", {})
        self.assertTrue(out["isError"])
        self.assertIn("PayByPhone", out["content"][0]["text"])


class Hosted(unittest.TestCase):
    def setUp(self):
        os.environ["PAYBYBOT_SECRET"] = "t"
        connector._EPOCHS.clear()

    def test_a_code_opens_tokens_once(self):
        used = set()

        def store(fn, p_key=None, **kw):
            fresh = p_key not in used
            used.add(p_key)
            return fresh
        with patch.object(web, "HOSTED", True), patch.object(web, "store", side_effect=store):
            self.assertTrue(connector.once("c"))
            self.assertFalse(connector.once("c"))

    def test_disconnect_refuses_old_tokens(self):
        account = {"mcp_epoch": 0}
        data = connector.tokens(STATE, "cid", 0)
        with patch.object(web, "HOSTED", True), patch.object(web, "account_by_owner", side_effect=lambda o: account):
            ok = run(connector.mcp(request("POST", "/mcp", body=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(),
                                           headers={"authorization": "Bearer " + data["access_token"]})))
            self.assertEqual(ok.status_code, 200)
            account["mcp_epoch"] = 1  # « Déconnecter Claude »
            connector._EPOCHS.clear()
            refused = run(connector.mcp(request("POST", "/mcp", body=b"{}",
                                                headers={"authorization": "Bearer " + data["access_token"]})))
            self.assertEqual(refused.status_code, 401)
            again = run(connector.token(request("POST", body=urlencode(
                {"grant_type": "refresh_token", "refresh_token": data["refresh_token"], "client_id": "cid"}).encode())))
            self.assertEqual(body(again)["error"], "invalid_grant")


class Activate(unittest.TestCase):
    def test_the_resident_rate_found_on_paybyphone_is_used(self):
        os.environ["PAYBYBOT_SECRET"] = "t"
        s = MagicMock()
        s.call.return_value = {"paymentCards": [{"paymentAccountId": "card1", "cardType": "Visa", "maskedCardNumber": "4242"}]}
        added = []
        with patch.object(web, "current", return_value=s), \
                patch.object(web, "vehicle_zones", return_value=[({"licensePlate": "AB-123-CD"}, "75001", {"ratePolicyId": 9})]), \
                patch.object(web, "quote"), \
                patch.object(web, "add_autopilot", side_effect=lambda body, token: added.append(body) or {"id": "r1"}):
            out = connector.activate_renewal("tok", {"plate": "ab123cd"})
        self.assertTrue(out["ok"])
        self.assertEqual((added[0].location, added[0].rate, added[0].duration, added[0].paymentAccountId),
                         ("75001", "9", 7, "card1"))


if __name__ == "__main__":
    unittest.main()
