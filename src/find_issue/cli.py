import os
import re
import argparse
import time
from datetime import datetime
from typing import Any, List, Union, Tuple

from find_issue.config_manager import get_credentials
from find_issue.git_finder import fetch_issues

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

start_time = time.time()


class SecurityScanner:
    """Scans text for prompt injection patterns and malicious CLI commands using hardcoded rules."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"system\s*prompt\s*override",
        r"you\s+are\s+now\s+(an?|in)\s+unrestricted",
        r"jailbreak",
        r"developer\s+mode\s+enabled",
        r"do\s+anything\s+now",
        r"new\s+system\s+directive",
        r"forget\s+(all\s+)?previous\s+context",
    ]

   
    MALICIOUS_CMD_PATTERNS = [
        r"rm\s+-(rf|fr|r)\b",                   # Destructive file removal
        r">\s*/dev/sd[a-z]",                    # Direct drive writes
        r"mkfs(\.[a-z0-9]+)?\b",                # Filesystem wipe
        r":\(\)\{\s*:\|:&\s*\};:",              # Fork bomb
        r"(curl|wget)\s+.*\|\s*(bash|sh|zsh)",  # Unverified remote execution
        r"\b(nc|ncat|netcat)\b.*-e\s+(/bin/)?(ba)?sh", # Reverse shell
        r"/etc/shadow\b",                       # Sensitive credentials
        r"/etc/passwd\b",
        r"\b(chmod|chown)\s+(-R\s+)?777\b",    # Extreme permission modifications
        r"dd\s+if=/dev/(zero|urandom)",         # Drive overwrite
    ]

    @classmethod
    def scan(cls, context_text: str, output_text: str) -> Tuple[bool, List[str]]:
        flags = []

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, context_text, re.IGNORECASE):
                flags.append(f"Prompt injection pattern detected in issue context: `{pattern}`")

        
        for pattern in cls.MALICIOUS_CMD_PATTERNS:
            match = re.search(pattern, output_text, re.IGNORECASE)
            if match:
                flags.append(f"High-risk command detected in output: `{match.group(0)}`")

        is_flagged = len(flags) > 0
        return is_flagged, flags

    @classmethod
    def format_banner(cls, is_flagged: bool, flags: List[str]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_flagged:
            reasons = "\n".join([f"- {flag}" for flag in flags])
            return (
                "> [!CAUTION]\n"
                "> ### SECURITY ALERT: POTENTIAL MALICIOUS CONTENT DETECTED\n"
                f"> **Scan Timestamp:** {timestamp}\n"
                "> This roadmap generated warnings during automated static inspection. Issue data or model output matched known attack signatures.\n"
                "> **DO NOT execute the commands below without thorough manual verification.**\n"
                ">\n"
                "> **Detected Flags:**\n"
                f"{reasons}\n\n---\n\n"
            )
        else:
            return (
                "> [!NOTE]\n"
                "> ### Security Verification: PASSED\n"
                f"> **Scan Timestamp:** {timestamp}\n"
                "> No prompt injection signatures or destructive system commands detected by rule-based filters. "
                "Always review CLI commands before running them locally.\n\n---\n\n"
            )


class StepLogger:
    def __init__(self, filename: str = "steps.txt"):
        self.filename = filename
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"=== Agent Execution Trace: {datetime.now().isoformat()} ===\n\n")

    def log(self, text: str):
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(text.strip() + "\n\n")


def format_issues_compact(issues: list, repo_name: str, max_body_chars: int = 300) -> str:
    if not issues:
        return "No open issues found."

    compact = []
    for issue in issues:
        body = (issue.get("body") or "No description").strip()
        body = " ".join(body.split())
        if len(body) > max_body_chars:
            body = body[:max_body_chars] + "..."

        labels = ",".join(issue.get("labels", []))
        compact.append(
            f"#{issue['number']}: {issue['title']} | Labels: [{labels}] | URL: https://github.com/{repo_name}/issues/{issue['number']}\n"
            f"Context: {body}"
        )
    return "\n\n".join(compact)


class ContributorRoadmapPipeline:
    def __init__(self, model_name: str = "gemma-4-26b-a4b-it", log_file: str = "steps.txt"):
        self.logger = StepLogger(log_file)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=2048,
        )

    def run(self, repo_target: str, limit: int = 8) -> Tuple[str, str]:
        print(f"-> Fetching {limit} issues for {repo_target} via API...")
        issues = fetch_issues(repo_target, limit)
        issue_context = format_issues_compact(issues, repo_target, max_body_chars=350)

        self.logger.log(f"[PRE-PROCESSED CONTEXT]\n{issue_context}")

        system_prompt = (
            "You are an open-source mentor. Given raw issue summaries, select 3 genuinely beginner-to-intermediate. Less than 3 are also fine if the issues are not at all  beginner level. DO NOT TALK LIKE A PERSON "
            "issues and produce a concise onboarding roadmap in GitHub-flavored Markdown. "
            "Include prerequisites-highly technical, issue links, and clear local verification steps. "
            "Do NOT hallucinate CLI commands; if unverified, use generic instructions."
        )

        user_prompt = (
            f"Repository: {repo_target}\n\n"
            f"Open Issues Context:\n{issue_context}\n\n"
            f"Generate a contributor roadmap based solely on this data."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        print("-> Generating roadmap in a single pass...")
        ai_msg = self.llm.invoke(messages)

        content = ai_msg.content
        if isinstance(content, list):
            final_text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        else:
            final_text = str(content)

        self.logger.log(f"[FINAL RESPONSE]\n{final_text}")
        return final_text, issue_context


def main():
    github_token, gemini_key = get_credentials()
    parser = argparse.ArgumentParser(
        description="Token-efficient roadmap generator from GitHub open issues."
    )
    parser.add_argument("-r", "--repo", type=str, required=True, help="Target GitHub repo")
    parser.add_argument("-l", "--limit", type=int, default=8, help="Issues to retrieve (default: 8)")
    parser.add_argument("-o", "--output", type=str, default="OUTPUT.md", help="Output file")
    parser.add_argument("--log-file", type=str, default="steps.txt", help="Execution log path")
    parser.add_argument("--model", type=str, default="gemma-4-26b-a4b-it", help="Model name")

    args = parser.parse_args()

    pipeline = ContributorRoadmapPipeline(model_name=args.model, log_file=args.log_file)
    markdown_roadmap, issue_context = pipeline.run(repo_target=args.repo, limit=args.limit)

    # Perform hardcoded rule-based security scan
    is_flagged, flags = SecurityScanner.scan(issue_context, markdown_roadmap)
    security_banner = SecurityScanner.format_banner(is_flagged, flags)

    # Prepend banner to output markdown
    final_document = security_banner + markdown_roadmap

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(final_document)

    print("\nExecution complete:")
    print(f" - Log file: {args.log_file}")
    print(f" - Markdown roadmap: {args.output}")
    print(f" - Security scan status: {'[FLAGGED RISKS]' if is_flagged else '[PASSED]'}")
    print(f" - Total execution time: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()