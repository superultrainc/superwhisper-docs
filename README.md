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

### Images

Every image under `images/` must be sized and compressed to the repo standard
(max 2048 px wide, 3200 px tall; PNGs through pngquant + oxipng). A CI check
runs on every pull request and fails if an added or changed image is not compliant.

Before committing an image:

```
brew install pngquant oxipng gifsicle && pip3 install pillow   # once
python3 scripts/optimize-images.py --frame ~/Desktop/capture.png images/screens/mac/new-screen.png   # bare capture -> framed, sized, compressed
python3 scripts/optimize-images.py images/screens/mac/new-screen.png                                # already framed -> sized, compressed
python3 scripts/optimize-images.py --check
```

`--frame` also saves the bare capture under `captures/` at the same path, so a
screen can be re-framed later. Commit both. Highlights, numbered badges, arrows,
and blurs come from a JSON spec beside the capture; see the skill for the format.

Details, folder layout, and naming rules: [`skills/docs-images/SKILL.md`](skills/docs-images/SKILL.md).

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
