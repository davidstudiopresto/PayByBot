"""PayByBot as a connector in Claude (MCP over HTTP, OAuth 2.1).

Claude adds https://paybybot.fr/mcp; the user signs in on paybybot.fr as on the site (PayByPhone number and password,
never seen by Claude) and clicks « Autoriser Claude ». Nothing new is stored: the client, the code and the tokens are
sealed like the session cookie (one key per use). « Déconnecter Claude » in Mon compte raises the account's
`mcp_epoch`: every token made before is refused from then on.

The tools call the site's own routes with a session made for the call, so Claude goes through exactly the checks of
the dashboard (own vehicles, subscription, no ticket paid twice).
"""
import base64
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import Cookie, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

ACCESS_TTL = 3600  # an hour; Claude asks a new one with its refresh token
REFRESH_TTL = 60 * 86400  # two months without using Claude: sign in again
CODE_TTL = 300
REQUEST_TTL = 900  # the « Autoriser » page, opened from Claude
SCOPE = "paybybot"
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")


def base(request):
    """https://paybybot.fr online; the local address otherwise."""
    if web.HOSTED:
        return "https://" + (request.headers.get("x-forwarded-host") or request.headers.get("host") or "paybybot.fr")
    return str(request.base_url).rstrip("/")


def sealed(purpose, data):
    return web._fernet(purpose).encrypt(json.dumps(data).encode()).decode()


def opened(purpose, value, ttl):
    try:
        return json.loads(web._fernet(purpose).decrypt((value or "").encode(), ttl=ttl))
    except Exception:
        return None


# --- Discovery (RFC 9728, RFC 8414) ---------------------------------------------------------------------------------

def resource_metadata(request: Request):
    root = base(request)
    return {"resource": root + "/mcp", "authorization_servers": [root], "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"], "resource_name": "PayByBot"}


def server_metadata(request: Request):
    root = base(request)
    return {"issuer": root, "authorization_endpoint": root + "/oauth/authorize", "token_endpoint": root + "/oauth/token",
            "registration_endpoint": root + "/oauth/register", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [SCOPE]}


# --- Client registration (RFC 7591): the client is its own sealed id -------------------------------------------------

def good_redirect(uri):
    """https anywhere (claude.ai), or a program on this computer (http://localhost)."""
    if not isinstance(uri, str) or len(uri) > 500:
        return False
    parts = urlsplit(uri)
    if parts.fragment or not parts.netloc:
        return False
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1"))


async def register(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = None
    uris = (body or {}).get("redirect_uris") if isinstance(body, dict) else None
    if not isinstance(uris, list) or not 1 <= len(uris) <= 5 or not all(good_redirect(u) for u in uris):
        return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
    name = str(body.get("client_name") or "Claude")[:60]
    client_id = sealed("mcp-client", {"n": name, "r": uris})
    return JSONResponse({"client_id": client_id, "client_id_issued_at": int(time.time()), "client_name": name,
                         "redirect_uris": uris, "token_endpoint_auth_method": "none",
                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]},
                        status_code=201)


def client(client_id):
    found = opened("mcp-client", client_id, None)
    return found if isinstance(found, dict) and found.get("r") else None


# --- Authorization: the « Autoriser Claude » page, then a one-time code ----------------------------------------------

def authorize(request: Request):
    q = request.query_params
    app = client(q.get("client_id"))
    uri = q.get("redirect_uri") or (app["r"][0] if app and len(app["r"]) == 1 else None)
    if not app or uri not in app["r"]:
        return JSONResponse({"error": "invalid_client", "error_description": "Adresse de retour inconnue."}, status_code=400)

    def back(**params):
        return RedirectResponse(uri + ("&" if "?" in uri else "?") + urlencode({**params, "state": q.get("state") or ""}),
                                status_code=302)

    if q.get("response_type") != "code":
        return back(error="unsupported_response_type")
    if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
        return back(error="invalid_request", error_description="PKCE S256 requis.")
    pending = sealed("mcp-request", {"c": q.get("client_id"), "n": app["n"], "u": uri, "s": q.get("state") or "",
                                     "cc": q["code_challenge"]})
    return RedirectResponse("/#/autoriser?r=" + pending, status_code=302)


class Approval(BaseModel):
    r: str = Field(max_length=4000)
    allow: bool


def approval_request(r):
    req = opened("mcp-request", r, REQUEST_TTL)
    if not req:
        raise HTTPException(410, "Cette demande a expiré. Reconnectez PayByBot depuis Claude.")
    return req


def describe(r: str):
    """What the « Autoriser » page shows: who asks."""
    return {"client": approval_request(r)["n"]}


def approve(body: Approval, pbb_session: str = Cookie(None)):
    req = approval_request(body.r)
    target = req["u"] + ("&" if "?" in req["u"] else "?")
    if not body.allow:
        return {"redirect": target + urlencode({"error": "access_denied", "state": req["s"]})}
    s = web.current(pbb_session)
    if s.demo and web.HOSTED:  # on this computer the demo can, to try the connector end to end
        raise HTTPException(400, "Le compte de démonstration ne se connecte pas à Claude.")
    if web.HOSTED and not web.guarded(lambda: web.has_account(s)):
        raise HTTPException(404, "Aucun compte PayByBot pour ce compte PayByPhone.")
    epoch = int(web.load_account(s).get("mcp_epoch") or 0)
    try:  # shown in Mon compte, with « Déconnecter Claude »
        web.save_account(s, {"mcp_since": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        web.log.warning("connector date not kept: %s", type(e).__name__)
    code = sealed("mcp-code", {"st": s.to_state(), "c": req["c"], "u": req["u"], "cc": req["cc"], "ep": epoch,
                               "j": secrets.token_urlsafe(8)})
    web.log.info("connector authorized (%s)", req["n"])
    web.record_activity("Connexion à Claude", s)
    return {"redirect": target + urlencode({"code": code, "state": req["s"]})}


# --- Tokens ----------------------------------------------------------------------------------------------------------

def token_error(error, description=None, status=400):
    return JSONResponse({"error": error, **({"error_description": description} if description else {})},
                        status_code=status, headers={"Cache-Control": "no-store"})


def once(code):
    """A code opens one pair of tokens only (online: the shared store remembers it was used)."""
    if not web.HOSTED:
        return True
    key = "mcpcode:" + hashlib.sha256(code.encode()).hexdigest()
    try:
        return bool(web.store("rate_hit", p_key=key, p_window_seconds=CODE_TTL + 60, p_max=1))
    except Exception:
        return False


def tokens(state, client_id, epoch):
    owner_state = {**state, "rm": True}
    data = {"st": owner_state, "c": client_id, "ep": epoch}
    return {"access_token": sealed("mcp-access", data), "token_type": "Bearer", "expires_in": ACCESS_TTL,
            "refresh_token": sealed("mcp-refresh", data), "scope": SCOPE}


def owner_of(state):
    return web.owner_id(state["u"])


def epoch_now(owner):
    """The account's current epoch (« Déconnecter Claude » raises it)."""
    if not web.HOSTED:
        return 0
    return int((web.account_by_owner(owner) or {}).get("mcp_epoch") or 0)


async def token(request: Request):
    form = {k: v[0] for k, v in parse_qs((await request.body()).decode(errors="replace")).items()}
    grant = form.get("grant_type")
    if grant == "authorization_code":
        got = opened("mcp-code", form.get("code"), CODE_TTL)
        if not got or got["c"] != form.get("client_id") or got["u"] != form.get("redirect_uri"):
            return token_error("invalid_grant")
        verifier = form.get("code_verifier") or ""
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        if not secrets.compare_digest(challenge, got["cc"]):
            return token_error("invalid_grant", "PKCE incorrect.")
        if not once(form["code"]):
            return token_error("invalid_grant", "Code déjà utilisé.")
        return JSONResponse(tokens(got["st"], got["c"], got["ep"]), headers={"Cache-Control": "no-store"})
    if grant == "refresh_token":
        got = opened("mcp-refresh", form.get("refresh_token"), REFRESH_TTL)
        if not got or got["c"] != form.get("client_id"):
            return token_error("invalid_grant")
        try:
            if got["ep"] != epoch_now(owner_of(got["st"])):
                return token_error("invalid_grant", "Connexion à Claude coupée depuis PayByBot.")
        except Exception:
            return token_error("temporarily_unavailable", status=503)
        state = dict(got["st"])
        try:  # the newest PayByPhone login kept for the account (each use may replace it)
            login = web.stored_login(owner_of(state)) if web.HOSTED else None
            if login and login.get("a"):
                state.update(t=login["a"], r=login.get("r") or state.get("r"))
        except Exception:
            pass
        return JSONResponse(tokens(state, got["c"], got["ep"]), headers={"Cache-Control": "no-store"})
    return token_error("unsupported_grant_type")


# --- MCP: JSON-RPC over HTTP, one answer per request (no stream needed) ---------------------------------------------

def unauthorized(request, description="Connectez PayByBot."):
    meta = base(request) + "/.well-known/oauth-protected-resource"
    return JSONResponse({"error": "invalid_token", "error_description": description}, status_code=401,
                        headers={"WWW-Authenticate": 'Bearer resource_metadata="%s"' % meta})


_EPOCHS = {}


def current_epoch(owner):
    """Read again at most once a minute per server, like the logged-out sessions."""
    hit = _EPOCHS.get(owner)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    value = epoch_now(owner)
    _EPOCHS[owner] = (time.time(), value)
    return value


def session_token(state):
    """A session cookie made for this call: the site's routes check it as any other."""
    s = web.UserSession.from_state({**state, "iat": int(time.time()), "rm": True})
    s.remember = True
    s.issued_at = int(time.time())
    return web.seal(s)


def obj(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


RENEWAL_ID = {"type": "string", "description": "L'identifiant du renouvellement ou du ticket programmé (champ id de get_account)."}
DAY = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "description": "Jour au format AAAA-MM-JJ (heure de Paris)."}

TOOLS = [
    {"name": "get_account", "title": "Voir mon compte PayByBot",
     "description": "Tickets PayByPhone en cours, véhicules du compte, renouvellements automatiques et tickets "
                    "programmés (avec leur prochain ticket, leur pause et leur dernière erreur).",
     "inputSchema": obj(), "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "get_history", "title": "Historique des tickets",
     "description": "Les tickets payés par PayByBot, du plus récent au plus ancien (60 au plus).",
     "inputSchema": obj(), "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "activate_renewal", "title": "Activer le renouvellement résident",
     "description": "Active le renouvellement automatique du ticket résident d'un véhicule du compte : PayByBot "
                    "reprend un ticket résident d'une semaine sur PayByPhone dès que le précédent se termine, payé "
                    "par PayByPhone avec la carte enregistrée. Demander confirmation à l'utilisateur avant.",
     "inputSchema": obj({"plate": {"type": "string", "description": "La plaque du véhicule, telle que dans get_account."}},
                        ["plate"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "schedule_handi_ticket", "title": "Programmer le ticket handicapé (CMI-S)",
     "description": "Programme le ticket gratuit carte mobilité inclusion stationnement (CMI-S, « Handi ») à Paris "
                    "pour un véhicule du compte : PayByBot prend un ticket d'une journée dans chaque arrondissement "
                    "choisi, les jours choisis. À utiliser seulement si l'utilisateur a dit être titulaire de la "
                    "carte CMI-S ; demander confirmation avant.",
     "inputSchema": obj({
         "plate": {"type": "string", "description": "La plaque du véhicule, telle que dans get_account."},
         "zones": {"type": "array", "minItems": 1, "maxItems": 21, "uniqueItems": True,
                   "items": {"type": "string", "pattern": r"^75(0(0[1-9]|1\d|20)|116)$"},
                   "description": "Les arrondissements de Paris couverts en même temps (75001 à 75020, 75116)."},
         "days": {"type": "array", "minItems": 1, "maxItems": 7, "uniqueItems": True,
                  "items": {"type": "integer", "minimum": 0, "maximum": 6},
                  "description": "Les jours (0 = lundi … 6 = dimanche). Par défaut lundi à samedi : le dimanche est "
                                 "gratuit à Paris."},
         "now": {"type": "boolean", "description": "Prendre le premier ticket tout de suite (si c'est un des jours)."},
         "cmis_card": {"type": "boolean", "description": "true : l'utilisateur a confirmé être titulaire de la "
                                                         "carte CMI-S."}},
         ["plate", "zones", "cmis_card"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "pause_renewal", "title": "Mettre en pause",
     "description": "Met en pause un renouvellement ou un ticket programmé : aucun ticket n'est pris du premier au "
                    "dernier jour inclus (sans dernier jour : jusqu'à la reprise).",
     "inputSchema": obj({"renewal_id": RENEWAL_ID, "start": DAY, "end": DAY}, ["renewal_id", "start"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}},
    {"name": "resume_renewal", "title": "Reprendre",
     "description": "Termine la pause d'un renouvellement ou d'un ticket programmé (ou relance un renouvellement "
                    "suspendu). Un ticket peut être pris tout de suite s'il en faut un.",
     "inputSchema": obj({"renewal_id": RENEWAL_ID}, ["renewal_id"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "stop_renewal", "title": "Arrêter un renouvellement",
     "description": "Arrête définitivement un renouvellement ou un ticket programmé. Le ticket déjà en cours va "
                    "jusqu'à sa fin. Demander confirmation à l'utilisateur avant.",
     "inputSchema": obj({"renewal_id": RENEWAL_ID}, ["renewal_id"]),
     "annotations": {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False}},
]


def renewal_view(ap):
    return {k: ap.get(k) for k in ("id", "label", "plate", "location", "locations", "enabled", "days", "start",
                                   "dateFrom", "dateTo", "pausedFrom", "pausedUntil", "lastPayment", "lastError",
                                   "nextTicket", "cmis")}


def get_account(token, args):
    data = web.overview(token)
    return {
        "tickets_en_cours": [{k: x.get(k) for k in ("plate", "location", "start", "expire", "resident")}
                             for x in data["sessions"] if not x.get("stopped")],
        "vehicules": [{"plate": v["plate"], "type": v.get("type"), "zone_residente": v.get("zone")} for v in data["vehicles"]],
        "renouvellements_et_tickets_programmes": [renewal_view(ap) for ap in data["autopilots"]],
        "carte_de_paiement": bool(data.get("payments")),
    }


def get_history(token, args):
    return {"tickets": [{k: x.get(k) for k in ("plate", "location", "start", "expire", "cost", "kind")}
                        for x in web.history(token)]}


WEEKLY_LABEL = "Riverain hebdo"  # as the dashboard names it (Riverain.tsx)


def activate_renewal(token, args):
    s = web.current(token)
    plate = web.plate_key(args.get("plate") or "")
    found = [(v, z, r) for v, z, r in web.guarded(lambda: web.vehicle_zones(s)) if web.plate_key(v["licensePlate"]) == plate]
    if not found:
        raise HTTPException(400, "Pas de tarif résident trouvé pour ce véhicule sur PayByPhone (véhicule du compte, "
                                 "carte résident active ?).")
    vehicle, zone, rate = found[0]
    payments = web.normalize_accounts(web.guarded(lambda: s.call("get_payment_accounts")) or {})
    usable = [p for p in payments if not p.get("expired")]
    if not usable:
        raise HTTPException(400, "Aucune carte bancaire valide dans PayByPhone : ajoutez-en une dans l'application.")
    parking = dict(location=zone, rate=str(rate["ratePolicyId"]), duration=7,
                   unit="Days", plate=vehicle["licensePlate"], paymentAccountId=usable[0]["id"])
    web.quote(web.QuoteRequest(**parking, renewal=True), token)
    result = web.add_autopilot(web.Autopilot(**parking, label=WEEKLY_LABEL), token)
    return {"ok": True, "vehicule": vehicle["licensePlate"], "zone": zone,
            "activation": (result or {}).get("activation") if isinstance(result, dict) else None}


DAILY_LABEL = "Jours précis"  # as the dashboard names a programmed ticket (DailyTickets.tsx)


def schedule_handi_ticket(token, args):
    """As « Programmer un ticket » → Carte mobilité CMI-S on the dashboard: a day ticket, each zone its own Handi rate."""
    if args.get("cmis_card") is not True:
        raise HTTPException(400, "Le ticket CMI-S est réservé aux titulaires de la carte mobilité inclusion "
                                 "stationnement : confirmez-le d'abord.")
    s = web.current(token)
    zones = sorted(set(args.get("zones") or []))
    if not zones or not all(web.PARIS_ZONE.match(z) for z in zones):
        raise HTTPException(400, "Le ticket CMI-S est proposé à Paris seulement (75001 à 75020).")
    plate = web.plate_key(args.get("plate") or "")
    vehicle = next((v for v in web.guarded(lambda: s.call("get_vehicles")) or []
                    if web.plate_key(v.get("licensePlate") or "") == plate and not v.get("archived")), None)
    if not vehicle:
        raise HTTPException(400, "Ce véhicule n'est pas sur votre compte PayByPhone.")
    plate = vehicle["licensePlate"]
    payments = web.normalize_accounts(web.guarded(lambda: s.call("get_payment_accounts")) or {})
    cards = [p for p in payments if p.get("kind") == "card" and not p.get("expired")]
    if not cards:
        raise HTTPException(400, "Aucune carte bancaire valide dans PayByPhone : ajoutez-en une dans l'application.")
    rate = web.guarded(lambda: web.handi_rate(s, zones[0], plate))
    paris = datetime.now(web.PARIS)
    now = bool(args.get("now"))
    body = web.Autopilot(location=zones[0], rate=str(rate), duration=1, unit="Days", plate=plate,
                         paymentAccountId=cards[0]["id"], label=DAILY_LABEL, days=args.get("days") or [0, 1, 2, 3, 4, 5],
                         tz="Europe/Paris", start="%02d:00" % ((paris.hour + 1) % 24), cmis=True, now=now,
                         locations=zones if len(zones) > 1 else None)
    ap = web.add_autopilot(body, token)
    out = {"ok": True, "programme": renewal_view(ap)}
    if now:  # the dashboard then takes it at once (one wave of zones; the scheduler takes the rest)
        got = web.take_now(ap["id"], token)
        out["pris_maintenant"] = {"couverts": got.get("covered"), "sur": got.get("total"),
                                  "suite_par_le_planificateur": bool(got.get("more")), "erreur": got.get("error")}
    return out


def pause_renewal(token, args):
    return renewal_view(web.pause_autopilot(args["renewal_id"], web.Pause(start=args["start"], end=args.get("end")), token))


def resume_renewal(token, args):
    result = web.resume_autopilot(args["renewal_id"], token)
    return renewal_view(result) if isinstance(result, dict) and "id" in result else {"ok": True}


def stop_renewal(token, args):
    web.delete_autopilot(args["renewal_id"], token)
    return {"ok": True, "arrete": args["renewal_id"]}


HANDLERS = {"get_account": get_account, "get_history": get_history, "activate_renewal": activate_renewal,
            "schedule_handi_ticket": schedule_handi_ticket, "pause_renewal": pause_renewal, "resume_renewal": resume_renewal, "stop_renewal": stop_renewal}

INSTRUCTIONS = ("PayByBot renouvelle automatiquement les tickets de stationnement PayByPhone (ticket résident chaque "
                "semaine, tickets programmés certains jours). Commencez par get_account. Les tickets sont payés par "
                "PayByPhone avec la carte de l'utilisateur : confirmez avec lui avant activate_renewal ou stop_renewal.")


def call_tool(state, name, args):
    handler = HANDLERS.get(name)
    if not handler:
        return {"content": [{"type": "text", "text": "Outil inconnu : %s" % name}], "isError": True}
    try:
        result = handler(session_token(state), args or {})
    except HTTPException as e:
        return {"content": [{"type": "text", "text": str(e.detail)}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": web.friendly_error(e)}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "structuredContent": result}


def answer(state, msg):
    """One JSON-RPC message; None for a notification."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return {"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None,
                "error": {"code": -32600, "message": "Invalid Request"}}
    if "id" not in msg:
        return None
    method, params = msg["method"], msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        result = {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "PayByBot", "title": "PayByBot", "version": "1.0.0"},
                  "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(state, params.get("name"), params.get("arguments"))
    else:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": msg["id"], "result": result}


async def mcp(request: Request):
    auth = request.headers.get("authorization") or ""
    got = opened("mcp-access", auth[7:].strip(), ACCESS_TTL) if auth.lower().startswith("bearer ") else None
    if not got:
        return unauthorized(request)
    try:
        if got["ep"] != current_epoch(owner_of(got["st"])):
            return unauthorized(request, "Connexion à Claude coupée depuis PayByBot.")
    except Exception:
        return JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
                            status_code=400)
    from starlette.concurrency import run_in_threadpool

    holder = web._loaded.get()
    try:
        if isinstance(body, list):
            replies = [r for r in [await run_in_threadpool(answer, got["st"], m) for m in body] if r is not None]
        else:
            replies = await run_in_threadpool(answer, got["st"], body)
    finally:
        if holder is not None:
            holder.clear()  # the session made for the call never goes back as a cookie
    if replies is None or replies == []:
        return Response(status_code=202)
    return JSONResponse(replies)


def mcp_get(request: Request):
    return Response(status_code=405, headers={"Allow": "POST"})


def disconnect(pbb_session: str = Cookie(None)):
    """« Déconnecter Claude » in Mon compte: every token given before is refused from now on."""
    s = web.current(pbb_session)
    account = web.load_account(s)
    web.save_account(s, {"mcp_epoch": int(account.get("mcp_epoch") or 0) + 1, "mcp_since": None})
    _EPOCHS.pop(web.owner_id(s.username), None)
    web.record_activity("Déconnexion de Claude", s)
    return {"ok": True}


def register_routes(app):
    """Before the site's catch-all route (which serves the page for every other GET)."""
    app.add_api_route("/.well-known/oauth-protected-resource", resource_metadata, methods=["GET"], include_in_schema=False)
    app.add_api_route("/.well-known/oauth-protected-resource/mcp", resource_metadata, methods=["GET"], include_in_schema=False)
    app.add_api_route("/.well-known/oauth-authorization-server", server_metadata, methods=["GET"], include_in_schema=False)
    app.add_api_route("/oauth/register", register, methods=["POST"], include_in_schema=False)
    app.add_api_route("/oauth/authorize", authorize, methods=["GET"], include_in_schema=False)
    app.add_api_route("/oauth/token", token, methods=["POST"], include_in_schema=False)
    app.add_api_route("/api/oauth/request", describe, methods=["GET"], include_in_schema=False)
    app.add_api_route("/api/oauth/approve", approve, methods=["POST"], include_in_schema=False)
    app.add_api_route("/api/oauth/disconnect", disconnect, methods=["POST"], include_in_schema=False)
    app.add_api_route("/mcp", mcp, methods=["POST"], include_in_schema=False)
    app.add_api_route("/mcp", mcp_get, methods=["GET", "DELETE"], include_in_schema=False)


# Last: web.py imports this module to register its routes, and this one uses web's functions at call time.
from paybybot3 import web  # noqa: E402
