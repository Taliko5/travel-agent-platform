## MODIFIED Requirements

### Requirement: Automation Publishes and Deploys Without Stored Long-Lived Credentials
The pipeline SHALL publish images to a registry the cluster can pull from and deploy them, authenticating to the cloud with a short-lived credential issued to the workflow run and scoped to this repository. No long-lived cloud credential SHALL be stored in the CI provider. Published images SHALL be identified by the commit they were built from.

#### Scenario: A merge to the release branch
- **WHEN** a commit is merged to the release branch
- **THEN** images SHALL be published under an identifier that names that commit
- **AND** the deploy SHALL reference that identifier rather than a moving tag

#### Scenario: A push to the default branch
- **WHEN** a commit is pushed to the default branch
- **THEN** the publish and deploy steps SHALL NOT run
- **AND** the pipeline SHALL NOT authenticate to the cloud

#### Scenario: CI runs where no deployment is intended
- **WHEN** the pipeline runs on a pull request, or in a fork with no cloud configuration at all
- **THEN** the publish and deploy steps SHALL NOT run
- **AND** the pipeline SHALL still complete successfully, preserving its "passes on a fresh fork with zero configuration" property

#### Scenario: The CI provider's stored configuration is inspected
- **WHEN** the secrets and variables configured for this repository are listed
- **THEN** none SHALL be a credential that would still authenticate if copied out
- **AND** any stored value SHALL be an identifier only

## ADDED Requirements

### Requirement: A Deploy Succeeds Only When the Workload Becomes Ready
The system SHALL report a deploy as successful only once the deployed workload has reached a ready state within a bounded time, and SHALL report it as failed if that bound is exceeded rather than reporting success once its instructions have merely been accepted. On failure, the system SHALL retain, as part of the run's own record, enough diagnostic information about the workload's state to investigate the failure after the underlying infrastructure no longer exists.

#### Scenario: The workload becomes ready in time
- **WHEN** a deploy runs and the deployed workload reaches a ready state within the bound
- **THEN** the deploy SHALL be reported as successful

#### Scenario: The workload does not become ready in time
- **WHEN** a deploy runs and the deployed workload does not reach a ready state within the bound
- **THEN** the deploy SHALL be reported as failed
- **AND** the run's own record SHALL retain diagnostic information about the workload's unready state, sufficient to investigate after the infrastructure it describes is gone

### Requirement: A Deploy Fails When No Target Exists
The system SHALL fail the deploy when a merge into the release branch occurs while no deployment target is available, rather than reporting success or silently skipping it.

#### Scenario: A merge occurs while no cluster is raised
- **WHEN** a commit is merged into the release branch while no cluster is available to deploy to
- **THEN** the deploy SHALL fail
- **AND** SHALL NOT be reported as successful, and SHALL NOT be silently skipped

### Requirement: An In-Progress Deploy Runs to Completion
The system SHALL NOT interrupt a deploy that has already started. Once it finishes, the system SHALL deploy the most recent merge into the release branch. A merge that was superseded by a newer one while waiting need not be deployed on its own, since the newer merge already contains it.

#### Scenario: A merge lands while a deploy is running
- **WHEN** a commit is merged into the release branch while an earlier deploy triggered by a previous merge is still running
- **THEN** the running deploy SHALL be allowed to finish rather than being interrupted
- **AND** once it finishes, the system SHALL deploy the most recent merge into the release branch

#### Scenario: A merge is superseded before its deploy starts
- **WHEN** more than one merge into the release branch lands while a deploy is running, so only the most recent of them is still waiting once that deploy finishes
- **THEN** the superseded merges need not be deployed on their own
- **AND** the deploy for the most recent merge SHALL be treated as covering them, since it contains their changes

### Requirement: The Release Branch Advances Only Through Traceable Merges
The release branch SHALL change only through a pull request originating from the default branch, merged in a way that preserves the default branch's own commits within the resulting history. The release branch's history SHALL NOT be rewritten or deleted.

#### Scenario: The release branch is updated
- **WHEN** a change is introduced to the release branch
- **THEN** it SHALL have arrived through a pull request from the default branch
- **AND** the commits that were on the default branch SHALL remain present, unaltered, within the release branch's resulting history

#### Scenario: An attempt to rewrite or delete history
- **WHEN** an attempt is made to force-push over or delete the release branch
- **THEN** the repository SHALL be configured to reject it

### Requirement: Deploy Tooling Versions Are Version-Controlled
The versions of the tooling the deploy process depends on SHALL change only through a commit to the repository, never through an external default resolved at run time.

#### Scenario: A deploy runs
- **WHEN** a deploy runs
- **THEN** the versions of the tooling it depends on SHALL be exactly what the repository's committed configuration specifies at that commit
- **AND** SHALL NOT vary from one run to the next unless a commit changed them
