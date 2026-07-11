#!/usr/bin/env python3
"""
+æ MCP Server — Agentic Entrepreneurship tools for any MCP client.

Tools exposed:
  ae_activate      — load +æ context (prompt becomes >_æ|)
  ae_deactivate    — unload -æ context (prompt returns to >_)
  ae_status        — check if +æ is active
  ae_naics_search  — search NAICS business classification (live API + fallback)
  ae_blueprints    — list organizational blueprints
  ae_revenue       — show real revenue proof ($133.65 PAID)
  ae_mission       — show #opensourceware #250 mission
  ae_install       — skill install command + public artifacts

Usage with Hermes:
  hermes mcp add ae-tools --command python --args C:/æ/mcp/ae_server.py

Usage with any MCP client:
  Configure as stdio MCP server pointing to this file.

$OS = economic infrastructure for agentic entrepreneurship.
#startabusiness +æ
"""
import json
import os
import urllib.request
import urllib.parse

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ae-tools")

# ── State ───────────────────────────────────────────────────────

_AE_ACTIVE = False

AE_CONTEXT = {
    "language": {
        "+æ": "add agentic entrepreneurship context",
        "^æ": "compress to agentic notation",
        "$^æ": "execute agentic entrepreneurship",
        "#": "blueprint / ask / organizational intent",
        "$": "economic execution (requires confirmation)",
        ">_æ|": "live sovereign prompt",
    },
    "stack": {
        "Hermesᴴ": "conductor",
        "NVIDIAᴺ": "compute (121 models)",
        "Stripe$": "economics platform",
        "Doolaᴰ": "formation (50% commission)",
        "NAICS": "classification (live API)",
        "Reachyᴿ": "embodiment",
        "Exoᴱˣᵒ": "glocal compute mesh",
        "æ.store": "namespace IQ",
    },
    "blueprints": {
        "#startabusiness": "default blueprint — formation + Stripe + NAICS",
        "#daollc": "DAO LLC formation blueprint",
        "#reachy-clerk": "Reachy as Stripe clerk / DAOLLC operator",
        "#llmstore": "model combinator / intelligence storefront",
        "#clillc": "command line for company formation",
    },
    "naics_codes": {
        "541511": "Custom Computer Programming Services",
        "541512": "Computer Systems Design Services",
        "541519": "Other Computer Related Services",
        "513210": "Software Publishers",
        "518210": "Data Processing, Hosting, and Related Services",
        "541618": "Other Management Consulting Services",
        "611430": "Professional and Management Development Training",
        "541715": "R&D in Nanotech/Biotech/Physical/Engineering/Life Sciences",
    },
    "revenue_proof": {
        "customer": "Nicolas Enriquez",
        "purchase": "$267.30 (Doola LLC formation)",
        "commission": "$133.65 (50%)",
        "date": "Dec 11, 2025",
        "status": "PAID",
    },
    "mission": {
        "name": "#opensourceware #250",
        "goal": "Help start 250 American businesses",
        "challenge": "Challenge sponsors to help start 250,000",
        "philosophy": "OCW → OSW (democratize agency, not just knowledge)",
        "care": "We embody #opensourceware and equip new business owners with care",
    },
    "install": "hermes skills install https://myaelmendez.github.io/SKILL.md",
    "artifacts": [
        "https://myaelmendez.github.io/ae/",
        "https://myaelmendez.github.io/SKILL.md",
        "https://myaelmendez.github.io/PRIMITIVE.md",
        "https://myaelmendez.github.io/naics-blueprint.md",
        "https://myaelmendez.github.io/domain-stack.json",
    ],
}


# ── Tools ───────────────────────────────────────────────────────

@mcp.tool()
def ae_activate() -> str:
    """Load +æ agentic entrepreneurship context. Prompt becomes >_æ|."""
    global _AE_ACTIVE
    _AE_ACTIVE = True
    return json.dumps({
        "status": "active",
        "prompt": ">_æ|",
        "language": AE_CONTEXT["language"],
        "stack": list(AE_CONTEXT["stack"].keys()),
        "blueprints": list(AE_CONTEXT["blueprints"].keys()),
        "mission": AE_CONTEXT["mission"]["name"],
        "message": "+æ context loaded. # asks, $ executes, | is live. Hermes is the conductor.",
    }, indent=2)


@mcp.tool()
def ae_deactivate() -> str:
    """Unload -æ agentic entrepreneurship context. Prompt returns to >_."""
    global _AE_ACTIVE
    _AE_ACTIVE = False
    return json.dumps({
        "status": "inactive",
        "prompt": ">_",
        "message": "-æ context unloaded.",
    }, indent=2)


@mcp.tool()
def ae_status() -> str:
    """Check if +æ context is active."""
    return json.dumps({
        "active": _AE_ACTIVE,
        "prompt": ">_æ|" if _AE_ACTIVE else ">_",
    }, indent=2)


@mcp.tool()
def ae_naics_search(query: str = "custom computer programming") -> str:
    """Search NAICS business classification codes. Uses live API if NAICS_API_KEY is set, otherwise static fallback.

    Args:
        query: What the business does (e.g., "custom software", "consulting", "e-commerce")
    """
    naics_key = os.environ.get("NAICS_API_KEY", "")
    if naics_key:
        try:
            q = urllib.parse.quote(query)
            url = f"https://api.naics.com/api/search?q={q}&limit=5"
            req = urllib.request.Request(url, headers={
                "X-API-Key": naics_key,
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                api_data = json.loads(r.read())
            results = [
                {
                    "code": item.get("code"),
                    "title": item.get("title"),
                    "description": (item.get("description") or "")[:150],
                }
                for item in api_data.get("data", [])[:5]
            ]
            return json.dumps({
                "source": "live NAICS API",
                "query": query,
                "results": results,
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "source": "static (API error)",
                "error": str(e)[:100],
                "codes": AE_CONTEXT["naics_codes"],
            }, indent=2)
    return json.dumps({
        "source": "static (no NAICS_API_KEY)",
        "query": query,
        "codes": AE_CONTEXT["naics_codes"],
    }, indent=2)


@mcp.tool()
def ae_blueprints() -> str:
    """List available organizational blueprints. Blueprints are above skills — they define organizations, not just procedures."""
    return json.dumps({
        "blueprints": AE_CONTEXT["blueprints"],
        "note": "Blueprints (#) are organizational patterns. Skills do tasks. $ executes within economic boundary.",
    }, indent=2)


@mcp.tool()
def ae_revenue() -> str:
    """Show real revenue proof — $133.65 earned through Doola affiliate commission."""
    return json.dumps(AE_CONTEXT["revenue_proof"], indent=2)


@mcp.tool()
def ae_mission() -> str:
    """Show the #opensourceware #250 mission and challenge."""
    return json.dumps(AE_CONTEXT["mission"], indent=2)


@mcp.tool()
def ae_install() -> str:
    """Get the Hermes skill install command and public artifact URLs."""
    return json.dumps({
        "install": AE_CONTEXT["install"],
        "artifacts": AE_CONTEXT["artifacts"],
    }, indent=2)


# ── Run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
