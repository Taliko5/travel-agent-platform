## MODIFIED Requirements

### Requirement: Local Prometheus and Grafana Services with Persistent Storage
The system SHALL provide `prometheus` and `grafana` services in `docker-compose.yaml` that can reach the backend's `/metrics` endpoint on the compose network, with Grafana pre-configured to query the Prometheus service as a datasource, with each service's data persisted in a named Docker volume so it survives a container restart, and with Prometheus' retention explicitly configured in the repository rather than left to whatever the image's default happens to be.

#### Scenario: Full stack starts via docker-compose
- **WHEN** a user runs `docker-compose up --build`
- **THEN** the `prometheus` and `grafana` services SHALL start alongside `backend` and `frontend`
- **AND** the `backend` service SHALL NOT depend on `prometheus`/`grafana` being healthy to start

#### Scenario: Prometheus scrapes the backend target
- **WHEN** the `prometheus` service is running with its provisioned scrape config
- **THEN** Prometheus SHALL list the backend's `/metrics` endpoint as a scrape target

#### Scenario: Grafana has a working Prometheus datasource
- **WHEN** a user opens the Grafana UI
- **THEN** a Prometheus datasource pointing at the compose `prometheus` service SHALL already be configured, without manual datasource setup

#### Scenario: Restarting the stack preserves prior data
- **WHEN** a user runs `docker-compose restart prometheus grafana` (not `down -v`) after metrics have been scraped
- **THEN** previously scraped Prometheus data and Grafana configuration SHALL still be present after the restart

#### Scenario: Prometheus' retention is explicit and bounded
- **WHEN** the `prometheus` service starts with this repository's configuration
- **THEN** its effective `storage.tsdb.retention.time` and `storage.tsdb.retention.size` SHALL be values stated in a version-controlled file, not the image's undocumented default
- **AND** both values SHALL be finite — neither left unset in a way that makes either dimension unbounded
