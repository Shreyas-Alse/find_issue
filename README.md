<div align="center">

# 🧭 find_issue

### *Your beginner-friendly roadmap into open source.*

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Powered by Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204-4285F4?logo=google&logoColor=white)](https://ai.google.dev/gemma)
[![Security](https://img.shields.io/badge/Prompt%20Injection-Scanned-success?logo=shield&logoColor=white)](#-built-in-security)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-contributing)

</div>

---

> **🤔 Can't I just ask an AI chatbot?**
> You can, for a one-off. find_issue is for doing it **repeatably and safely**: it pulls issues directly from the GitHub API with your own token (no copy-pasting), gives you the same roadmap format every time with one command, and **scans untrusted issue text and the model's output for prompt injection and risky commands** before you act on anything. And it **doesn't hand you the finished code**: it gives you pointers on what to do and how to check your work, so you learn by doing the contribution yourself.

---

## 💡 Why find_issue?

You've just learnt to code. You're excited. Someone says *"try contributing to open source!"* and then you open a big repository and see **hundreds of issues**, unfamiliar jargon, and no idea where to begin.

It's daunting. Many beginners give up before they ever make their first pull request.

**find_issue exists to change that.** Point it at any GitHub repository and it will:

1. 🔍 **Find** the open issues in the repo
2. 🌱 **Filter** the ones that are genuinely beginner-friendly
3. 🗺️ **Generate** a complete, beginner-friendly roadmap you can act on right away

Built by a learner, for fellow learners, to help more of us grow into open source contributors.

---

## ✨ Features

| | Feature | What it does |
|---|---|---|
| 🔍 | **Issue discovery** | Fetches open issues from a GitHub repository |
| 🌱 | **Beginner filtering** | Selects 3 beginner-to-intermediate issues from the batch |
| 🗺️ | **Contributor roadmap** | Writes an onboarding roadmap as a Markdown file |
| 🛡️ | **Prompt-injection defense** | Regex-based security checks flag the output as compromised |
| 🤖 | **Gemma 4 under the hood** | Runs `gemma-4-26b-a4b-it` through the Gemini API |
| 🔐 | **Guided first-run setup** | A config manager collects your credentials on the first run |
| 📝 | **Execution trace** | Saves the context and model response to `steps.txt` |

---

## 🚀 Installation

### Prerequisites

- **Python 3**
- **[pipx](https://pipx.pypa.io/)**, which installs Python CLI tools in isolated environments
- A **Gemini API key** ([get one here](https://aistudio.google.com/app/apikey))
- A **GitHub Personal Access Token (PAT)** ([create one here](https://github.com/settings/tokens))

### Install

```bash
git clone https://github.com/Shreyas-Alse/find_issue.git
cd find_issue
pipx install .
```

### 🔑 First run

On the first run, the built-in **config manager** asks for your **GitHub PAT** and **Gemini API key**. You only need to provide them once.

---

## 🎯 Usage

```bash
find_issue --repo owner/repo
```

### Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `--repo` | `-r` | *(required)* | Target GitHub repo, as `owner/repo` |
| `--limit` | `-l` | `8` | Number of issues to retrieve |
| `--output` | `-o` | `OUTPUT.md` | Where to write the roadmap |
| `--log-file` | | `steps.txt` | Where to write the execution trace |
| `--model` | | `gemma-4-26b-a4b-it` | Model name to use |

### Examples

```bash
# Basic run
find_issue --repo owner/repo

# Look at 15 issues and save to a custom file
find_issue -r owner/repo -l 15 -o my_roadmap.md
```

### What you get

- **`OUTPUT.md`** (or your `--output` path): the roadmap, with a security banner at the top
- **`steps.txt`** (or your `--log-file` path): the issue context sent to the model and the model's response

---

## 🛡️ Built-in Security

Issue titles and bodies are written by strangers on the internet, which makes them a natural place to hide **prompt injection** attacks aimed at manipulating an AI model. The model's output could also contain risky shell commands that a beginner might run without thinking.

find_issue scans for both, using hardcoded **regex rules**:

- 🔎 **Issue context scan**: looks for injection phrases such as "ignore previous instructions", "jailbreak", "developer mode enabled", and similar patterns
- 💻 **Output scan**: looks for high-risk commands such as `rm -rf`, `curl | bash`, reverse shells, fork bombs, and access to `/etc/shadow` or `/etc/passwd`
- 🚩 **Compromised-output flagging**: if anything matches, a **security alert banner** is placed at the top of the roadmap listing exactly what was detected, and the terminal reports `[FLAGGED RISKS]`
- ✅ If nothing matches, the roadmap gets a **"Security Verification: PASSED"** banner and the terminal reports `[PASSED]`

> ⚠️ Pattern-based checks reduce risk but are not a guarantee. Always review the roadmap, the linked issues, and any command before running it.

---

## 📸 Sample Output

Running it against a real repository:

```text
$ find_issue -r nextcloud/desktop
-> Fetching 8 issues for nextcloud/desktop via API...
-> Generating roadmap in a single pass...

Execution complete:
 - Log file: steps.txt
 - Markdown roadmap: OUTPUT.md
 - Security scan status: [PASSED]
 - Total execution time: 22.48 seconds
```

And an excerpt of the generated `OUTPUT.md`:

````markdown
> [!NOTE]
> ### Security Verification: PASSED
> **Scan Timestamp:** 2026-10-18 16:52:11
> No prompt injection signatures or destructive system commands detected by rule-based filters. Always review CLI commands before running them locally.

---

# Contributor Onboarding Roadmap: nextcloud/desktop

## Selected Issues

### 1. UI/UX Improvement: Persistent Sync Selection
* **Issue:** [#11082](https://github.com/nextcloud/desktop/issues/11082)
* **Difficulty:** Beginner
* **Description:** The client prompts the user to "Choose how to sync your files" on every launch even after the user has selected "Decide later." This is a state persistence issue.
* **Local Verification:**
    1. Build and launch the client.
    2. Select "Decide later" during the initial setup.
    3. Restart the application.
    4. **Fail condition:** The selection prompt appears again.
    5. **Success condition:** The application launches directly to the main interface without the prompt.
````

---

## 🧠 How It Works

```
   ┌──────────────┐    ┌───────────────┐    ┌───────────────┐    ┌────────────────┐
   │  GitHub repo │ ─▶ │ Fetch issues  │ ─▶ │ Gemma 4 builds│ ─▶ │ Security scan  │
   │ (owner/repo) │    │ (via your PAT)│    │ the roadmap   │    │ (regex rules)  │
   └──────────────┘    └───────────────┘    └───────────────┘    └───────┬────────┘
                                                                         ▼
                                                        📄 OUTPUT.md with security banner
```

---

## 🤝 Contributing

Contributions are very welcome, especially from fellow beginners! If this tool helps you make your first PR, consider making one to improve it.

1. Fork the repo
2. Create a branch: `git checkout -b my-improvement`
3. Commit your changes
4. Open a pull request

---

## 📜 License

Distributed under the **GPL-3.0 License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for every learner taking their first step into open source.**

⭐ If this helped you, consider starring the repo!

</div>