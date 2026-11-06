# Test cases

Run these in a workspace you can administer, with at least one app and one dashboard already created. Sign in as a workspace admin so **Customize Sidebar** is visible. Repeat the last case as a member who is not an admin or a developer.

## First open

Open **Portal** at `/w/{workspace}/portal/home` or the Portal switcher entry.

The page title should be `Portal` on home, and `Workspace Portal` after a portal path. The sidebar should show an **Applications** section and a **Dashboards** section when those exist. The first visible app or dashboard should open in the page. The address should become `/portal/app/{id}` or `/portal/dashboard/{id}`.

## Empty workspace

Use a workspace with no apps and no dashboards, and delete any saved portal layout for it so the next read bootstraps.

You should see the heading **Welcome to Workspace Portal** and the sentence `This is your centralized hub for business applications and dashboards. No items have been published to the sidebar navigation yet.` The sidebar should say `No items pinned to sidebar.` The saved layout should be one empty section titled `Applications`.

## Customize the sidebar

Choose **Customize Sidebar**. The dialog heading should be **Customize Portal Sidebar**.

Add a category. Its title should start as `New Category`. Rename it to `Operations`. Move it above the other categories. Add the existing app and the existing dashboard into `Operations`. Hide the dashboard with the eye control. Add an external link titled `Documentation Hub` with URL `https://example.com`. Choose **Save Changes**.

You should see `Portal sidebar layout saved.` After the drawer closes, the sidebar should show `Operations` first, the app visible, the dashboard absent, and `Documentation Hub` opening `https://example.com` in a new tab.

Open **Customize Sidebar** again and choose **Add Link** with the title or the URL left blank. You should see `Title and URL are required`, and the category should not gain an item. Choose **Cancel**. The saved layout should be unchanged.

## Open an app and a dashboard

Select a visible app that is stopped or inactive. You should see `{name} is currently offline` and **Start Application**. Start it. You should see `Starting {name}...`, then the app frame. The frame address should be the runtime URL, or `/api/v1/apps/{id}/proxy/` when the runtime URL is empty.

Select a dashboard. The dashboard should render without the editor chrome.

Open an app id that does not exist. You should see **Application Not Found** and `The requested application could not be loaded. It may have been deleted or moved.` **Retry** should ask for the app again.

## Another role

Sign in as a member who is not an account admin, workspace admin, or workspace developer.

The app switcher should offer only Portal. **Customize Sidebar** should be absent from the sidebar and from the empty portal page. The visible apps and dashboards from the saved layout should still open.
