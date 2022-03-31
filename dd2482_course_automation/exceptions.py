class AfterDeadlineError(Exception):
    pass

class MissingRepoError(Exception):
    pass

class AmbiguousRepoError(Exception):
    pass

class PrivateRepoError(Exception):
    pass

class UnclearPullRequest(Exception):
    pass
