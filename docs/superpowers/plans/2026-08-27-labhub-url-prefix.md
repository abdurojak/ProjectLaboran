# LabHub Production URL Prefix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every browser-facing Django URL use `/labhub/` in production while preserving root deployment during local development.

**Architecture:** Keep `FORCE_SCRIPT_NAME` as Django's URL-prefix source and derive browser WebSocket paths from `{% url 'dashboard:home' %}`. Scope session and CSRF cookies to the configured script prefix, and compare realtime refresh paths after removing the public prefix from the current pathname.

**Tech Stack:** Django 5.2, Django templates, Channels/Daphne, JavaScript, Django test framework

---

## File Map

- Modify `project_laboran/settings.py`: derive cookie paths from `URL_PREFIX`.
- Modify `project_laboran/test_deployment.py`: cover prefixed redirect and cookie paths.
- Modify `apps/kalender/templates/kalender/realtime_client.html`: prefix notification WebSocket URLs and normalize refresh path matching.
- Modify `apps/kalender/tests.py`: verify prefixed realtime client output.
- Modify `apps/core/templates/core/bantuan.html`: prefix user help WebSocket URLs.
- Modify `apps/core/templates/core/bantuan_admin.html`: prefix administrator help WebSocket URLs.
- Modify `apps/core/tests.py`: verify both help pages emit prefixed WebSocket paths.

### Task 1: Prefix Django Runtime URLs And Cookies

**Files:**
- Modify: `project_laboran/settings.py`
- Test: `project_laboran/test_deployment.py`

- [ ] **Step 1: Write failing deployment tests**

Add a test using `override_script_prefix('/labhub/')` which asserts that the anonymous dashboard redirect is `/labhub/pengguna/login/?next=/labhub/`. Load settings in a subprocess with `FORCE_SCRIPT_NAME=/labhub` and assert `STATIC_URL`, `MEDIA_URL`, `SESSION_COOKIE_PATH`, and `CSRF_COOKIE_PATH` begin with `/labhub/`.

```python
@override_script_prefix('/labhub/')
def test_prefixed_dashboard_redirects_to_prefixed_login(self):
    response = self.client.get('/')
    self.assertEqual(
        response.headers['Location'],
        '/labhub/pengguna/login/?next=/labhub/',
    )
```

- [ ] **Step 2: Run tests and verify cookie assertions fail**

Run: `python manage.py test project_laboran.test_deployment -v 2`

Expected: URL assertions pass; cookie assertions fail because cookie paths default to `/`.

- [ ] **Step 3: Derive cookie paths from the script prefix**

```python
APPLICATION_COOKIE_PATH = f'{URL_PREFIX}/' if URL_PREFIX else '/'
SESSION_COOKIE_PATH = APPLICATION_COOKIE_PATH
CSRF_COOKIE_PATH = APPLICATION_COOKIE_PATH
```

- [ ] **Step 4: Run deployment tests**

Run: `python manage.py test project_laboran.test_deployment -v 2`

Expected: all deployment tests pass.

- [ ] **Step 5: Commit runtime changes**

```powershell
git add project_laboran/settings.py project_laboran/test_deployment.py
git commit -m "fix: scope production URLs to LabHub prefix"
```

### Task 2: Prefix Notification Realtime URLs

**Files:**
- Modify: `apps/kalender/templates/kalender/realtime_client.html`
- Test: `apps/kalender/tests.py`

- [ ] **Step 1: Write a failing prefixed-template test**

Render an authenticated page inside `override_script_prefix('/labhub/')` and assert its realtime script contains an `appPath` of `/labhub` and a notification socket under `/labhub/ws/notifikasi/`. Also assert refresh matching removes `appPath` from the current pathname.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python manage.py test apps.kalender.tests.KalenderViewTests.test_realtime_urls_follow_script_prefix -v 2`

Expected: fail because the current socket URL is rooted at `/ws/notifikasi/`.

- [ ] **Step 3: Derive the application path from Django URL reversing**

```javascript
const appPath = "{% url 'dashboard:home' %}".replace(/\/$/, '');
const socketUrl = protocol + '//' + window.location.host + appPath + '/ws/notifikasi/';
```

Normalize the path used by realtime refresh matching:

```javascript
const currentPath = appPath && window.location.pathname.startsWith(appPath)
    ? window.location.pathname.slice(appPath.length) || '/'
    : window.location.pathname;
```

- [ ] **Step 4: Run Kalender tests**

Run: `python manage.py test apps.kalender.tests -v 1`

Expected: all Kalender tests pass.

- [ ] **Step 5: Commit notification changes**

```powershell
git add apps/kalender/templates/kalender/realtime_client.html apps/kalender/tests.py
git commit -m "fix: prefix notification websocket URLs"
```

### Task 3: Prefix Help Chat WebSocket URLs

**Files:**
- Modify: `apps/core/templates/core/bantuan.html`
- Modify: `apps/core/templates/core/bantuan_admin.html`
- Test: `apps/core/tests.py`

- [ ] **Step 1: Write failing template tests**

For both help pages rendered under `override_script_prefix('/labhub/')`, assert the WebSocket constructor includes `/labhub/ws/bantuan/<id>/` and does not use a root-only `/ws/bantuan/` expression.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python manage.py test apps.core.tests.BantuanWebSocketTests -v 2`

Expected: prefixed-template assertions fail against the hard-coded paths.

- [ ] **Step 3: Prefix both WebSocket constructors**

```javascript
const appPath = "{% url 'dashboard:home' %}".replace(/\/$/, '');
const chatSocket = new WebSocket(
    socketProtocol + window.location.host + appPath + '/ws/bantuan/{{ percakapan.pk }}/'
);
```

- [ ] **Step 4: Run Core WebSocket tests**

Run: `python manage.py test apps.core.tests.BantuanWebSocketTests -v 2`

Expected: all help WebSocket tests pass.

- [ ] **Step 5: Commit help changes**

```powershell
git add apps/core/templates/core/bantuan.html apps/core/templates/core/bantuan_admin.html apps/core/tests.py
git commit -m "fix: prefix help websocket URLs"
```

### Task 4: Verify Production Prefix Behavior

**Files:**
- No additional source files

- [ ] **Step 1: Run focused regression suites**

Run: `python manage.py test project_laboran.test_deployment apps.kalender.tests apps.core.tests -v 1`

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 2: Run Django checks with production URL settings**

```powershell
$env:FORCE_SCRIPT_NAME='/labhub'
$env:PUBLIC_ACCESS_BASE_URL='https://lab1.trisakti.ac.id/labhub'
python manage.py check
Remove-Item Env:FORCE_SCRIPT_NAME
Remove-Item Env:PUBLIC_ACCESS_BASE_URL
```

Expected: `System check identified no issues`.

- [ ] **Step 3: Audit hard-coded root URLs**

```powershell
rg -n -P --glob '*.html' --glob '*.js' 'host \+ ["'']/ws/|(href|action|src)=["'']/(?!/)' apps
```

Expected: no application runtime URL requiring `/labhub` remains.

- [ ] **Step 4: Review the final diff**

Run: `git diff --check; git status --short`

Expected: no whitespace errors; only the unrelated pre-existing `exports/` directory may remain untracked.
