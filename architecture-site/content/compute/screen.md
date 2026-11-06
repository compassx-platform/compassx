# Screen

The compute screen is `frontend/src/modules/compute`. The list route is `compute`. The shell title is **Compute**. A resource detail route is `compute/{resourceId}` and the shell title is **Compute Detail**.

## List

The heading is **Compute**. The tabs are **All-purpose Compute ({n})**, **Services ({n})**, and **Sandboxes ({n})**. The tab is also the `tab` query: `resources`, `services`, or `sandboxes`. Changing a tab clears the status, runtime, and consumer filters.

The search placeholder is `Filter compute resources` on the resources tab, `Filter services` on the services tab, and `Filter sandboxes` on the sandboxes tab.

The resources tab has **Status** and **Runtime** selects, and the button **Create Compute**. An empty table says `No compute resources yet`. The services table empty text is `No compute services found.`

The page loads health once. When health is not `ok`, or the health call returns HTTP 503 with a message, that message is shown above the toolbar. The fallback text is `Compute infrastructure not connected.`

Resources, services, sandboxes, and port-forward status refresh every 10 seconds.

## Create

The dialog title is **Create Compute Resource**. The name placeholder is `e.g., Data Processing Pipeline`. The description placeholder is `Optional description of this compute resource`. The submit button is **Create Resource**, and **Creating…** while the request is in flight. The list calls `POST /resources` and closes the dialog after the list reloads. There is no success toast.

## Detail

The detail page reads one resource and its metrics. The title is the resource name. The page links back to `/compute`. Metrics accept the ranges the API allows: `15m`, `1h`, `6h`, and `24h`.

## Sandboxes tab

The sandboxes tab and **Provision Sandbox** are on this screen. Creating, suspending, and terminating a sandbox is the Sandbox module. The empty text is `No compute sandboxes running currently`. The search placeholder on that tab is `Filter sandboxes`.
