# Bandhan.com — Single-Page Prototype (Batch 1)

This is a **separate, safe test version** — it does NOT touch or replace your
current live 32-page Streamlit app in any way.

## What's inside
- `app.py` — ONE file containing Home, Registration, Search Partner, and My
  Matches, with every field/button/feature identical to the current live
  versions of those 4 pages.
- `requirements.txt` — same dependencies as your main app.

## Why this fixes the flicker
There is **no `pages/` folder here at all**. Navigation between Home,
Registration, Search Partner, and My Matches happens entirely through
`st.session_state` inside this single script — Streamlit never treats it as
loading a "new page", so the sidebar component is never torn down and
rebuilt. That's what causes the flash you were seeing before; removing real
page-navigation removes the flash.

## How to test this SAFELY (separate from your live app)

1. **Create a brand-new GitHub repo** — something like `bandhan-singlepage-test`.
   (Do NOT put this in your existing `bandhan` repo yet — keep it fully separate
   until you've confirmed you like the feel.)
2. Upload to that new repo:
   - `app.py`
   - `requirements.txt`
   - Your logo image (`000001.png` or `896327.jpg` — whichever one you're
     currently using) — copy it from your main repo's root into this new one.
3. Go to Streamlit Community Cloud → **New app** → point it at this new repo
   → Deploy.
4. Log in with `boss@bandhan.com` / `BossAdmin@2026` and click between Home,
   Registration, Search Partner, and My Matches in the sidebar — watch
   closely for the flicker. It should now be gone or dramatically reduced,
   since the sidebar itself is a single component that just sits there while
   only the content next to it swaps.

## What's NOT in this version yet

Only 4 pages are ported so far, exactly as promised — everything else (Chat,
Wedding Services, VIP Membership, Admin Dashboard, and the rest of the 28
pages) shows a temporary "coming in the next batch" placeholder with a
"Back to Home" button, so nothing crashes if you click into them. Once you
confirm the navigation feel is right, the remaining pages get folded into
this same `app.py` in the same batches-of-a-few-pages way.

## If you like it

Once you're happy with how it feels, we can either:
- (a) Keep growing this single `app.py` until all 32 pages are inside it, or
- (b) Replace your existing `bandhan` repo's `app.py` with this one and
  delete the `pages/` folder entirely, once every page has been ported over.

Nothing about your current live app changes until you explicitly decide to
switch over.
