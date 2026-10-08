# Publishing to the Chrome Web Store

## One-time setup

1. Sign in at https://chrome.google.com/webstore/devconsole with the Google
   account that will own the listing.
2. Register as a Chrome Web Store developer: accept the agreement and pay the
   one-time US$5 fee.
3. Under **Account**:
   - verify your contact email
   - set a publisher name
   - enable 2-Step Verification on the Google account (required to publish)

## Upload

1. Run `python3 build.py`.
2. In the dashboard, click **New item** and upload
   `dist/graffiti-neon-street-1.0.0.zip`.
3. Fill in the tabs below, then click **Submit for review**. Themes are usually
   reviewed within a few days.

### Store listing

| Field | Value |
|---|---|
| Description | Copy from below |
| Category | Themes (selected automatically for themes) |
| Language | English |
| Store icon | `store/icon-128.png` |
| Screenshot | `store/screenshot-1280x800.png` (you can add real screenshots too) |
| Small promo tile | `store/promo-small-440x280.png` |
| Marquee promo tile (optional) | `store/promo-marquee-1400x560.png` |
| Homepage / support URL | https://github.com/daniellopez12/graffiti-neon-street |

Description:

```
Graffiti Neon Street is a dark-mode theme built around a neon green and hot-pink
street-art wall.

• Deep-green tabs, toolbar and window frame that flow with the artwork
• WCAG AAA contrast (7:1 or better) for tab titles, toolbar icons, bookmarks and
  the address bar
• The New Tab art fades into a matching background, so it looks right on a
  laptop and on a 4K or ultrawide monitor
• Pure theme: no permissions, no scripts, no data collection

Open source: https://github.com/daniellopez12/graffiti-neon-street
```

### Privacy

- **Single purpose:** "Changes the browser's colours and New Tab background."
- **Permissions:** none.
- **Data usage:** collects no user data. Tick the certification boxes.

### Distribution

- Visibility: **Public**
- Regions: all regions

## Updating

1. Bump `VERSION` in `build.py`.
2. Run `python3 build.py`.
3. In the dashboard, open the item, go to **Package**, click
   **Upload new package**, then **Submit for review**.
