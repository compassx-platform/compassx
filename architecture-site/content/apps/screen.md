# Screen

The list route is `apps`. The heading is **Apps**. The button is **Add app**. Search placeholder is `Search apps by name, repo, or branch...`. The count reads `{n} app` or `{n} apps`. While the list loads, the text is `Loading workspace applications...`.

An empty workspace says **No apps yet** and `Connect a Git repository to deploy interactive Streamlit applications, custom web apps, or agentic dashboards.` The empty button is also **Add app**.

## Add

The dialog title is **Add New App**, then **Configure Git repository**. The first step says `Provide application name and general runtime settings.` The second says `Optionally configure a Git repository for your app. You can deploy from this repository later.`

Creating an app shows `App "{name}" created and registered in system DB.` A failure shows the server detail or `Failed to create app.` Deleting shows `Deleted "{name}".` A failure shows the server detail or `Failed to delete app.`

## Open

An app opens at `apps/{applicationId}`. The build studio is `apps/{applicationId}/build`. The detail page can delete the app. The build studio is where files, the dev terminal, the preview, and the Omnigent chat run. Those calls use the dev routes on that app id.
