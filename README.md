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
2. add the query endpoint function to [src/managers/...](src/managers). Add the imports from the [database models](src/master/db/models) and [parsers](src/managers).
3. add the parser function to [src/managers/...](src/managers)
4. add sql database ORM models to [src/master/db/models/](src/master/db/models)
5. do the alembic migration review at [migrations/versions](migrations/versions)

    5.1 bring infra up 

    > % make infra-up

    5.2 run the migration

    --entrypoint is needed because [migrate serive](docker-compose.yml) already had an entrypoint in the .yml file. it will create a container with `migration_container_name` in the header and the `migration_path` at the bottom

    > % docker compose run --entrypoint alembic migrate revision --autogenerate -m "message"

    5.3 copy the migration file from container to project file system

    use the `migration_container_name` as before or find it with 

    > % docker ps -a | grep `platform-migrate`

    then

    > % docker cp `migration_path` ./migrations/versions/

    5.4 remove the migration container

    > % docker rm `migration_container_name`

    5.5 run the alembic upgrade head or:

    > % make infra-up
    
    > % make migrate

    since it already have `alembic upgrade head` as entrypoint.

    5.6 check is table is in the databse

    > % docker compose exec `db` psql -U `$USER` -d `$DB` -c "\d `table_name`"

6. wire in the endpoint through [src/managers/sync.py](src/managers/sync.py)

    might need to do some additions in [src/master/db/queries.py](src/master/db/queries.py) due to the upsert signature

    6.1 add new source at [sync.py/SOURCES](src/managers/sync.py) and [routes.py/fetch_status_map](src/app/web/routes.py)