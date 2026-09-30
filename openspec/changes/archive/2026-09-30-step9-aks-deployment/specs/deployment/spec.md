## ADDED Requirements

### Requirement: Managed Kubernetes Target for This Iteration
The deployed system SHALL run on a managed Kubernetes service in the owner's Azure subscription, with every resource it depends on created in a single region declared in the infrastructure definitions, and with the cluster raised on demand for a working session and destroyed at the end of it rather than left running.

This is the one requirement in this capability that names a provider, and it is deliberately the only one: Step 10 modifies this requirement and must be able to leave every other requirement below untouched. Any requirement Step 10 cannot satisfy without rewording either belongs here or is written wrong.

#### Scenario: A session begins
- **WHEN** the owner authorizes a raise and the cluster is created from the repository's definitions
- **THEN** the cluster SHALL be created in the region the cost inventory was priced for
- **AND** no resource SHALL be created in any other region

#### Scenario: A session ends
- **WHEN** the working session the cluster was raised for is over
- **THEN** the cluster SHALL be destroyed rather than left running
- **AND** the repository SHALL contain no procedure that assumes a cluster is already up

### Requirement: Every Deployed Object Originates in Version Control
Every Kubernetes object and every cloud resource the deployment depends on SHALL be defined in a version-controlled file and created from that file. No object required for the system to serve traffic SHALL owe its existence to a command an operator has to remember, and the repository SHALL NOT document one as a deployment step.

#### Scenario: A cluster is raised from a clean checkout
- **WHEN** an operator with the necessary credentials raises a cluster from a fresh clone at a given commit, following only the repository's own procedure
- **THEN** the system SHALL reach a serving state with no object created by an ad-hoc command typed at a terminal
- **AND** a second raise from the same commit SHALL produce the same set of objects

#### Scenario: An out-of-band step is genuinely unavoidable
- **WHEN** a value cannot be committed — a secret's plaintext, or a credential the owner must supply
- **THEN** the out-of-band step SHALL be limited to supplying that value into a store the definitions already reference
- **AND** it SHALL NOT extend to creating, naming, or shaping any object the definitions do not already declare

### Requirement: The Full User-Facing Stack Runs on the Cluster
Both the API backend and the browser client SHALL be deployed to the cluster, so that the deployment can be exercised end to end by a user rather than only by an API call. Components whose purpose is to hold history across sessions SHALL NOT be deployed to an ephemeral cluster.

#### Scenario: The deployed system is exercised end to end
- **WHEN** an operator reaches the deployed browser client and asks a travel question
- **THEN** the request SHALL be served by the backend running on the same cluster
- **AND** a grounded response SHALL be returned, without any part of the round trip depending on a process running on the operator's machine

#### Scenario: History-holding components are not placed on an ephemeral cluster
- **WHEN** the cluster is raised
- **THEN** no metrics-storage or dashboard workload whose data is expected to outlive a session SHALL be deployed onto it
- **AND** destroying the cluster SHALL therefore destroy no observability history

### Requirement: Secret Values Never Enter the Repository, an Image, or Infrastructure State
The application's secret material SHALL be held in a secret store, delivered to the workload at run time, and SHALL never appear in a version-controlled file, in a built image layer, in infrastructure state, or in a CI provider's stored configuration. The workload SHALL obtain it using a credential bound to the workload's own identity and issued for the occasion, not a long-lived credential stored somewhere for the purpose.

#### Scenario: The repository and infrastructure state are searched
- **WHEN** the repository at any commit on this branch, and any state file the infrastructure definitions produce, are searched for the secret's value
- **THEN** the value SHALL NOT be present in either

#### Scenario: The workload reads its secret
- **WHEN** a pod starts and the application reads the secret from its environment as it does today
- **THEN** the value SHALL have been delivered from the secret store for that pod
- **AND** no application source file SHALL have changed to make that work

#### Scenario: A workload identity is revoked
- **WHEN** the workload's identity loses its grant on the secret store
- **THEN** subsequent pods SHALL fail to obtain the secret
- **AND** no cached long-lived credential SHALL let them succeed anyway

### Requirement: Deployment Inputs Are Parameters, Not Edits
Everything that differs between one deploy and the next — at minimum the image identity, the API origin the browser client calls, and the origins the backend accepts — SHALL be supplied as declared inputs to a single version-controlled definition of the workload. Deploying a new build SHALL NOT require editing a tracked file, rendering a per-deploy copy of one, or substituting text into one from a CI script.

The definition being parameterised rather than rendered is itself the requirement, not a packaging preference: it is what keeps the deployment contract readable in the repository instead of scattered across workflow steps, and what lets Step 10 change values rather than rewrite manifests.

#### Scenario: A new commit is deployed
- **WHEN** a new commit is built and deployed
- **THEN** the only thing that differs from the previous deploy SHALL be the values supplied at deploy time
- **AND** no tracked file SHALL have been modified to effect the deploy

#### Scenario: The workload definition is checked before a cluster exists
- **WHEN** a reviewer renders the workload definition with a given set of input values
- **THEN** the complete set of objects that would be created SHALL be inspectable and machine-validatable without a cluster
- **AND** that check SHALL be runnable in CI

### Requirement: Automation Publishes and Deploys Without Stored Long-Lived Credentials
The pipeline SHALL publish images to a registry the cluster can pull from and deploy them, authenticating to the cloud with a short-lived credential issued to the workflow run and scoped to this repository. No long-lived cloud credential SHALL be stored in the CI provider. Published images SHALL be identified by the commit they were built from.

#### Scenario: A merge to the default branch
- **WHEN** a commit is merged to the default branch
- **THEN** images SHALL be published under an identifier that names that commit
- **AND** the deploy SHALL reference that identifier rather than a moving tag

#### Scenario: CI runs where no deployment is intended
- **WHEN** the pipeline runs on a pull request, or in a fork with no cloud configuration at all
- **THEN** the publish and deploy steps SHALL NOT run
- **AND** the pipeline SHALL still complete successfully, preserving its "passes on a fresh fork with zero configuration" property

#### Scenario: The CI provider's stored configuration is inspected
- **WHEN** the secrets and variables configured for this repository are listed
- **THEN** none SHALL be a credential that would still authenticate if copied out
- **AND** any stored value SHALL be an identifier only

### Requirement: Deployment Configuration Defaults to Current Local Behaviour
Configuration the cluster supplies SHALL be readable from the environment with defaults that reproduce today's local behaviour exactly, so that a developer who pulls this branch and runs the local stack, or runs the test suite, observes no change.

#### Scenario: Nothing is configured
- **WHEN** the backend starts with no deployment-related configuration set
- **THEN** the origins it accepts SHALL be exactly what it accepts today
- **AND** the local stack and the test suite SHALL behave as they do now

#### Scenario: The cluster supplies its own values
- **WHEN** the deployment supplies an origin the browser client is actually served from
- **THEN** the backend SHALL accept requests from that origin
- **AND** a request from an origin that was not supplied SHALL NOT be accepted

#### Scenario: The browser client is built for a target
- **WHEN** the client image deployed to the cluster is built
- **THEN** the API address it calls SHALL be determined by that build from a supplied value
- **AND** it SHALL NOT fall back to an address that only resolves on a developer's machine

### Requirement: The Retrieval Corpus Is Available to Every Serving Replica Without a Manual Step
The vector store the retrieval path reads SHALL NOT be per-pod local state, and SHALL NOT depend on an operator running an ingestion command against a running pod after deployment. Every replica serving traffic SHALL read the same corpus.

The mechanism is deliberately unspecified: a shared retrieval service and a single-replica attached volume both satisfy this requirement.

#### Scenario: A pod is replaced
- **WHEN** a serving pod is restarted, rescheduled, or replaced by a new deploy
- **THEN** the replacement SHALL answer corpus-grounded questions from the same corpus
- **AND** no operator action SHALL be required between the replacement starting and it answering correctly

#### Scenario: More than one replica serves traffic
- **WHEN** the deployment declares more than one serving replica
- **THEN** the same query SHALL retrieve the same context regardless of which replica handles it

#### Scenario: A raise follows a teardown
- **WHEN** a cluster is raised after a previous one was destroyed
- **THEN** the procedure that restores the corpus SHALL be part of the repository's deployment definitions
- **AND** it SHALL NOT be a step an operator is expected to remember

### Requirement: HTTP Routing Is Expressed in Portable Terms
The routed entry point in front of the deployed services SHALL be expressed in upstream Kubernetes API resources, with provider-specific binding confined to named fields and annotations on those resources. The services behind it SHALL remain cluster-internal.

The portability is the requirement rather than a preference: `docs/plan.md` makes the ingress layer one of the things Step 10 is meant to prove moves between clouds, so a route definition that has to be rewritten to port is a failed requirement, not a rough edge.

#### Scenario: Traffic reaches the application through the entry point
- **WHEN** a request is sent to the routed entry point
- **THEN** it SHALL be routed to the correct service by rules stated in version-controlled resources
- **AND** the services themselves SHALL NOT be individually exposed outside the cluster

#### Scenario: The definitions are read against a port to another provider
- **WHEN** the route definitions are examined for what a port to a different managed Kubernetes provider would have to change
- **THEN** the changes SHALL be limited to the controller binding and provider annotations
- **AND** the routing rules themselves SHALL be unchanged

### Requirement: No Traffic Crosses an Untrusted Network Unencrypted
No request to the deployed system SHALL traverse a network the operator does not control without being encrypted. While the entry point is not reachable from outside the cluster and the only access path is an already-encrypted, authenticated tunnel, the entry point's own listener need not terminate TLS; the moment the entry point becomes reachable without that tunnel, a validatable certificate becomes a precondition for exposing it.

#### Scenario: The entry point is internal
- **WHEN** the deployment is raised as designed
- **THEN** the entry point SHALL have no address reachable from the public internet
- **AND** operator access SHALL be through an authenticated, encrypted tunnel to the cluster

#### Scenario: Someone proposes to expose the entry point
- **WHEN** a change would make the entry point reachable without that tunnel
- **THEN** that change SHALL NOT be complete without a certificate a client can validate
- **AND** the absence of a certificate today SHALL NOT be cited as precedent for exposing a plaintext listener

#### Scenario: Clients are never told to skip verification
- **WHEN** the repository documents how to reach the deployed system
- **THEN** no documented step SHALL instruct a client to disable certificate verification

### Requirement: Runtime Resource Consumption Is Observable Without Endangering Existing History
Per-container CPU and memory consumption for every application container SHALL be collectable from the cluster without hand-written scrape configuration, and queryable from the tooling the operator already uses. Collection SHALL be limited to a declared set rather than defaulting to everything available. Nothing in the raise, verify or destroy cycle SHALL read, move, overwrite or delete the existing local metrics history.

#### Scenario: A session's consumption is inspected
- **WHEN** an operator queries the collected metrics during or after a session
- **THEN** CPU usage, memory working set, and CPU throttling SHALL be available per application container
- **AND** they SHALL be reachable from the same dashboard tool the local stack already uses

#### Scenario: Collection scope is bounded
- **WHEN** metric collection is configured
- **THEN** the set collected SHALL be a stated setting in a version-controlled file
- **AND** it SHALL NOT be whatever the collector gathers when left at its broadest default

#### Scenario: The local history is unaffected
- **WHEN** a cluster is raised, verified, and destroyed
- **THEN** the existing local metrics volume SHALL be untouched by every step of that cycle
- **AND** no procedure in this capability SHALL name a command that would destroy it

### Requirement: Cluster Capacity Is Established by Measurement, Not Assumption
The cluster's node pool SHALL satisfy the provider's documented minimum requirements for the pool type it uses, and SHALL be shown by measurement on a raised cluster to have capacity for the platform's own components together with the workload. Workload objects SHALL declare resource requests, so that a shortfall surfaces as a scheduling decision rather than as contention.

#### Scenario: A cluster is raised for the first time
- **WHEN** the workload is deployed to the raised cluster
- **THEN** no application pod SHALL remain unschedulable
- **AND** the actual requests and allocatable capacity SHALL be measured and recorded rather than inferred

#### Scenario: The sizing is challenged later
- **WHEN** someone asks whether the pool could be smaller or must be larger
- **THEN** the recorded measurement SHALL be the basis of the answer
- **AND** any figure quoted SHALL be traceable to the run that produced it

### Requirement: No Billable Resource Exists Before Approval and Authorization
No billable cloud resource SHALL be created until the complete inventory of what would be created and what each item costs has been approved by the owner, and the owner has separately authorized the specific raise. Approval of the inventory SHALL NOT be treated as authorization to apply.

#### Scenario: The inventory is approved
- **WHEN** the owner approves the cost inventory
- **THEN** that approval SHALL permit no resource to be created by itself
- **AND** a subsequent raise SHALL require its own explicit go-ahead

#### Scenario: An apply is attempted without authorization
- **WHEN** any step would create a billable resource and no go-ahead for that run has been given
- **THEN** the step SHALL stop and report rather than proceed

#### Scenario: The inventory is read
- **WHEN** the owner reads the inventory in order to approve it
- **THEN** every resource that will bill SHALL be listed with its rate
- **AND** every figure SHALL name the source it was read from

### Requirement: Teardown Destroys the Session and Nothing Else
Teardown SHALL destroy every resource created for the session and SHALL leave intact the resources the design designates as surviving, so that the pipeline still works on the next merge. Teardown SHALL be a distinct operation from any command that destroys local development data, and the repository SHALL never present the two as one step.

#### Scenario: A session is torn down
- **WHEN** teardown runs
- **THEN** no per-hour billable resource created for that session SHALL remain
- **AND** the registry and the secret store SHALL still exist, with the pipeline still able to publish and the secret still readable by the next raise

#### Scenario: Teardown is documented
- **WHEN** the teardown procedure is written down
- **THEN** it SHALL state that it has no relationship to destroying local volumes
- **AND** no procedure in this capability SHALL pair the two in a single instruction

#### Scenario: Standing cost between sessions
- **WHEN** no session is running
- **THEN** the only cost incurred SHALL come from resources the design explicitly designates as surviving

### Requirement: The Step Is Complete Only When a Verified Raise Is Recorded
This capability SHALL NOT be considered delivered when its definitions are written. It SHALL be considered delivered when a cluster has been raised from those definitions, exercised against the scenarios above, destroyed, and the observations recorded in `docs/`. The record SHALL state which previously-unverified claims the run settled, what each measured, and which remain open.

#### Scenario: The definitions are written but never run
- **WHEN** the infrastructure definitions, the workload definition and the pipeline changes are complete and reviewed
- **THEN** the step SHALL still be incomplete
- **AND** the outstanding work SHALL be the raise, the verification, the teardown, and the record

#### Scenario: A verification run is recorded
- **WHEN** a raise/verify/destroy cycle completes
- **THEN** the record SHALL name the commit and the cluster version it ran against
- **AND** each measurement SHALL appear once, with anything still unverified named as such rather than omitted

#### Scenario: A claim the run could not settle
- **WHEN** the run does not answer a question the design flagged as unverified
- **THEN** the record SHALL say so explicitly
- **AND** it SHALL name what would settle it, rather than leaving the gap silent
