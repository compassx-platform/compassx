# Entry point

`GET /api/um/entry-point` takes an optional `deep_link_workspace_id` query. It requires a signed-in user. The handler calls `resolve_entry_point` and returns `workspace_id`, `section`, and `route`.

The result is cached in process for 60 seconds under `{user_id}:{deep_link}`. `invalidate_entry_point_cache(user_id)` drops that user's keys. Calling it with no user clears the cache. Membership changes from the account and member routes call it.

## Which workspace

Memberships are direct user assignments plus assignments to the user's groups, including parent groups. For one workspace the higher `WORKSPACE_ROLE_RANK` wins. An account admin also receives every active workspace in the account, or every active workspace when that list is empty, with role `workspace_admin`.

A deep link matches a workspace id or slug the user can access. That match wins. Otherwise the user's direct assignment with `is_default` true is used when that workspace is still in the membership list. Otherwise a user with exactly one membership lands there.

A user with more than one membership and no default returns `{ workspace_id: null, section: "picker", route: "/workspace-picker" }`. An account admin with no memberships returns `{ section: "create_workspace", route: "/workspace/create" }`. Anyone else with no memberships returns `{ section: "none", route: "/no-workspace-access" }`.

## Which route

Inside a workspace, a workspace-scoped landing rule for that role is preferred, then a global rule, highest `priority` first. The fallback is `/platform/notebooks`.

A route of `/business-center` or `/business_center` becomes `/platform/dashboards`. A trailing slash is removed. A route without a leading slash gets one.

The response route is `/w/{slug}{suffix}`. `workspace_id` is the workspace row id. `section` is `app`. Seeded global rules send `workspace_admin` and `analyst` to `/platform/notebooks`, and `business_viewer` to `/platform/dashboards`, each at priority 10. Existing global rules are left in place. Legacy business-center targets on any landing rule are rewritten to `/platform/dashboards`.
