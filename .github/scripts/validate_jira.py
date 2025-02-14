import os
import re
import sys
import subprocess
import requests
from base64 import b64encode
from typing import List, Tuple, Optional

class JiraTicketValidator:
    def __init__(self):
        # Get Jira credentials from environment variables
        self.jira_base_url = os.getenv('JIRA_BASE_URL', 'https://dummy-jira.atlassian.net')
        self.jira_username = os.getenv('JIRA_USERNAME', 'dummy@example.com')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN', 'dummy-token')
        self.test_mode = os.getenv('TEST_MODE', 'true').lower() == 'true'

        # Create Basic Auth header
        auth_str = f"{self.jira_username}:{self.jira_api_token}"
        self.auth_header = b64encode(auth_str.encode()).decode()

    def get_commit_messages(self) -> List[Tuple[str, str]]:
        """Get commit messages for validation."""
        try:
            if self.test_mode:
                git_command = ['git', 'log', '-n', '3', '--pretty=format:%H||%s %b']
            else:
                base_ref = os.getenv('GITHUB_BASE_REF', 'main')
                git_command = ['git', 'log', f'origin/{base_ref}..HEAD', '--pretty=format:%H||%s %b']

            result = subprocess.run(git_command, capture_output=True, text=True, check=True)

            commits = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("||", 1)
                if len(parts) == 2:
                    commits.append((parts[0], parts[1]))
            return commits

        except subprocess.CalledProcessError as e:
            print(f"::error::Git command failed: {e}")
            sys.exit(1)

    def extract_jira_ticket(self, message: str) -> Optional[str]:
        """Extract Jira ticket from commit message using regex."""
        pattern = r'([A-Z]+-\d+)'
        match = re.search(pattern, message)
        return match.group(1) if match else None

    def validate_jira_ticket(self, ticket: str) -> bool:
        """Validate if Jira ticket exists."""
        if self.jira_base_url == 'https://dummy-jira.atlassian.net':
            return ticket.startswith('TEST-')

        headers = {
            'Authorization': f'Basic {self.auth_header}',
            'Content-Type': 'application/json'
        }

        url = f"{self.jira_base_url}/rest/api/2/issue/{ticket}"

        try:
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"::error::Error validating Jira ticket: {e}")
            return False

    def run_validation(self):
        """Main validation logic."""
        commits = self.get_commit_messages()
        has_invalid_commits = False

        for sha, message in commits:
            ticket = self.extract_jira_ticket(message)

            if not ticket:
                print(f"::error::Commit {sha[:8]} does not contain a Jira ticket reference")
                has_invalid_commits = True
                continue

            if not self.validate_jira_ticket(ticket):
                print(f"::error::Commit {sha[:8]} contains invalid Jira ticket: {ticket}")
                has_invalid_commits = True
                continue

            print(f"✓ Commit {sha[:8]} has valid Jira ticket: {ticket}")

        if has_invalid_commits:
            sys.exit(1)

if __name__ == "__main__":
    validator = JiraTicketValidator()
    validator.run_validation()
