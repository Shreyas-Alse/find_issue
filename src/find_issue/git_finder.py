from github import Github
import os

token = os.getenv('GITHUB_TOKEN')
g = Github(token)



issues_data = []

def fetch_issues(repo_name, limit):
    repo = g.get_repo(repo_name)
    issues = repo.get_issues(state='open', labels=['good first issue', 'help wanted'])
    count = 0
    for issue in issues:
        if not issue.pull_request: 
            issues_data.append({
                'number': issue.number,
                'title': issue.title,
                'labels': [label.name for label in issue.labels],
                'body': issue.body,
            })
            count += 1
            if count >= limit:
                break

    return issues_data


