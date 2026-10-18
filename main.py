import os
import argparse
from datetime import datetime
from typing import Any, List, Union
from config_manager import *

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from git_finder import fetch_issues


# ==========================================
# 1. Step Logger Utility
# ==========================================
class StepLogger:
    """Manages file-based step logging during agent execution."""
    def __init__(self, filename: str = "steps.txt"):
        self.filename = filename
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(f"=== Agent Execution Trace: {datetime.now().isoformat()} ===\n\n")

    def log(self, text: str):
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(text.strip() + "\n\n")


# ==========================================
# 2. Tool Definitions
# ==========================================
@tool
def get_repo_issues(repo_name: str, limit: int = 15) -> str:
    """Fetches open issues from a GitHub repository to analyze them for beginner friendliness."""
    issues = fetch_issues(repo_name, limit)
    if not issues:
        return "No open issues found or failed to retrieve issues."

    formatted = []
    for issue in issues:
        labels_str = ", ".join(issue.get("labels", []))
        raw_body = issue.get("body") or "No description provided."
        
        # Token efficiency safeguard: truncate massive stack traces or junk dumps
        truncated_body = raw_body[:1200] + "..." if len(raw_body) > 1200 else raw_body

        formatted.append(
            f"Issue #{issue['number']}: {issue['title']}\n"
            f"URL: https://github.com/{repo_name}/issues/{issue['number']}\n"
            f"Labels: {labels_str if labels_str else 'None'}\n"
            f"Body:\n{truncated_body.strip()}"
        )
    return "\n\n" + ("=" * 40) + "\n\n".join(formatted)


# ==========================================
# 3. Content Parsing Utility
# ==========================================
def extract_text_from_content(content: Union[str, List[Any]]) -> str:
    """Safely parses LangChain AIMessage content (supports str, dict, Part objects)."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
            elif hasattr(part, "text"):
                parts.append(getattr(part, "text", ""))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


# ==========================================
# 4. Roadmap Agent Runner
# ==========================================
class ContributorRoadmapAgent:
    def __init__(self, model_name: str = "gemma-4-26b-a4b-it", log_file: str = "steps.txt"):
        self.logger = StepLogger(log_file)
        self.tools = [get_repo_issues]
        self.tool_map = {t.name: t for t in self.tools}

        # Initialize LLM with tool calling
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=1.0,
            top_p=0.95,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def run(self, repo_target: str, limit: int = 15, max_iterations: int = 6) -> str:
        prompt_text = (
            f"Analyze issues in the repository '{repo_target}'. Fetch up to {limit} issues, "
            f"filter out any test or placeholder noise, select the most beginner-friendly ones, "
            f"and generate a clear, step-by-step onboarding roadmap in GitHub-flavored Markdown. "
            f"Include direct hyperlinks to the issues and practical local verification steps."
            f"At the beginning, include the prerequisites for a contributor to get started with this repository."
        )

        messages = [
            SystemMessage(
                content=(
                    "You are an expert open-source mentor. When given a repository, invoke your tools "
                    "to inspect open issues, filter out noise, select beginner-friendly issues, and "
                    "produce a detailed Markdown roadmap to help a contributor solve them."
                )
            ),
            HumanMessage(content=prompt_text),
        ]

        self.logger.log(f"[USER PROMPT]\n{prompt_text}")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            ai_msg = self.llm_with_tools.invoke(messages)
            messages.append(ai_msg)

            # Termination check: No tool calls generated
            if not ai_msg.tool_calls:
                final_text = extract_text_from_content(ai_msg.content)
                self.logger.log(f"[FINAL RESPONSE]\n{final_text}")
                return final_text

            # Execute tool calls
            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                call_id = tool_call["id"]

                self.logger.log(f"[TOOL CALL] {tool_name} with args: {tool_args}")
                print(f"-> Calling tool {tool_name} with args: {tool_args}")

                selected_tool = self.tool_map.get(tool_name)
                if selected_tool:
                    tool_output = selected_tool.invoke(tool_args)
                else:
                    tool_output = f"Tool '{tool_name}' not found."

                self.logger.log(f"[TOOL OUTPUT]\n{tool_output}\n" + "-" * 50)

                messages.append(
                    ToolMessage(
                        content=str(tool_output),
                        tool_call_id=call_id
                    )
                )

        # Fallback if iterations exceed limit
        return "Failed to produce roadmap: Maximum agent loop iterations exceeded."


# ==========================================
# 5. CLI Interface
# ==========================================
def main():

    github_token, gemini_key = get_credentials()
    parser = argparse.ArgumentParser(
        description="Autonomous agent that turns GitHub open issues into actionable onboarding roadmaps."
    )
    parser.add_argument(
        "-r", "--repo",
        type=str,
        required=True,
        help="Target GitHub repository (e.g. rust-lang/rustlings, cli/cli)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=15,
        help="Number of issues to retrieve (default: 15)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="OUTPUT.md",
        help="Output markdown file path (default: OUTPUT.md)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="steps.txt",
        help="File to record execution logs (default: steps.txt)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemma-4-26b-a4b-it",
        help="Gemma model variant to use via the Gemini Developer API"
    )

    args = parser.parse_args()

    agent = ContributorRoadmapAgent(model_name=args.model, log_file=args.log_file)
    print(f"Analyzing {args.repo} (fetching up to {args.limit} issues)...")
    
    markdown_roadmap = agent.run(repo_target=args.repo, limit=args.limit)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(markdown_roadmap)

    print("\nExecution complete:")
    print(f" - Execution trace logged to: {args.log_file}")
    print(f" - Markdown roadmap written to: {args.output}")


if __name__ == "__main__":
    main()