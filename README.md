# Superwhisper Documentation

Public documentation for [Superwhisper](https://superwhisper.com), built with [Mintlify](https://mintlify.com).

### Development

Install the [Mint CLI](https://www.npmjs.com/package/mint) to preview changes locally:

```
npm i -g mint
```

Run the dev server at the root of the repo (where `docs.json` is):

```
mint dev
```

The preview serves at `http://localhost:3000`.

### Google Analytics

Google Analytics 4 is configured site-wide in `docs.json` under
`integrations.ga4`. It uses Superwhisper's measurement ID, `G-MYXWDXVGEM`.
All docs pages inherit this integration, including new pages. No per-page
tracking code is needed.

After deployment, check a direct page load and navigation between docs pages
in GA4 Realtime or Google Tag Assistant. Confirm the page URLs use
`superwhisper.com/docs` and the measurement ID above. Mintlify disables analytics
on preview links; verify collection on the published site. See
[Mintlify's GA4 integration](https://www.mintlify.com/docs/integrations/analytics/google-analytics).
