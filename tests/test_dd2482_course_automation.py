from copy import copy
import logging
import sys
from dd2482_course_automation import __version__, validate, AfterDeadlineError, PrivateRepoError, MissingRepoError, AmbiguousRepoError, get_args, give_feedback, run
from pathlib import Path
import pytest
import requests
import dd2482_course_automation.main as main

resource_dir = Path(__file__).parent / "resources"

def mock_get_repo_public(owner, repo, secret):
    return {"private": False}

def mock_get_repo_private(owner, repo, secret):
    return {}

original_get_repo = copy(main.get_repo)
main.get_repo = mock_get_repo_public

class MockException(Exception):
    pass

class MockResponse:

    @staticmethod
    def json():
        return {"html_url": "TARGET"}

def test_version():
    assert __version__ == '0.1.0'

def test_correct_validate():
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_submission.json")}
    
    d, e, s = get_args(args)
    validate(d,e)
    
def test_invalid_arguments():
    with pytest.raises(ValueError):
        args = {}
        d, e, s = get_args(args)
        validate(d,e)

def test_wrong_path():
    with pytest.raises(FileNotFoundError):
        args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "nonexisting_payload.json")}
        d, e, s = get_args(args)
        validate(d,e)

def test_after_deadline():
    with pytest.raises(AfterDeadlineError):
        args = {'d': '2010-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_submission.json")}
        d, e, s = get_args(args)
        validate(d,e)

def test_missing_repo():
    with pytest.raises(MissingRepoError):
        args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_no_repo.json")}
        d, e, s = get_args(args)
        validate(d,e)

def test_ambiguous_repos():
    with pytest.raises(AmbiguousRepoError):
        args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_ambiguous.json")}
        d, e, s = get_args(args)
        validate(d,e)

def test_private_repo():
    main.get_repo = mock_get_repo_private
    with pytest.raises(PrivateRepoError):
        args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_private_repo.json")}
        d, e, s = get_args(args)
        validate(d,e)
        
    main.get_repo = mock_get_repo_public

def test_feedback_no_secret():
    with pytest.raises(ValueError):
        args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_submission.json")}
        
        d, e, s = get_args(args)
        validate(d,e)
        give_feedback(e, s)

def test_feedback_positive(caplog, monkeypatch):
    
    def mock_post(*a, **k):
        return MockResponse()
    
    caplog.set_level(logging.INFO)
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_submission.json"), 's': 'random'}
    
    
    d, e, s = get_args(args)
    validate(d,e)
    
    monkeypatch.setattr(requests, "post",mock_post)
    e["__result__"] = {"stage": "final_submission"}
    give_feedback(e, s)
    expected_logs = ["[POST::LABELS]: {'labels': ['course_automation', 'final_submission']}","[POST::PR-COMMENT]: {'body': 'All mandatory parts where found. Awaiting TA for final judgement.'}", "[POST::STATUS]: {'status': 'success', 'description': 'Validation successful', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'INFO'
        assert record.message == log
    


def test_feedback_negative(caplog, monkeypatch):
    
    def mock_post(*a, **k):
        return MockResponse()
    
    caplog.set_level(logging.INFO)
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_submission.json"), 's': 'random'}
    
    
    d, e, s = get_args(args)
    validate(d,e)
    
    monkeypatch.setattr(requests, "post",mock_post)
    e["__result__"] = {"stage": "final_submission"}
    
    give_feedback(e, s, error_message="a generic error")
    expected_logs = ["[POST::LABELS]: {'labels': ['course_automation']}","[POST::PR-COMMENT]: {'body': 'a generic error'}", "[POST::STATUS]: {'status': 'failure', 'description': 'Validation failed', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'ERROR'
        assert record.message == log

def test_valid_proposal(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    monkeypatch.setattr(requests, "post",mock_post)
    
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_proposal.json"), 's': 'random'}
    run(args)
    expected_logs = ["Validation successful","[POST::LABELS]: {'labels': ['course_automation', 'proposal']}","[POST::PR-COMMENT]: {'body': 'All mandatory parts where found. Awaiting TA for final judgement.'}", "[POST::STATUS]: {'status': 'success', 'description': 'Validation successful', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'INFO'
        assert record.message == log

def test_valid_submission(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    monkeypatch.setattr(requests, "post",mock_post)
    
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_proposal.json"), 's': 'random'}
    run(args)
    expected_logs = ["Validation successful","[POST::LABELS]: {'labels': ['course_automation', 'proposal']}","[POST::PR-COMMENT]: {'body': 'All mandatory parts where found. Awaiting TA for final judgement.'}", "[POST::STATUS]: {'status': 'success', 'description': 'Validation successful', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'INFO'
        assert record.message == log

def test_invalid_submission_no_repo(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    def mock_exit(*a, **k):
        raise MockException(*a)
    
    monkeypatch.setattr(requests, "post",mock_post)
    monkeypatch.setattr(sys, "exit",mock_exit)
    
    # valid date, invalid pr-body-no-repo
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_no_repo.json"), 's': 'random'}
    with pytest.raises(MockException):
        run(args)
    expected_logs = ["No repository url found in provided pull request. Please provide one, or clearly state in your pull request that it is only a proposal.","[POST::LABELS]: {'labels': ['course_automation']}","[POST::PR-COMMENT]: {'body': 'No repository url found in provided pull request. Please provide one, or clearly state in your pull request that it is only a proposal.'}", "[POST::STATUS]: {'status': 'failure', 'description': 'Validation failed', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'ERROR'
        assert record.message == log

def test_invalid_submission_many_repo(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    
    def mock_post(*a, **k):
        return MockResponse()
    
    def mock_exit(*a, **k):
        raise MockException(*a)
    
    monkeypatch.setattr(requests, "post",mock_post)
    monkeypatch.setattr(sys, "exit",mock_exit)
    
    # valid date, invalid pr-body-many-repo
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_ambiguous.json"), 's': 'random'}
    with pytest.raises(MockException):
        run(args)
    expected_logs = ["More than one repo was provided in the pull request","[POST::LABELS]: {'labels': ['course_automation']}","[POST::PR-COMMENT]: {'body': 'More than one repo was provided in the pull request'}", "[POST::STATUS]: {'status': 'failure', 'description': 'Validation failed', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'ERROR'
        assert record.message == log

def test_invalid_proposal_after_deadline(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    def mock_exit(*a, **k):
        raise MockException(*a)
    
    monkeypatch.setattr(requests, "post",mock_post)
    monkeypatch.setattr(sys, "exit",mock_exit)
    
    # invalid date, invalid pr-body
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_late_proposal.json"), 's': 'random'}
    with pytest.raises(MockException):
        run(args)
    expected_logs = ["Pull request after deadline: 2022-04-05 17:00:00+00:00","[POST::LABELS]: {'labels': ['course_automation']}","[POST::PR-COMMENT]: {'body': 'Pull request after deadline: 2022-04-05 17:00:00+00:00'}", "[POST::STATUS]: {'status': 'failure', 'description': 'Validation failed', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'ERROR'
        assert record.message == log

def test_invalid_submission_after_deadline(caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    def mock_exit(*a, **k):
        raise MockException(*a)
    
    monkeypatch.setattr(requests, "post",mock_post)
    monkeypatch.setattr(sys, "exit",mock_exit)
    
    # invalid date, invalid pr-body
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_late_submission.json"), 's': 'random'}
    with pytest.raises(MockException):
        run(args)
    expected_logs = ["Pull request after deadline: 2022-04-05 17:00:00+00:00","[POST::LABELS]: {'labels': ['course_automation']}","[POST::PR-COMMENT]: {'body': 'Pull request after deadline: 2022-04-05 17:00:00+00:00'}", "[POST::STATUS]: {'status': 'failure', 'description': 'Validation failed', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'ERROR'
        assert record.message == log

def test_valid_submission_miss_labeled(caplog, monkeypatch):
    # EDGE CASE: PR has repo and is created before deadline, but is not defined as final submission
    caplog.set_level(logging.INFO)
    
    def mock_post(*a, **k):
        return MockResponse()
    
    monkeypatch.setattr(requests, "post",mock_post)
    
    args = {'d': '2022-04-05T17:00:00Z', 'e': str(resource_dir / "payload_valid_undefined.json"), 's': 'random'}
    run(args)
    expected_logs = ["Validation successful","[POST::LABELS]: {'labels': ['course_automation', 'final_submission']}","[POST::PR-COMMENT]: {'body': 'All mandatory parts where found. Awaiting TA for final judgement.'}", "[POST::STATUS]: {'status': 'success', 'description': 'Validation successful', 'context': 'Check mandatory part(s)', 'target_url': 'TARGET'}"]
    for record, log in zip(caplog.records, expected_logs):
        assert record.levelname == 'INFO'
        assert record.message == log
