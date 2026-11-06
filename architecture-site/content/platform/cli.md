# Command line

The command is `compassx`, implemented by `compassx.cli.main:app`. It does not call Docker, kubectl, or Helm itself. It asks `PlatformManager`, and the launchers perform the infrastructure calls.

`--profile` / `-p` selects a profile. `--verbose` / `-v` sets logging to DEBUG. The default format is `%(asctime)s %(levelname)s %(name)s: %(message)s`.

`compassx up [SERVICES...]` prints `Starting platform with profile {name}...`, starts the services, and prints the status table. When every reported service is running it prints `Platform ready.` Otherwise it prints `Platform started (some services not running).` `--no-wait` skips the health wait. `--timeout` is the health wait in seconds, default `300`.

`compassx down [SERVICES...]` stops the services and prints `Platform stopped.`

`compassx restart [SERVICES...]` restarts the services and prints the status table.

`compassx status` prints the status table. The title is `Platform status — profile {name}`. Columns are Service, Running, Healthy, and Detail. Running and Healthy render `yes` or `no`. Healthy renders `-` when the launcher did not report it.

`compassx health` prints a table titled `Health — profile {name}`. Columns are Service, Endpoint, Status, Latency, and Root cause. A healthy row shows `healthy` and `{latency}ms`. An unhealthy row shows the cause, or `down`, and the message. Latency is `-` when there is no measurement. The process exits `0` when every service is healthy and `1` otherwise.

`compassx logs SERVICE` prints the launcher output. `--tail` / `-n` defaults to `200`. Empty output prints `<no logs>`.

`compassx profile list` prints one profile per line. The active profile from `.compassx/active-profile` is marked with `*`. The others have a leading space. The names are `docker`, `kubernetes-cloud`, `kubernetes-local`, and `local-dev`.

`compassx profile use NAME` checks that the profile file exists, writes `.compassx/active-profile`, and prints `Active profile set to {name}`.

Any `PlatformError` prints `Error: {message}` and the process exits `1`.

Each command function in `compassx.cli.main` forwards to the matching file in `compassx/cli/application/`. The Typer help text stays on the facade.
