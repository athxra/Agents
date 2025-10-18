#!/usr/bin/env python3
"""
Gemini SEO Agent using Apify SEO Audit Tool
-------------------------------------------
1. Calls Apify's 'misceres/seo-audit-tool' to get an SEO report.
2. Sends the audit report to Gemini for fix suggestions.
"""

import time
import json
import os
import glob
from pathlib import Path
from apify_client import ApifyClient
import google.generativeai as genai

# =========================================================
# 🔑 CONFIGURATION
# =========================================================
# Load env vars from .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

# Get Apify and Gemini tokens from environment (no hardcoded defaults)
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not APIFY_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("Missing APIFY_TOKEN or GEMINI_API_KEY. Set them in a .env file or environment.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
client = ApifyClient(APIFY_TOKEN)

SEO_AUDIT_ACTOR = "misceres/seo-audit-tool"

# =========================================================
# Helper Functions
# =========================================================
def run_apify_seo_audit_and_save(url_to_check):
    print(f"🚀 Starting SEO audit for: {url_to_check}")
    # Use the actor's documented input shape; keep it minimal/robust
    input_data = {
        "startUrl": url_to_check,
        "maxDepth": 1,
        "maxPagesPerDomain": 5,
        "useChrome": True,
        "proxy": {
            "useApifyProxy": True
        }
    }


    run = client.actor(SEO_AUDIT_ACTOR).call(run_input=input_data)
    run_id = run.get("id") or run.get("runId")
    dataset_id = run["defaultDatasetId"]

    while True:
        run_info = client.run(run_id).get()
        status = run_info.get("status")
        print("   🔄 Status:", status)
        if status in ("SUCCEEDED", "FAILED", "ABORTED"):
            break
        time.sleep(3)

    if status != "SUCCEEDED":
        raise RuntimeError(f"SEO audit failed or aborted ({status}).")

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"✅ SEO audit completed. Found {len(items)} items.")

    # Save each item to its own file
    for i, item in enumerate(items, 1):
        filename = f"seo_audit_page_{i}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(item, f, indent=2)
        print(f"Saved SEO audit for item {i} to {filename}")
        print(json.dumps(item, indent=2)) # Debug print each item
    
    return items


def load_local_audit_results(pattern: str = "seo_audit_page_*.json"):
    """Load existing local audit JSON files if they exist."""
    files = sorted(glob.glob(pattern))
    results = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"⚠️ Skipping unreadable file {path}: {e}")
    if results:
        print(f"📄 Loaded {len(results)} local audit file(s) matching {pattern}.")
    return results


def summarize_issues_from_audit(audit_results):
    """Map Apify audit fields into a structured list of human-readable issues."""
    summarized_issues = []
    for page in audit_results:
        url = page.get("url")
        title = page.get("title")
        issues = []

        # Headings
        is_h1 = page.get("isH1")
        is_h1_only_one = page.get("isH1OnlyOne")
        if is_h1 is False:
            issues.append("Missing H1 tag on page")
        elif is_h1_only_one is False:
            issues.append("Multiple H1 tags detected; ensure exactly one H1 per page")

        # Titles and meta
        if page.get("isTitle") is False:
            issues.append("Missing <title> tag")
        elif page.get("isTitleEnoughLong") is False:
            issues.append("Title length is suboptimal; adjust to ~50–60 characters")

        if page.get("isMetaDescription") is False:
            issues.append("Missing meta description")
        elif page.get("isMetaDescriptionEnoughLong") is False:
            issues.append("Meta description length is suboptimal; target ~150–160 characters")

        # Content length
        if page.get("isContentEnoughLong") is False:
            wc = page.get("wordsCount")
            issues.append(f"Low content depth; wordsCount={wc}")

        # Links
        links_count = page.get("linksCount")
        if page.get("isTooEnoughLinks"):
            issues.append(f"Too many links on page; linksCount={links_count}")

        internal_nofollow_count = page.get("internalNoFollowLinksCount", 0)
        if internal_nofollow_count:
            issues.append(f"Internal nofollow links present; count={internal_nofollow_count}")

        # Images
        not_opt_img_count = page.get("notOptimizedImagesCount", 0)
        if not_opt_img_count:
            sample = page.get("notOptimizedImages", [])[:5]
            issues.append(f"Unoptimized images detected; count={not_opt_img_count}; examples={sample}")

        # Broken links & images
        broken_links_count = page.get("brokenLinksCount", 0)
        if broken_links_count:
            issues.append(f"Broken internal links; count={broken_links_count}; examples={page.get('brokenLinks', [])[:5]}")

        ext_broken_links_count = page.get("externalBrokenLinksCount", 0)
        if ext_broken_links_count:
            issues.append(f"Broken external links; count={ext_broken_links_count}; examples={page.get('externalBrokenLinks', [])[:5]}")

        broken_images_count = page.get("brokenImagesCount", 0)
        if broken_images_count:
            issues.append(f"Broken images; count={broken_images_count}")

        # Technical signals
        if page.get("isViewport") is False:
            issues.append("Missing viewport meta tag for mobile responsiveness")
        if page.get("pageIsBlocked"):
            issues.append("Page is blocked for crawling; check robots/meta robots")
        if page.get("robotsFileExists") is False:
            issues.append("robots.txt missing")
        if page.get("faviconExists") is False:
            issues.append("Favicon missing")

        # Structured data
        json_ld = page.get("jsonLd", {})
        if not json_ld.get("isJsonLd", False):
            issues.append("Missing JSON-LD structured data")
        microdata = page.get("microdata", {})
        if not microdata.get("isMicrodata", False):
            issues.append("No Microdata present (optional if using JSON-LD)")

        # Only include pages that have at least one issue
        if issues:
            summarized_issues.append({
                "page": url,
                "title": title,
                "issues": issues,
            })
    return summarized_issues


def call_gemini_for_fixes(audit_summary):
    """Ask Gemini to propose fixes for the detected issues (summarized input)."""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            "You are an expert SEO consultant. Based on the following audit report, "
            "analyze each issue and generate:\n"
            "1. A short fix suggestion (HTML/text/config changes).\n"
            "2. A one-line explanation of why it helps.\n\n"
            f"Audit report:\n{json.dumps(audit_summary, indent=2)}\n\n"
            "Output your response as a clean, numbered list of actionable fixes."
        )
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        return f"Gemini call failed: {e}"


def _fallback_rule_based_fixes(full_items):
    """Produce deterministic fixes if Gemini is unavailable, using the full audit items."""
    lines = []
    idx = 1
    for item in full_items:
        url = item.get("url")
        title = item.get("title")
        lines.append(f"Page: {title or ''} ({url})")
        # Heuristics
        if item.get("isH1") is False:
            lines.append(f"{idx}. Fix: Add a single <h1> near the top with the page's primary topic.\n   Why: Clarifies hierarchy for crawlers and users.")
            idx += 1
        if item.get("isTitle") is False:
            lines.append(f"{idx}. Fix: Add a concise, keyword-focused <title> (~50–60 chars).\n   Why: Improves CTR and relevance.")
            idx += 1
        if item.get("isMetaDescription") is False or item.get("isMetaDescriptionEnoughLong") is False:
            lines.append(f"{idx}. Fix: Write a unique meta description (~150–160 chars) with a clear value prop and CTA.\n   Why: Boosts SERP CTR.")
            idx += 1
        if item.get("notOptimizedImagesCount", 0):
            lines.append(f"{idx}. Fix: Compress to WebP/AVIF, add width/height, lazy-load images; serve responsive sizes.\n   Why: Improves Core Web Vitals.")
            idx += 1
        if item.get("brokenLinksCount", 0):
            lines.append(f"{idx}. Fix: Fix or redirect broken internal links.\n   Why: Prevents crawl waste and improves UX.")
            idx += 1
        if item.get("externalBrokenLinksCount", 0):
            lines.append(f"{idx}. Fix: Update or remove dead outbound links.\n   Why: Maintains trust and avoids 404s.")
            idx += 1
        if item.get("isViewport") is False:
            lines.append(f"{idx}. Fix: Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.\n   Why: Enables mobile responsiveness.")
            idx += 1
        lines.append("")
    return "\n".join(lines).strip()


def call_gemini_on_full_audits(audit_results, preferred_chunk_size: int = 16):
    """Send the full JSON for all audits to Gemini in batches, with graceful degradation."""
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        print(f"⚠️ Failed to init Gemini model, using fallback: {e}")
        return _fallback_rule_based_fixes(audit_results)

    for chunk_size in [preferred_chunk_size, 8, 4, 2, 1]:
        try:
            all_parts = []
            batch_idx = 1
            for batch in chunks(audit_results, chunk_size):
                prompt = (
                    "You are an expert SEO consultant. Analyze the following SEO audit JSON objects as-is.\n"
                    "For EACH page, produce 3-8 specific, actionable fixes with short 'why' lines.\n"
                    "Be concrete (HTML/meta examples, redirect rules, JSON-LD snippets).\n"
                    "Present your output in raw markdown format with:\n"
                    "- Headings for each page, e.g. using `## Page: <title> (<url>)`\n"
                    "- Numbered lists for fixes, e.g. `1. Fix: ...`\n"
                    "- Each fix followed by an indented `Why:` explanation.\n"
                    "- Use fenced code blocks for any HTML/meta tags or JSON-LD snippets (triple backticks ```).\n\n"
                    f"This is batch {batch_idx} of multiple.\n"
                    f"Audit JSON batch ({len(batch)} items):\n{json.dumps(batch, indent=2)}\n"
                )
                resp = model.generate_content(prompt)
                all_parts.append((resp.text or "").strip())
                batch_idx += 1
            return "\n\n".join(all_parts).strip()
        except Exception as e:
            print(f"⚠️ Gemini call failed for chunk_size={chunk_size}, retrying smaller. Error: {e}")
            continue

    print("⚠️ Gemini calls failed for all chunk sizes, using rule-based fallback.")
    return _fallback_rule_based_fixes(audit_results)


# =========================================================
# Main Function
# =========================================================
def main():
    # "https://www.myfirstpcb.com/"
    url = input("Enter the link: ").strip()

    # Prefer using already-downloaded audit files to save time/credits
    audit_results = load_local_audit_results()
    if not audit_results:
        audit_results = run_apify_seo_audit_and_save(url)

    print("\n🤖 Sending full JSON of all audit pages to Gemini...")
    fixes = call_gemini_on_full_audits(audit_results, preferred_chunk_size=16)

    print("\n==============================")
    print(f"🔍 SEO Fix Suggestions for {url}")
    print("==============================")
    print(fixes)

    with open("seo_fixes_report.txt", "w", encoding="utf-8") as f:
        f.write(f"SEO Fix Suggestions for {url}\n\n{fixes}")
    print("\n💾 Saved to seo_fixes_report.txt")
    print("\n✅ Completed")


# =========================================================
if __name__ == "__main__":
    main()

# paste the raw md from this "agen s_report.txt" in this website "https://apitemplate.io/pdf-tools/convert-markdown-to-pdf/"