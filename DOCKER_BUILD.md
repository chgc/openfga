# Building and Running OpenFGA with MariaDB Locally

## Build the Local Docker Image

Build the OpenFGA image locally with the `local` tag:

```bash
docker build -t openfga/openfga:local .
```

## Run with Docker Compose

Start the MariaDB stack (database + migrate + openfga):

```bash
docker compose -f docker-compose.mariadb.yaml up
```

Or run in detached mode:

```bash
docker compose -f docker-compose.mariadb.yaml up -d
```

## Verify the Setup

Check that all services are healthy:

```bash
docker compose -f docker-compose.mariadb.yaml ps
```

Access OpenFGA:
- HTTP API: http://localhost:8080
- gRPC: localhost:8081
- Playground: http://localhost:3000
- Metrics: http://localhost:2112/metrics

## Stop and Clean Up

Stop all services:

```bash
docker compose -f docker-compose.mariadb.yaml down
```

Stop and remove volumes:

```bash
docker compose -f docker-compose.mariadb.yaml down -v
```

## Development Workflow

1. Make code changes
2. Rebuild the image: `docker build -t openfga/openfga:local .`
3. Restart services: `docker compose -f docker-compose.mariadb.yaml up --force-recreate`

## Alternative: Use Makefile for Quick Testing

For rapid development without Docker Compose, use the Makefile:

```bash
# Install locally and run with MariaDB
DATASTORE="mysql" make dev-run
```

Note: This uses hot-reloading with CompileDaemon for faster iteration.
