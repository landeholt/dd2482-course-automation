import argparse
from datetime import datetime
import pytz
from functools import reduce
import logging
from pathlib import Path
import re
from typing import Any, Optional, cast
import sys
import json
import requests
from exceptions import AfterDeadlineError, AmbiguousRepoError, MissingRepoError, PrivateRepoError, UnclearPullRequest

Payload = dict[str, Any]
GITHUB_URL = re.compile(r"https:\/\/(?:www\.)?github\.com\/(([^\/(?:KTH)])+)\/([\w\d\-\_]+)")
# propose, proposal, final, final submission
STAGE_PATTERN = re.compile(r"(propos(?:e|al)|(?:final(?: submission)?|submission))")
PROPOSAL = re.compile(r"(propos(?:e|al))")
FINAL = re.compile(r"(final(?: submission)?|submission)")

DATETIME_FORMAT = "%m/%d/%Y %H:%M:%S"

logger = logging.getLogger(__name__)


def parse_datetime_str(raw_datetime: str):
    try:
        return pytz.utc.localize(datetime.strptime(raw_datetime, DATETIME_FORMAT))
    except Exception:
        return datetime.strptime(raw_datetime, "%Y-%m-%dT%H:%M:%S%z")
        


def get_payload(path: Path) -> Payload:
    return json.loads(path.read_bytes())

def get_pull_request(payload: Payload) -> Payload:
    return payload.get("pull_request", dict())

def get_created_at(payload: Payload) -> datetime:
    pr = get_pull_request(payload)
    return parse_datetime_str(pr.get("created_at"))

def get_comments_url(payload: Payload) -> str:
    pr = get_pull_request(payload)
    return pr.get("comments_url")

def get_pull_request_files(payload: Payload) -> list[Payload]:
    pr = get_pull_request(payload)
    url = pr["url"] + "/files"
    return requests.get(url=url).json()

def get_pr_body(payload: Payload) -> str:
    pr = get_pull_request(payload)
    return pr.get("body", "")

def get_body(payload: Payload) -> str:
    
    files = get_pull_request_files(payload)
    
    def get(filename: str):
        owner, repo, __, branch = get_meta_details(payload)
        return requests.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}").text.lower()
    
    def keep_markdown():
        return reduce(lambda acc, file_ : acc + [(file_["filename"],get(file_["filename"]))] if file_["filename"].endswith(".md") and file_["status"] != "removed" else acc, files, [])
    
    kept_files: list[tuple[str,str]] = keep_markdown()
    
    if len(kept_files) == 0:
        raise FileNotFoundError("Pull request did not have any committed files")
    
    blob = '---'.join(map(lambda x : x[1], kept_files))
    return blob
    

def get_meta_details(payload: Payload):
    pr = get_pull_request(payload)
    repository = cast(Payload,payload.get("repository"))
    head = cast(Payload, pr.get("head"))
    ref = head.get("ref")
    sha = head.get("sha")
    repo = repository.get("name")
    owner: str = cast(Payload,repository.get("owner"))["login"]
    return owner, repo, sha, ref
    

def get_repo_urls(body: str) -> list[tuple[str, str]]:
    partials = GITHUB_URL.findall(body)
    result = []
    for r in partials:
        match = GITHUB_URL.match(r)
        if match:
            owner, repo = match.groups()
            result.append((owner, repo))
    return result

def get_stage(body: str):
    result = list(set(STAGE_PATTERN.findall(body)))
    # first instance is weighted to be most important
    # this selection is bound to fail. Better solution must be mandated.
    if len(result) == 0:
        return None
    first = result[0]
    if FINAL.match(first):
        return "final_submission"
    return "proposal"

def get_issue_number(payload: Payload):
    pr = get_pull_request(payload)
    return pr["number"]

def get_repo(owner: str, repo: str, secret: Optional[str]) -> dict[str, str]:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {}
    if secret:
        headers["Authorization"] = f"token {secret}"
    return requests.get(url=url,headers=headers).json()
    
def get_args(args: dict[str, str]) -> tuple[datetime, Payload, Optional[str]]:
    d, e, s = args.get("d"), args.get("e"), args.get('s')
    try:
        if not d:
            raise ValueError("Please provide a deadline")
        if not e:
            raise FileNotFoundError("Cannot find event payload")
        return parse_datetime_str(d), get_payload(Path(e)), s
    except Exception as exc:
        raise exc
       

def check_repo(repo, secret):
    owner, repo_name, = repo
    
    repo = get_repo(owner, repo_name, secret)
    is_private = repo.get("private", True)
    
    if is_private:
        raise PrivateRepoError("Provided repo is not public")
    

def validate(deadline: datetime, payload: Payload, secret: Optional[str] = None):
    
    payload["__result__"] = {"stage": "proposal", "repos": [], "created_at": None}
    
    
    # 1. Validate that PR is created before deadline
    
    created_at = get_created_at(payload)
    if created_at > deadline:
        raise AfterDeadlineError(f"Pull request after deadline: {deadline}")
    
    payload["__result__"]["created_at"] = created_at
    
    body = get_body(payload)
    
    found_stage = get_stage(body)
    if found_stage:
        payload["__result__"]["stage"] = found_stage
    
    # 2. PR readme.md must have url to remote repo.
    repo_urls = get_repo_urls(body)
    if len(repo_urls) == 0:
        raise MissingRepoError("No remote repository url found in provided pull request. Please provide one, or clearly state in your pull request that it is only a proposal.")
    
    # 3. PR readme.md must state whether it is a proposal or submission
    if not found_stage:
        raise UnclearPullRequest("Cannot find whether PR is __final submission__ or __proposal__. Please state it explicitly in your PR. Preferably as the title.")
    
    
    # 4. PR readme.md must have public repos
    for repo in repo_urls:
        check_repo(repo, secret)
    
    payload["__result__"]["repos"] += list(map(lambda x : x[1], repo_urls))


def give_feedback(payload: Payload, secret: Optional[str], error_message: Optional[str] = None):
    
    result: dict[str, str] = payload["__result__"]
    
    
    if not secret:
        raise ValueError("No provided github secret")
    
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {secret}"}
    log = logger.error if error_message else logger.info

    def set_labels(labels: list[str]):
        issue_number = get_issue_number(payload)
        owner, repo, *_ = get_meta_details(payload)
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/labels"
        json_ = {"labels": labels}
        log("[POST::LABELS]: " + str(json_))
        return requests.post(url=url,headers=headers,json=json_)
    

    def set_status(status: str, description: str, target_url: Optional[str] = None):
        owner, repo, sha, _ = get_meta_details(payload)
        url = f"https://api.github.com/repos/{owner}/{repo}/statuses/{sha}"
        json_ = {'status': status, 'description': description, 'context': 'Check mandatory part(s)'}
        if target_url:
            json_['target_url'] = target_url
            
        log("[POST::STATUS]: " + str(json_))
        return requests.post(url=url,headers=headers,json=json_).json()
    
    
    def send_comment(body: str):
        url = get_comments_url(payload)
        json_ = {"body": body}
        log("[POST::PR-COMMENT]: " + str(json_))
        return requests.post(url=url,headers=headers,json=json_).json()
    
    def format_body():
        repos = result["repos"]
        created_at = result["created_at"]
        stage = result["stage"]
        decision_message = "\n---\n\nDecision is based on the following findings:\n\n"
        decision_message += f"stage: {stage}\n"
        decision_message += f"created_at: {created_at}\n"
        decision_message += f"repos:\n"
        decision_message += '\n'.join(map(lambda x : '\t- ' + x,repos))
        if error_message:
            return error_message +  decision_message
        return "All mandatory parts where found. Awaiting TA for final judgement." + decision_message
    
        
    status = 'failure' if error_message else "success"
    description = 'Validation failed' if error_message else "Validation successful"
    body = format_body()
    
    labels = ["course_automation"]
    
    if status != "failure":
        labels.append(result["stage"])
    
    
    set_labels(labels)
    
    response = send_comment(body)
    url = response.get("html_url")
    
    set_status(status,description,url)
    
    
def run(args: dict[str, str]):
    payload, secret = {}, None
    try:
        deadline, payload, secret = get_args(args)
        validate(deadline, payload, secret)
                
        logger.info("Validation successful")
        give_feedback(payload, secret)
    
    except Exception as exc:
        message = "Error: " + " ".join(exc.args)
        
        logger.error(message)
        give_feedback(payload, secret, error_message=message)

        sys.exit(message)
        
    

def cli():
    parser = argparse.ArgumentParser(description="automatic course-automation evaluator")
    parser.add_argument('--deadline', dest="d",help="Deadline for the first task in the course")
    parser.add_argument('--event', dest="e",help="Event path")
    parser.add_argument('--secret', dest="s",help="Github secret")
    args = parser.parse_args()
    args = vars(args)
    
    
    run(args)
    
if __name__ == "__main__":
    cli()
    
