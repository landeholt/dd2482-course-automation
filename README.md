# Meta course-automation

## Takeaways

- Github actions autoparses datetimes
- Fetches from `https://raw.githubusercontent.com` are cached with a duration or 300s (5min)
  - This can be side-stepped by providing the SHA. `https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}`
- hidden characters are hell. `Especially \r.`
- Github actions are nice
- Its hard to debug, as the payload is like a blackbox. Should exist a tool to test actions locally. [Dagger](https://github.com/dagger/dagger) seems to have this feature.

## Validation [link](https://github.com/landeholt/dd2482-course-automation/pull/8)
1. A PR is valid when: it is `final_submission`, created/updated before deadline and contains a public repository link.

> ## All mandatory parts were found. Awaiting TA for final judgement.
> Decision is based on the following findings:
> 
> created at: 2022-04-01 15:47:52+00:00
> 
> ## contributions/course-automation/johnlan/README.md
> assumed stage: `final_submission`
> 
> ```gfm
> ...
> # Assignment Submission    <-- HERE
> 
> ## Title
> 
> Automatic verification for mandatory parts of course-automation final
> ...
> ```
> 
> repos: - [dd2482-course-automation](https://www.github.com/landeholt/dd2482-course-automation)

2. A PR is valid when: it is a `proposal` and created/updated before deadline.

> ## All mandatory parts were found. Awaiting TA for final judgement.
> Decision is based on the following findings:
> 
> created at: 2022-04-01 15:50:18+00:00
> 
> ## contributions/course-automation/johnlan/README.md
> assumed stage: `proposal`
> 
> ```gfm
> ...
> # Assignment Proposal    <-- HERE
> 
> ## Title
> 
> Automatic verification for mandatory parts of course-automation final
> 
> ...
> ```
> 
> repos: - No repos found

3. A PR is invalid when:  PR is a `final_submission` and found repositories are private

> ## Error: Provided repo is not public
> Decision is based on the following findings:
> 
> created at: 2022-04-01 15:48:40+00:00
> 
> ## contributions/course-automation/johnlan/README.md
> assumed stage: `final_submission`
> 
> ```gfm
> ...
> # Assignment Submission    <-- HERE
> 
> ## Title
> 
> Automatic verification for mandatory parts of course-automation final
> ...
> ```
> 
> repos: - [dd2482-course-automation-very-secret](https://www.github.com/landeholt/dd2482-course-automation-very-secret)

4. A PR is invalid when: PR is a `final_submission` and doe not contain any repository links.

> ## Error: No remote repository url found in provided pull request. Please provide one, or clearly state in your pull request that it is only a proposal.
> Decision is based on the following findings:
> 
> created at: 2022-04-01 15:49:34+00:00
> 
> ## contributions/course-automation/johnlan/README.md
> assumed stage: `final_submission`
> 
> ```gfm
> ...
> # Assignment Submission    <-- HERE
> 
> ## Title
> 
> Automatic verification for mandatory parts of course-automation final
> ...
> ```
> 
> repos: - No repos found

5. A PR is invalid when: PR cannot be determined if it is **final submission** or **proposal**

> ## Error: Cannot find whether PR is **final submission** or **proposal**. Please state it explicitly in your PR. Preferably as the title.
> Decision is based on the following findings:
> 
> created at: 2022-04-01 15:50:56+00:00
> 
> ## contributions/course-automation/johnlan/README.md
> assumed stage: **NOT FOUND** repos: - No repos found

## Solution
