# Platform layer

This layer contains the shared platform services for ingestion and data persistence.

Structure:
- [app/](src/app): the front-end interface
- [managers/](src/managers): source-specific ingestion managers
- [master/](src/master): shared database, storage, and stream orchestration

## Resources Needed:
- A PostgreSQL database container

## Overall project structure:
```
root/
│ 
└───infrastructure/
│   │   db-credentials.env
│   │   docker-compose.yml
│   │   Makefile
│   
└───platform/
│   │   migrations/
│   │   src/
│   │   docker-compose.yml
│   │   Dockerfile
│   │   Makefile
│   │   ...
│
└───projects/
    │   project-1/
    │   project-2/
    │   ...
```

## To run the Platform
Only the platform layer
> % make up 

Platform layer + infra
> % make up-all

## To add a new source

### from a new client
[...] to be included [...]

### from an existing client
1. add the fixed query parameters to [src/config.py](src/managers/config.py)
2. add sql database ORM models to [src/master/db/models/](src/master/db/models)
3. add the query endpoint function to [src/managers/...](src/managers). Add the imports from the [database models](src/master/db/models) and [parsers](src/managers).
4. add the parser function to [src/managers/...](src/managers)
5. do the alembic migration review at [migrations/versions](migrations/versions)

    5.1 bring infra up and build the app image so the new SQL models are there

    > % make infra-up

    > % make build

    5.2 run the migration

    --entrypoint is needed because [migrate serive](docker-compose.yml) already had an entrypoint in the .yml file. it will show the `migration_path` at the bottom

    > % docker compose run --name gen_migration --entrypoint alembic migrate revision --autogenerate -m "message"

    5.3 copy the migration file from container to project file system

    > % docker cp gen_migration:`migration_path` ./migrations/versions/

    5.4 remove the migration container

    > % docker rm gen_migration

    5.5 run the alembic upgrade head:
    make migrate now does all the work needed to apply the upgrade. make infra up, copy the new version file to the image (so migration service could access it) and run the alembic upgrade head.

    > % make migrate

    5.6 check is table is in the databse

    > % docker compose exec `db` psql -U `$USER` -d `$DB` -c "\d `table_name`"

    5.7 to downgrade (and immediatly remove the container)

    > % docker compose run --rm --entrypoint alembic migrate downgrade -1

6. wire in the endpoint through [src/managers/sync.py](src/managers/sync.py)

    might need to do some additions in [src/master/db/queries.py](src/master/db/queries.py) due to the upsert signature

    6.1 add new source at [sync.py/SOURCES](src/managers/sync.py) and [routes.py/fetch_status_map](src/app/web/routes.py)