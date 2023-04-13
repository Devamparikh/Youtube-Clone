import os
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime
import subprocess
import re

projects = {'IDEA': '11330', 'KB': '11331', 'PRM': '11335', 'BI': '11336', 'PRO': '11338', 'SAL': '11339', 'AUTO': '11341', 'WRK': '11342', 'AUCS': '11344', 'DESK': '10900', 'DNA': '11351', 'DAAS': '11352', 'DGO': '11354', 'DLH': '11355', 'VIZ': '11356', 'RES': '11358', 'SRE': '11360', 'IT': '11361', 'FCLTS': '11363', 'ID': '11364', 'OPS': '10000', 'DOMO': '11365', 'SANDBOX': '11302', 'INFOSEC': '11368', 'UNI': '11304', 'COMM': '11307', 'HAND': '11371', 'FIN': '11308', 'PA': '11372', 'PUB': '11309', 'CHA': '11310', 'DISC': '11374', 'SEL': '11311', 'BUY': '11312', 'CAR': '11313', 'PAR': '11314', 'UXF': '11315', 'EXP': '11316', 'AUC': '11317', 'PDL': '11318', 'TEST': '11319', 'DAT': '11320', 'VAL': '11000', 'ARC': '10107' }

def get_latest_tag():
    # Get the repository name and owner from the environment variables
    repo_name = os.environ['GITHUB_REPOSITORY']

    # Make a request to the GitHub API to get the latest release tag
    response = requests.get(f'https://api.github.com/repos/{repo_name}/releases/latest')
    latest_tag = response.json()['tag_name']
    
    if not latest_tag:
        raise ValueError("Latest tag is empty.")
    
    return latest_tag

def extract_jira_release_name():
    repo_name = os.environ['GITHUB_REPOSITORY']
    jira_release_name = repo_name.split('/')[1]
    return jira_release_name

def extract_jira_project_id():
    project_name = os.environ['PROJECT_NAME']
    jira_project_id = ''

    if projects.get(project_name):
        jira_project_id = projects.get(project_name)
    else:
        raise ValueError("PROJECT_NAME is incorrect or not present in project list.")
    
    return jira_project_id

def extract_jira_issue_ids():
    commit_message = subprocess.check_output('git log --pretty=%B | awk "/release-please--branches--stable--components--release-please-action/{c++;if(c==2)exit} c==1"', shell=True).decode('utf-8')
    print(commit_message)
    jira_issue_ids = set(re.findall(r'\b[A-Z][A-Z0-9_]+-[1-9][0-9]*', commit_message))
    print(jira_issue_ids)
    project_name = os.environ['PROJECT_NAME']

    if project_name:
        jira_issue_ids = {elem for elem in jira_issue_ids if elem.startswith(project_name)}
    else:
        raise ValueError("PROJECT_NAME is not present as environment variable.")

    return list(jira_issue_ids)

def create_jira_release(jira_release_name):
    # Get the latest release tag from GitHub
    latest_tag = get_latest_tag()
    project_id = extract_jira_project_id()

    # Get the Jira API token from GitHub secrets
    jira_token = os.environ['JIRA_TOKEN']

    # Set up the Jira API URL, authentication, and headers
    url = "https://devamparikh.atlassian.net/rest/api/3/version"
    auth = HTTPBasicAuth("devamparikh15@gmail.com", jira_token)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    if jira_release_name:
        release_name = jira_release_name + '-' + latest_tag
    else:
        release_name = latest_tag

    description = f"Release created automatically for GitHub tag {latest_tag} \n \n"
    changelog = subprocess.check_output('git diff $(git log --merges --pretty=format:%H -n 2 | tail -1) -- CHANGELOG.md | grep "^+" | grep -v "+++" | sed "s/^+//;/^$/d"', shell=True).decode('utf-8')
    
    if changelog:
        description += changelog

    # Set up the payload with the release name, description, and current date as release date
    payload = json.dumps({
        "archived": False,
        "description": description,
        "name": release_name,
        "projectId": project_id,  # Replace with your Jira project ID
        "releaseDate": datetime.now().strftime("%Y-%m-%d"),
        "released": False
    })

    # Send the API request to create the release
    response = requests.post(url, data=payload, headers=headers, auth=auth)
    
    if response.status_code // 100 != 2:  # not a 2xx response code
        raise Exception(f'Request to create Jira release failed with status code {response.status_code}')

    # Print the response to the console for debugging purposes
    # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    # Extract the name of the created release from the Jira API response
    release_name = response.json()['name']

    # Return the name of the created release
    return release_name

def get_issue_fix_version(issue_id):
    # Set up the JIRA API endpoint
    endpoint = f"https://devamparikh.atlassian.net/rest/api/3/issue/{issue_id}"
    auth = HTTPBasicAuth("devamparikh15@gmail.com", os.environ['JIRA_TOKEN'])
    headers = {"Accept": "application/json"}

    # Send a GET request to the endpoint
    response = requests.get(endpoint, headers=headers, auth=auth)

    # Extract the fixVersions from the response
    data = json.loads(response.text)
    fix_versions = data["fields"]["fixVersions"]
    existing_fix_versions = []

    for version in fix_versions:
        existing_fix_versions.append(version["name"])
    
    return existing_fix_versions
    
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
        if existing_fix_versions is not None:
            # Convert single object to list
            if not isinstance(existing_fix_versions, list):
                existing_fix_versions = [existing_fix_versions]
            for fix_version in existing_fix_versions:
                payload["fields"]["fixVersions"].append({
                    "name": fix_version
                })

        # Send PUT request to update the issue
        issue_url = api_endpoint + issue_id
        response = requests.put(issue_url, headers=headers, auth=auth, data=json.dumps(payload))

        # Check if the request was successful
        if response.status_code // 100 != 2:  # not a 2xx response code
            raise ValueError(f'Could not able to attach fixVersion for Jira Issue: {issue_id}')

jira_issue_ids = extract_jira_issue_ids()
jira_release_name = extract_jira_release_name()
jira_release_id = create_jira_release(jira_release_name)
add_fix_version_to_issues(jira_issue_ids, jira_release_id)
