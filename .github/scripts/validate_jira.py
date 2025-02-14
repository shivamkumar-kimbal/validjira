import os
import re
import sys
import subprocess
import requests
from base64 import b64encode
from typing import List, Tuple, Optional

class JiraTicketValidator:
    def __init__(self):
        # Using dummy values for testing
        self.jira_base_url = os.environ.get('JIRA_BASE_URL', 'https://dummy-jira.atlassian.net')
        self.jira_username = os.environ.get('JIRA_USERNAME', 'dummy@example.com')
        self.jira_api_token = os.environ.get('JIRA_API_TOKEN', 'dummy-token')
        self.test_mode = os.environ.get('TEST_MODE', 'true').lower() == 'true'

        # Basic auth header for Jira API
        auth_str = f"{self.jira_username}:{self.jira_api_token}"
        self.auth_header = b64encode(auth_str.encode()).decode()

    def get_commit_messages(self) -> List[Tuple[str, str]]:
        """Get commit messages for validation."""
        if self.test_mode:
            # In test mode, only check the last 3 commits
            git_command = ['git', 'log', '-n', '3', '--format=%H%n%s%n%b']
        else:
            # In PR context, check commits in the PR
            base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
            git_command = ['git', 'log', f'origin/{base_ref}..HEAD', '--format=%H%n%s%n%b']

        result = subprocess.run(
            git_command,
            capture_output=True,
            text=True
        )

        commits = []
        messages = result.stdout.strip().split('\n\n')
        for message in messages:
            if not message.strip():
                continue
            lines = message.strip().split('\n')
            if len(lines) >= 2:  # Ensure we have both hash and message
                commits.append((lines[0], '\n'.join(lines[1:])))
        return commits

    def extract_jira_ticket(self, message: str) -> Optional[str]:
        """Extract Jira ticket from commit message using regex."""
        pattern = r'([A-Z]+-\d+)'
        match = re.search(pattern, message)
        return match.group(1) if match else None

    def validate_jira_ticket(self, ticket: str) -> bool:
        """
        Validate if Jira ticket exists and is valid.
        For dummy values, accept tickets matching TEST-* pattern.
        """
        if self.jira_base_url == 'https://dummy-jira.atlassian.net':
            # For testing: accept any ticket starting with TEST-
            return ticket.startswith('TEST-')

        headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

        url = f"{self.jira_base_url}/rest/api/2/issue/{ticket}"

        try:
            response = requests.get(url, headers=headers)
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"::error::Error validating Jira ticket: {str(e)}")
            return False

    def run_validation(self):
        """Main validation logic."""
        commits = self.get_commit_messages()
        has_invalid_commits = False

        for sha, message in commits:
            ticket = self.extract_jira_ticket(message)

            if not ticket:
                print(f"::error::Commit {sha[:8]} does not contain a Jira ticket reference")
                print(f"Commit message: {message}")
                has_invalid_commits = True
                continue

            if not self.validate_jira_ticket(ticket):
                print(f"::error::Commit {sha[:8]} contains invalid Jira ticket: {ticket}")
                print(f"Commit message: {message}")
                has_invalid_commits = True
                continue

            print(f"✓ Commit {sha[:8]} has valid Jira ticket: {ticket}")

        if has_invalid_commits:
            print("\nValidation failed! Please ensure all commits:")
            print("1. Include a valid Jira ticket reference (e.g., TEST-123)")
            print("2. Reference existing Jira tickets")
            print("\nTo fix:")
            print("1. Use 'git commit --amend' to edit the most recent commit")
            print("2. Use 'git rebase -i' to edit older commits")
            sys.exit(1)

        print("\n✓ All commits have valid Jira ticket references")

if __name__ == "__main__":
    validator = JiraTicketValidator()
    validator.run_validation()
