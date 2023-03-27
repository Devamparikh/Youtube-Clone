import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime
import subprocess
import re

def get_latest_tag():
    # Get the repository name and owner from the environment variables
    repo_name = os.environ['GITHUB_REPOSITORY']
    repo_owner = repo_name.split('/')[0]

    # Make a request to the GitHub API to get the latest release tag
    response = requests.get(f'https://api.github.com/repos/{repo_name}/releases/latest')
    latest_tag = response.json()['tag_name']

    return latest_tag

def create_jira_release():
    # Get the latest release tag from GitHub
    latest_tag = get_latest_tag()

    # Get the Jira API token from GitHub secrets
    jira_token = os.environ['JIRA_TOKEN']

    # Set up the Jira API URL, authentication, and headers
    url = "https://devamparikh.atlassian.net/rest/api/3/version"
    auth = HTTPBasicAuth("devamparikh15@gmail.com", jira_token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Set up the payload with the release name, description, and current date as release date
    payload = json.dumps({
        "archived": False,
        "description": f"Release created automatically from GitHub tag {latest_tag}",
        "name": latest_tag,
        "projectId": 10000,  # Replace with your Jira project ID
        "releaseDate": datetime.now().strftime("%Y-%m-%d"),
        "released": False
    })

    # Send the API request to create the release
    response = requests.post(url, data=payload, headers=headers, auth=auth)

    # Print the response to the console for debugging purposes
    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    # Extract the name of the created release from the Jira API response
    release_name = response.json()['name']

    # Return the name of the created release
    return release_name

def extract_jira_issue_ids():
    commit_message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B']).decode('utf-8')
    jira_issue_ids = set(re.findall(r'\[jira_issue_id: ([A-Z]+-\d+)\]', commit_message))
    return list(jira_issue_ids)

def get_issue_fix_version(issue_id):
    # Set up the JIRA API endpoint
    endpoint = f"https://devamparikh.atlassian.net/rest/api/3/issue/{issue_id}"
    auth = HTTPBasicAuth("devamparikh15@gmail.com", os.environ['JIRA_TOKEN'])
    headers = {"Accept": "application/json"}

    # Send a GET request to the endpoint
    response = requests.get(endpoint, headers=headers, auth=auth)

    # Extract the fixVersions from the response
    fix_versions = json.loads(response.text)["fields"]["fixVersions"]
    if fix_versions:
        return fix_versions[0]["name"]
    else:
        return None
    
# Function to add Jira release as fixVersion for each issue
def add_fix_version_to_issues(jira_issue_ids, jira_release_id):
    # Jira API endpoint for updating an issue
    api_endpoint = "https://devamparikh.atlassian.net/rest/api/3/issue/"

    # Jira API authentication details
    jira_username = "devamparikh15@gmail.com"
    jira_token = os.environ.get("JIRA_TOKEN")
    auth = HTTPBasicAuth(jira_username, jira_token)

    # Jira API request headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Loop over each Jira issue ID
    for issue_id in jira_issue_ids:
        # Get the existing fixVersions for the issue
        existing_fix_versions = get_issue_fix_version(issue_id)

        # Create payload to update fixVersions for the issue
        payload = {
            "fields": {
                "fixVersions": []
            }
        }

        # Add the Jira release as a fixVersion if it's not already there
        if jira_release_id not in existing_fix_versions:
            payload["fields"]["fixVersions"].append({
                "name": jira_release_id
            })

        # Add the existing fixVersions to the payload
        for fix_version in existing_fix_versions:
            payload["fields"]["fixVersions"].append({
                "name": fix_version
            })

        # Send PUT request to update the issue
        issue_url = api_endpoint + issue_id
        response = requests.put(issue_url, headers=headers, auth=auth, data=json.dumps(payload))

        # Check if the request was successful
        if response.status_code == 200:
            print(f"Fix version added to issue {issue_id}")
        else:
            print(f"Error adding fix version to issue {issue_id}: {response.text}")

jira_issue_ids = extract_jira_issue_ids()
jira_release_id = create_jira_release()
add_fix_version_to_issues(jira_issue_ids, jira_release_id)
