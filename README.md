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

## Sources

### ENTSO-E prices (`entsoe_price`)
12.1.D day-ahead prices (A44) for the 12 Nordic zones and the coupled neighbours DE-LU, NL, PL, LT and EE. GB is not on the ENTSO-E platform after Brexit.

### ENTSO-E generation (`entsoe_generation`)
16.1.B/C actual generation per production type (A75, process A16), per Nordic zone, into `generation`.
- `psr_type` is the production type (B12 hydro reservoir, B14 nuclear, B19 wind onshore, …).
- Storage also comes as a consumption series (marked by `outBiddingZone_Domain`), stored with `direction = 'consumption'`: B10 pumped storage (NO2, NO3, NO5) and B25 energy storage (FI).

### ENTSO-E wind and solar forecast (`entsoe_wind_solar_forecast`)
14.1.D day-ahead forecast (A69, process A01), per Nordic zone, into `wind_solar_forecast`: B16 solar, B18 wind offshore, B19 wind onshore.

### ENTSO-E load forecast (`entsoe_load_forecast`)
6.1.B day-ahead total load forecast (A65, process A01), per Nordic zone, into `load_forecast`.

### ENTSO-E hydro reservoirs (`entsoe_hydro_reservoir`)
16.1.D reservoir filling (A72, process A16) for SE1–4, NO1–5 and FI, into `hydro_reservoir`, in MWh.
- Weekly (`P7D`): each row is a week starting Monday midnight market time (Europe/Brussels), so weeks across a DST change are 167 or 169 hours long in UTC.
- A sync whose start is mid-week, or whose end is after the last published week, asks for that week again on each run; that is one extra request per zone.

### JAO Nordic binding CNECs (`jao_binding_cnec`)
From JAO's Nordic publication tool, *Shadow Price & Flow_FB* page, binding CNECs only (shadow price > 0).
- `binding_cnec`: one row per binding CNEC per MTU, with shadow price, RAM, Fmax, Fref and flow after market coupling. `zone` is always `NORDIC`.
- `cnec_ptdf`: the CNEC's PTDF for each bidding zone and virtual HVDC hub (`SE3`, `SE3_FS`, …), zeros included, joined on `cnec_id`.
- Prices follow p_zone = λ − Σ shadow_price × PTDF_zone for every Nordic zone except DK1. DK1 is synchronous with continental Europe, so its PTDF on Nordic CNECs is ~0 and its price is set mostly by the Hansa/Core side (it tracks DE-LU); leave it out when estimating λ.
- One request per hour, sent sequentially at most once a second, as JAO's API guide asks. Recent business days are fetched only once JAO's monitoring endpoint reports them as `Received`.
- History starts 2024-10-29T23:00Z. Backfill one month per sync, and contact JAO before loading months or years of history; run such loads outside the morning publication window.
- CNEC names published before 2026-05-14 are anonymised (UUIDs); JAO offers a CSV that maps them back to real names on the FB Domain page.

### JAO Nordic border flows and net positions (`jao_fb_monitoring`)
From the same *Shadow Price & Flow_FB* page, the rows JAO generates for monitoring (`Filter={"Tso": [""]}`, ~420 rows per hour). They never bind; what limits a border is in `binding_cnec`. One request per hour fills both tables.
- `fb_border_flow`: one row per border per MTU (`SE3-SE4`, or towards an HVDC hub such as `SE4-SE4_SP`), with `min_flow` / `max_flow` and `flow_fb`, the flow after market coupling. Each min and max is an extreme on its own; two borders at their maximum at once is not guaranteed.
- `fb_net_position`: one row per bidding zone and HVDC hub per MTU, with `min_net_position` / `max_net_position` and `net_position` after market coupling. Positive is export; for a hub, power flowing from the link into its real zone.
- Hubs (`SE4_SP` SwePol, `NO2_NK` NordLink, …) are listed in table 1 of JAO's Nordic publication tool handbook.
- Same pacing and readiness check as `jao_binding_cnec`; gaps are read from `fb_border_flow`.

### ENTSO-E DC link transfer limits (`entsoe_dc_link_transfer_limit`)
11.3 Cross-Border Capacity for DC Links - Intraday Transfer Limits (A93), into `dc_link_transfer_limit`, for the HVDC links in `DC_LINKS`, per direction. No data for the links inside the Nordic flow-based region (e.g. NO2-DK1, SE3-FI); those limits are in `fb_border_flow`.

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