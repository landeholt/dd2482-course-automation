# 1. check date
# 2. check for readme / pull request body
# 3. check for github.com url
# 4. extract owner, repo
# 5. check if public
# 6. feedback


import argparse
from datetime import datetime
import logging
from pathlib import Path
import re
from typing import Any, Optional, cast
import sys
import json
import requests

from exceptions import AfterDeadlineError, AmbiguousRepoError, MissingRepoError, PrivateRepoError, UnclearPullRequest

Payload = dict[str, Any]
GITHUB_URL = re.compile(r"https:\/\/(?:www\.)?github\.com\/([^\/]+)\/([\w\d\-\_]+)")
# propose, proposal, final, final submission
STAGE_PATTERN = re.compile(r"(propos(?:e|al)|final(?: submission)?)")
PROPOSAL = re.compile(r"(propos(?:e|al))")
FINAL = re.compile(r"(final(?: submission)?)")
# 2019-05-15T15:20:33Z
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

logger = logging.getLogger(__name__)


def parse_datetime_str(raw_datetime: str):
    return datetime.strptime(raw_datetime, DATETIME_FORMAT)


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

def get_body(payload: Payload) -> str:
    pr = get_pull_request(payload)
    return pr.get("body", "")

def get_meta_details(payload: Payload):
    pr = get_pull_request(payload)
    repository = cast(Payload,payload.get("repository"))
    head = cast(Payload, pr.get("head"))
    sha = head.get("sha")
    repo = repository.get("name")
    owner: str = cast(Payload,repository.get("owner"))["login"]
    return owner, repo, sha
    

def get_repo_urls(body: str) -> list[str]:
    return list(set(GITHUB_URL.findall(body)))

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
        
    

def validate(deadline: datetime, payload: Payload, secret: Optional[str] = None):
    
    payload["__result__"] = {"stage": "proposal"}
    
    created_at = get_created_at(payload)
    if created_at > deadline:
        raise AfterDeadlineError(f"Pull request after deadline: {deadline}")
    
    body = get_body(payload)
    
    stage = get_stage(body)
    is_final = False
    if stage:
        payload["__result__"]["stage"] = stage
        is_final = payload["__result__"]["stage"] == "final_submission"
    
    
    repo_urls = get_repo_urls(body)
    if len(repo_urls) == 0 and is_final:
        raise MissingRepoError("No repository url found in provided pull request. Please provide one, or clearly state in your pull request that it is only a proposal.")
    
    elif len(repo_urls) == 0 and not stage:
        # when stage is not explictly defined
        raise UnclearPullRequest("Cannot evaluate whether PR is final submission or proposal. Please state it explicitly in your PR")
    elif len(repo_urls) == 1 and not is_final and stage:
        # explicitly proposal
        return
    elif len(repo_urls) == 1 and not stage:
        # when unexplictly final_submission
        is_final = True
        payload["__result__"]["stage"] = "final_submission"
        
    elif len(repo_urls) > 1:
        raise AmbiguousRepoError("More than one repo was provided in the pull request")
    
    
    owner, repo_name = repo_urls[0]
    
    repo = get_repo(owner, repo_name, secret)
    is_private = repo.get("private", True)
    
    if is_private:
        raise PrivateRepoError("Provided repo is not public")


def give_feedback(payload: Payload, secret: Optional[str], error_message: Optional[str] = None):
    
    if not secret:
        raise ValueError("No provided github secret")
    
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {secret}"}
    log = logger.error if error_message else logger.info

    def set_labels(labels: list[str]):
        issue_number = get_issue_number(payload)
        owner, repo, _ = get_meta_details(payload)
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/labels"
        json_ = {"labels": labels}
        log("[POST::LABELS]: " + str(json_))
        return requests.post(url=url,headers=headers,json=json_)
    

    def set_status(status: str, description: str, target_url: Optional[str] = None):
        owner, repo, sha = get_meta_details(payload)
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
    
    result: dict[str, str] = payload["__result__"]
        
    status = 'failure' if error_message else "success"
    description = 'Validation failed' if error_message else "Validation successful"
    body = error_message or "All mandatory parts where found. Awaiting TA for final judgement."
    
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
        message = " ".join(exc.args)
        
        logger.error(message)
        give_feedback(payload, secret, error_message=message)

        sys.exit(message)
        
    

def cli():
    parser = argparse.ArgumentParser(description="automatic course-automation evaluator")
    parser.add_argument('-d', action="store_const",required=True,const=None,help="Deadline for the first task in the course")
    parser.add_argument('-e', action="store_const",required=True,const=None,help="Event path")
    parser.add_argument('-s', action="store_const",required=True,const=None,help="Github secret")
    
    args = parser.parse_args()
    args = vars(args)
    
    run(args)
    
if __name__ == "__main__":
    cli()
    
