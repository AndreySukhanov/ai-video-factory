# TODO — follow-ups from QA results

Source: functional testing of the site (2026-05-28). All pages load without
console/network errors; the main pipeline (idea → series → video → stitching) works E2E
on the WaveSpeed Seedance 2.0 integration. Below are the bugs found, optimizations and insights.

## 🔴 Bugs (fix)

- [ ] **Failing jobs `'NoneType' object has no attribute 'id'`** in `/api/v1/jobs/`
      (legacy flow `GENERATE_SCENE_MEDIA`, e.g. scene_id 22). Null-deref — fix
      or remove the dead flow.
- [ ] **Review items reference `replicate.delivery`** — these URLs expire (~24h),
      so previews and publishing break over time. The new episode flow downloads videos to
      `/static/generated/`, but the review/old flow does not. → save review media locally.
- [ ] **Black previews on some trend cards** (Instagram) — likely a failure of
      `/api/v1/proxy/image`. → check the image proxy fallback.

## 🟡 Optimizations

- [ ] **Certbot renewal without nginx reload** on prod — the certificate will renew, but
      the nginx container won't pick up the new one. → deploy-hook `docker compose exec nginx nginx -s reload`.
- [ ] **Refine the WaveSpeed cost estimate**: currently hardcoded at `$0.54`, actually $0.5 (fast)
      / $0.6 (standard), depends on resolution. → compute by res/duration; for cheap
      tests default to fast + 480p.
- [ ] **uvicorn `--reload` on a Windows bind-mount** catches spurious reloads and kills
      long generations (caught during testing). Does not affect prod. →
      `--reload-exclude static,uploads` or run long tasks without reload.
- [ ] **`/api/v1/episodes/status`** always returns `replicate_minimax` regardless of
      the selected model — misleading; tie it to the actual selection.

## 🟢 Insights / opportunities

- [ ] **WaveSpeed = 996 models / 36 Seedance variants under a single key.** Cheaper
      tiers are available — **Seedance v1.5-pro ($0.2)** and turbo, as well as native **`video-extend`**
      and **`reference-to-video`** — potentially replacing the custom frame-chaining extender.
- [ ] **WaveSpeed balance is finite** — add a low-balance display/alert to the dashboard
      next to the YT quota (`GET /api/v3/balance`).
- [ ] **Two "Seedance 2.0"s**: LaoZhang $0.05 vs WaveSpeed $0.5+ (10× difference). During testing
      LaoZhang was returning 503 — which justifies WaveSpeed as a reliable backup. Document
      "when to use which" in the docs.
- [ ] **The `enable_web_search` parameter** of Seedance 2.0 is unused — could improve
      topical relevance.

## ⚪ Not tested (requires spending/state)

YouTube upload (no connected channel), trend fetching (quotas), delete/approve/publish/
reject/regenerate in review, creating scheduler tasks, video-extend, the "Test
notification" button (sends a real alert).
