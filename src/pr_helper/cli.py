import os
import argparse
import time
from datetime import datetime
from typing import Any, List, Union
from pr_helper.config_manager import get_credentials

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pr_helper.git_finder import fetch_issues

start_time = time.time()


class StepLogger:
    """Manages file-based step logging."""
    def __init__(self, filename: str = "steps.txt"):
        self.filename = filename
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"=== Agent Execution Trace: {datetime.now().isoformat()} ===\n\n")

    def log(self, text: str):
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(text.strip() + "\n\n")


def format_issues_compact(issues: list, repo_name: str, max_body_chars: int = 300) -> str:
    """
    Compresses issue data to bare essentials to minimize prompt tokens.
    Excludes boilerplate and truncates aggressive body text.
    """
    if not issues:
        return "No open issues found."

    compact = []
    for issue in issues:
        # Strip noisy multi-newlines and markdown comments
        body = (issue.get("body") or "No description").strip()
        body = " ".join(body.split())  # Collapse whitespace
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
        # Deterministic generation, minimal token waste on retries
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=2048,  # Caps output generation costs
        )

    def run(self, repo_target: str, limit: int = 8) -> str:
        # Step 1: Deterministic retrieval outside LLM context (Zero Token Cost)
        print(f"-> Fetching {limit} issues for {repo_target} via API...")
        issues = fetch_issues(repo_target, limit)
        issue_context = format_issues_compact(issues, repo_target, max_body_chars=350)
        
        self.logger.log(f"[PRE-PROCESSED CONTEXT]\n{issue_context}")

        # Step 2: Single-turn structured synthesis (No multi-turn agent history overhead)
        system_prompt = (
            "You are an open-source mentor. Given raw issue summaries, select 3 genuinely beginner-to-intermediate. DO NOT TALK LIKE A PERSON "
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
        
        # Handle string or content list cleanly
        content = ai_msg.content
        if isinstance(content, list):
            final_text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        else:
            final_text = str(content)

        self.logger.log(f"[FINAL RESPONSE]\n{final_text}")
        return final_text


def main():
    github_token, gemini_key = get_credentials()
    parser = argparse.ArgumentParser(
        description="Token-efficient roadmap generator from GitHub open issues."
    )
    parser.add_argument("-r", "--repo", type=str, required=True, help="Target GitHub repo")
    # Reduced default issue limit from 15 to 8 (sufficient for selecting 3 issues)
    parser.add_argument("-l", "--limit", type=int, default=8, help="Issues to retrieve (default: 8)")
    parser.add_argument("-o", "--output", type=str, default="OUTPUT.md", help="Output file")
    parser.add_argument("--log-file", type=str, default="steps.txt", help="Execution log path")
    parser.add_argument("--model", type=str, default="gemma-4-26b-a4b-it", help="Model name")

    args = parser.parse_args()

    pipeline = ContributorRoadmapPipeline(model_name=args.model, log_file=args.log_file)
    markdown_roadmap = pipeline.run(repo_target=args.repo, limit=args.limit)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown_roadmap)

    print("\nExecution complete:")
    print(f" - Log file: {args.log_file}")
    print(f" - Markdown roadmap: {args.output}")
    print(f" - Total execution time: {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    main()