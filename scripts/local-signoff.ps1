param(
    [string]$RecruiterEmail = "recruiter@example.com",
    [string]$OutputDirectory = "$env:TEMP/jobtalk-local-signoff",
    [switch]$TemplatesOnly,
    [switch]$RecruiterDraftOnly,
    [switch]$AdminOnly,
    [switch]$VacancyOnly
)

$ErrorActionPreference = "Stop"
$edgePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
$debugPort = 9341
$profilePath = "$env:TEMP/jobtalk-local-signoff-profile-$PID"
$script:socket = $null
$script:messageId = 0

function Invoke-Cdp([string]$method, [hashtable]$params = @{}) {
    $script:messageId += 1
    $requestId = $script:messageId
    $payload = @{ id = $requestId; method = $method; params = $params } | ConvertTo-Json -Depth 20 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $segment = [ArraySegment[byte]]::new($bytes)
    $script:socket.SendAsync($segment, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult()

    while ($true) {
        $stream = [IO.MemoryStream]::new()
        do {
            $buffer = New-Object byte[] 65536
            $receiveSegment = [ArraySegment[byte]]::new($buffer)
            $received = $script:socket.ReceiveAsync($receiveSegment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
            $stream.Write($buffer, 0, $received.Count)
        } while (-not $received.EndOfMessage)
        $response = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
        if ($response.id -eq $requestId) {
            if ($response.error) { throw "CDP $method failed: $($response.error.message)" }
            return $response.result
        }
    }
}

function Invoke-JavaScript([string]$expression) {
    $result = Invoke-Cdp "Runtime.evaluate" @{
        expression = $expression
        awaitPromise = $true
        returnByValue = $true
    }
    if ($result.exceptionDetails) {
        $detail = $result.exceptionDetails.exception.description
        if (-not $detail) { $detail = $result.exceptionDetails.text }
        throw "Browser JavaScript failed: $detail"
    }
    return $result.result.value
}

function Wait-JavaScript([string]$expression, [string]$description, [int]$seconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Invoke-JavaScript $expression) { return }
        Start-Sleep -Milliseconds 300
    }
    throw "Timed out waiting for $description"
}

function Save-Screenshot([string]$name) {
    $capture = Invoke-Cdp "Page.captureScreenshot" @{ format = "png"; fromSurface = $true }
    [IO.File]::WriteAllBytes((Join-Path $OutputDirectory $name), [Convert]::FromBase64String($capture.data))
}

function Set-Viewport([int]$width, [int]$height, [bool]$mobile) {
    Invoke-Cdp "Emulation.setDeviceMetricsOverride" @{
        width = $width
        height = $height
        deviceScaleFactor = 1
        mobile = $mobile
    } | Out-Null
}

function Set-InputAndSubmit([string]$selector, [string]$value) {
    $selectorJson = $selector | ConvertTo-Json -Compress
    $valueJson = $value | ConvertTo-Json -Compress
    $expression = @"
(() => {
  const input = document.querySelector($selectorJson);
  const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, $valueJson);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.form.requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $expression | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$edge = Start-Process -FilePath $edgePath -WindowStyle Hidden -PassThru -ArgumentList @(
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--remote-debugging-port=$debugPort",
    "--remote-allow-origins=*",
    "--user-data-dir=$profilePath",
    "about:blank"
)

try {
    $target = $null
    for ($attempt = 0; $attempt -lt 30 -and -not $target; $attempt++) {
        try {
            $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$debugPort/json" -TimeoutSec 2
            $target = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
        } catch {}
        if (-not $target) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $target) { throw "Edge debugging endpoint did not start" }

    $script:socket = [Net.WebSockets.ClientWebSocket]::new()
    $script:socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult() | Out-Null
    Invoke-Cdp "Page.enable" | Out-Null
    Invoke-Cdp "Runtime.enable" | Out-Null

    Set-Viewport 1200 800 $false
    Invoke-Cdp "Page.navigate" @{ url = "http://localhost:3000/" } | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" "entry screen"
    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(button => button.textContent.includes('hiring')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#email') !== null" "recruiter email form"
    $mailBefore = (Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/v1/messages" -TimeoutSec 5).total
    Set-InputAndSubmit "#email" $RecruiterEmail
    Wait-JavaScript "document.querySelector('#code') !== null" "recruiter code form"

    $code = $null
    $mailDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $mailDeadline -and -not $code) {
        $mail = Invoke-RestMethod -Uri "http://127.0.0.1:8025/api/v1/messages" -TimeoutSec 5
        if ($mail.total -gt $mailBefore) {
            $message = $mail.messages |
                Where-Object { $_.Subject -eq "Your Job Talk sign-in code" -and $_.To[0].Address -eq $RecruiterEmail } |
                Sort-Object Created -Descending |
                Select-Object -First 1
            if ($message.Snippet -match "\b(\d{6})\b") { $code = $Matches[1] }
        }
        if (-not $code) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $code) { throw "Recruiter sign-in code was not delivered" }
    Set-InputAndSubmit "#code" $code
    Wait-JavaScript "document.querySelector('.new-chat') !== null" "recruiter workspace"

    if ($AdminOnly) {
        Wait-JavaScript "document.querySelector('#admin-job') !== null" "owner all-jobs view"
        $adminCheckToken = $null
        try {
            $jobId = Invoke-JavaScript @'
(async () => {
  const base = 'http://localhost:8000/api';
  const jobs = await fetch(base + '/public/jobs').then(r => r.json());
  if (!jobs.length) throw new Error('This check needs a published local job');
  const guest = await fetch(base + '/auth/guest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: jobs[0].id }) }).then(r => r.json());
  window.__adminCheckGuest = guest.access_token;
  const headers = { Authorization: 'Bearer ' + guest.access_token, 'Content-Type': 'application/json' };
  const chats = await fetch(base + '/chats', { headers }).then(r => r.json());
  const submitted = await fetch(base + '/jobs/' + jobs[0].id + '/apply', { method: 'POST', headers, body: JSON.stringify({ candidate_chat_id: chats[0].id, candidate_name: 'Owner View Check', candidate_location: 'Cape Town', preferred_contact: 'owner-check@example.com', consent_to_share: true }) });
  if (!submitted.ok) throw new Error('Could not submit fictional application');
  return jobs[0].id;
})()
'@
            $adminCheckToken = Invoke-JavaScript "window.__adminCheckGuest"
            Invoke-JavaScript "[...document.querySelectorAll('.chat-header button')].find(button => button.textContent === 'Refresh').click(); true" | Out-Null
            Wait-JavaScript "document.querySelector('#admin-job') !== null" "refreshed owner job list"
            Invoke-JavaScript "(() => { const select = document.querySelector('#admin-job'); select.value = '$jobId'; select.dispatchEvent(new Event('change', { bubbles: true })); return true; })()" | Out-Null
            Wait-JavaScript "document.querySelector('.candidate-comparison')?.textContent.includes('Owner View Check')" "submitted snapshot from another recruiter's job"
            if (Invoke-JavaScript "document.querySelector('.close-job, .composer, .publish-bar') !== null") { throw "Owner view exposed job mutation controls" }
            Save-Screenshot "admin-jobs-desktop.png"
            Set-Viewport 390 760 $true
            Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed phone sidebar"
            if (Invoke-JavaScript "document.documentElement.scrollWidth > window.innerWidth") { throw "Admin view overflows the phone viewport" }
            Save-Screenshot "admin-jobs-phone.png"
            Invoke-JavaScript 'document.querySelector("[aria-label=''Open conversation menu'']").click(); true' | Out-Null
            Wait-JavaScript "document.querySelector('.sidebar.open') !== null" "phone owner navigation"
            Invoke-JavaScript "document.querySelector('.admin-nav').click(); true" | Out-Null
            Wait-JavaScript "document.querySelector('.sidebar.open') === null" "closed owner navigation"
            Invoke-JavaScript "window.__jobTalkReloadPending = true; true" | Out-Null
            Invoke-Cdp "Page.reload" | Out-Null
            Wait-JavaScript "!window.__jobTalkReloadPending && document.querySelector('#admin-job') !== null" "owner access after refresh"
            if (Invoke-JavaScript "document.querySelector('.error-notice, .admin-jobs .error') !== null") { throw "Owner view displayed an error" }
            Write-Output "Admin browser check passed: email-code login, all jobs, another recruiter's submitted snapshot, read-only comparison, refresh and phone navigation. No LLM calls made."
            Write-Output "Screenshots: $OutputDirectory"
        } finally {
            # Keep this temporary token in PowerShell across Page.reload; the
            # application's own browser session remains the owner session.
            if (-not $adminCheckToken) { $adminCheckToken = Invoke-JavaScript "window.__adminCheckGuest" }
            if ($adminCheckToken) {
                Invoke-RestMethod -Method Delete -Uri "http://localhost:8000/api/account" -Headers @{ Authorization = "Bearer $adminCheckToken" } | Out-Null
            }
        }
        return
    }

    if ($VacancyOnly) {
        . "$PSScriptRoot/manual-vacancy-check.ps1"
        return
    }

    $chatCount = Invoke-JavaScript "document.querySelectorAll('.chat-row').length"
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelectorAll('.template-choice').length === 3" "three starter templates"
    Save-Screenshot "00-templates-desktop.png"
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed template picker phone sidebar"
    Save-Screenshot "00-templates-phone.png"
    Set-Viewport 1200 800 $false
    Invoke-JavaScript "[...document.querySelectorAll('.template-choice')].find(button => button.dataset.templateId === 'generic-role').click(); true" | Out-Null
    Wait-JavaScript "document.querySelectorAll('.chat-row').length > $chatCount && document.querySelectorAll('.message-wrap.user').length === 0" "new hiring conversation"
    Wait-JavaScript "document.querySelector('.template-draft')?.textContent.includes('Unanswered')" "unconfirmed template fields"
    if (Invoke-JavaScript "document.querySelector('.publish-bar') !== null") { throw "Template suggestions made the empty role publishable" }
    Invoke-JavaScript "window.__jobTalkReloadPending = true; true" | Out-Null
    Invoke-Cdp "Page.reload" | Out-Null
    Wait-JavaScript "!window.__jobTalkReloadPending && document.querySelector('.template-draft')?.textContent.includes('Unanswered')" "saved template after reload"
    if ($TemplatesOnly) {
        foreach ($templateId in @('junior-software-developer', 'plumber')) {
            Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
            Wait-JavaScript "document.querySelectorAll('.template-choice').length === 3" "template picker"
            Invoke-JavaScript "[...document.querySelectorAll('.template-choice')].find(button => button.dataset.templateId === '$templateId').click(); true" | Out-Null
            Wait-JavaScript "document.querySelector('.template-draft') !== null" "new template draft"
            Invoke-JavaScript "window.__jobTalkReloadPending = true; true" | Out-Null
            Invoke-Cdp "Page.reload" | Out-Null
            Wait-JavaScript "!window.__jobTalkReloadPending && document.querySelector('.template-draft') !== null" "restored template draft"
            if (Invoke-JavaScript "[...document.querySelectorAll('.template-draft li')].some(field => field.dataset.fieldState !== 'unanswered')") { throw "Template silently confirmed a field" }
            if (Invoke-JavaScript "document.querySelector('.publish-bar') !== null") { throw "Template draft became publishable without answers" }
            Invoke-JavaScript "document.querySelector('.template-draft').scrollIntoView({ block: 'start', behavior: 'instant' }); true" | Out-Null
            Save-Screenshot "00-$templateId-desktop.png"
            Set-Viewport 390 760 $true
            Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed template draft phone sidebar"
            Invoke-JavaScript "document.querySelector('.template-draft').scrollIntoView({ block: 'start', behavior: 'instant' }); true" | Out-Null
            Save-Screenshot "00-$templateId-phone.png"
            Set-Viewport 1200 800 $false
        }
        Write-Output "Template browser check passed: three separate drafts, unconfirmed suggestions, and refresh persistence on desktop and phone. No LLM messages sent."
        Write-Output "Screenshots: $OutputDirectory"
        return
    }
    $roleText = "Job title: Browser Signoff Welder; Role description: The person will repair workshop gates and frames; Skills: Welding is required; Tools: Welding equipment is required; Experience: two years of welding experience; Work arrangement: on-site; Location: Cape Town; Working hours: weekdays; Start availability: immediately; No degree needed"
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $roleText
    Wait-JavaScript "document.querySelector('.publish-bar') !== null" "publish-ready role" 45
    if (Invoke-JavaScript "document.querySelector('.error-notice') !== null") { throw "Role creation displayed an error" }
    Save-Screenshot "01-role-ready-desktop.png"
    if ($RecruiterDraftOnly) {
        Set-InputAndSubmit "textarea[aria-label='Conversation message']" "Experience: three years of welding experience"
        Wait-JavaScript "document.querySelector('[data-field-key=experience]')?.textContent.includes('3 years') && !document.querySelector('.typing')" "corrected experience"
        Set-InputAndSubmit "textarea[aria-label='Conversation message']" "That's fine"
        Wait-JavaScript "[...document.querySelectorAll('.message-wrap.user')].at(-1)?.textContent.includes('fine') && !document.querySelector('.typing')" "ambiguous acknowledgement"
        if (-not (Invoke-JavaScript "document.querySelector('[data-field-key=experience]')?.textContent.includes('3 years') && document.querySelector('[data-field-key=education]')?.dataset.fieldState === 'not_required'")) { throw "Draft changed after an ambiguous reply" }
        Invoke-JavaScript "window.__jobTalkReloadPending = true; true" | Out-Null
        Invoke-Cdp "Page.reload" | Out-Null
        Wait-JavaScript "!window.__jobTalkReloadPending && document.querySelector('[data-field-key=experience]')?.textContent.includes('3 years')" "persisted corrected summary"
        Save-Screenshot "01-role-corrected-desktop.png"
    }
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed recruiter phone sidebar" 10
    Invoke-JavaScript "document.querySelector('.template-draft').scrollIntoView({ block: 'start', behavior: 'instant' }); true" | Out-Null
    Save-Screenshot "02-role-ready-phone.png"
    Set-Viewport 1200 800 $false

    $jobId = Invoke-JavaScript @'
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = { Authorization: 'Bearer ' + session.access_token };
  const chats = await fetch('http://localhost:8000/api/chats', { headers }).then(response => response.json());
  const details = await Promise.all(chats.map(chat => fetch('http://localhost:8000/api/chats/' + chat.id, { headers }).then(response => response.json())));
  return details.find(chat => chat.job_post?.title === 'Browser Signoff Welder')?.job_post?.id || 0;
})()
'@
    if (-not $jobId) { throw "Created recruiter job was not found" }
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.status-pill').textContent.includes('Published')" "published role"
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('criteria locked')" "locked published criteria"
    if (Invoke-JavaScript "document.querySelector('.composer') !== null") { throw "Published recruiter chat still offers criteria editing" }
    if ($RecruiterDraftOnly) {
        Write-Output "Recruiter draft browser check passed: captured fields, correction, explicit exclusion, refresh, phone summary, Publish, and published lock. Provider quality is verified separately."
        Write-Output "Screenshots: $OutputDirectory"
        return
    }
    $recruiterSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"

    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/?job=$jobId'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-job')?.textContent.includes('Browser Signoff Welder')" "new public job"
    Save-Screenshot "03-public-job-desktop.png"
    Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "candidate conversation"
    $candidateText = "I have three years of welding experience in Cape Town. I repaired workshop gates and frames using welding equipment. I am available immediately for on-site work and weekday hours."
    Invoke-JavaScript "window.__jobTalkFetch = window.fetch; window.fetch = (...args) => { window.fetch = window.__jobTalkFetch; return Promise.reject(new TypeError('Simulated temporary send failure')); }; true" | Out-Null
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $candidateText
    Wait-JavaScript "document.querySelector('.error-notice') !== null" "recoverable send error"
    $preservedMessage = Invoke-JavaScript "document.querySelector(``textarea[aria-label='Conversation message']``).value"
    if ($preservedMessage -ne $candidateText) { throw "Failed send discarded the candidate message" }
    Invoke-JavaScript "document.querySelector('.error-dismiss').click(); true" | Out-Null
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" $candidateText
    Wait-JavaScript "document.querySelector('.application-summary')?.textContent.includes('welding') && document.querySelector('.job-card .score strong')?.textContent !== '0%' && !document.querySelector('.typing')" "captured candidate evidence" 45
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" "Actually I have two years of welding experience"
    Wait-JavaScript "document.querySelector('.application-summary [data-field-key=experience]')?.textContent.includes('2 years') && !document.querySelector('.typing')" "corrected candidate duration" 45
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" "I cannot use welding equipment"
    Wait-JavaScript "document.querySelector('.application-summary [data-field-key=tools]')?.dataset.fieldState === 'gap' && !document.querySelector('.typing')" "reported tools gap" 45
    if (-not (Invoke-JavaScript "document.querySelector('.application-summary [data-field-key=experience]')?.dataset.fieldState === 'captured' && document.querySelector('.application-summary [data-field-key=experience]')?.textContent.includes('2 years')")) { throw "A tool gap incorrectly overwrote the experience answer" }
    Save-Screenshot "03-application-summary-desktop.png"
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed candidate summary phone sidebar"
    Invoke-JavaScript "document.querySelector('.application-summary').scrollIntoView({ block: 'start', behavior: 'instant' }); true" | Out-Null
    Save-Screenshot "03-application-summary-phone.png"
    Set-Viewport 1200 800 $false
    Invoke-JavaScript "document.querySelector('.job-card button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#candidate-name') !== null" "application review"
    $candidateForm = @"
(async () => {
  const setValue = async (selector, value) => {
    const input = document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
  };
  await setValue('#candidate-name', 'Local Signoff Candidate');
  if (document.querySelector('#candidate-location').value !== 'Cape Town') throw new Error('Candidate location was not extracted into review');
  await setValue('#candidate-contact', 'local-signoff@example.test');
  document.querySelector('.consent-check input').click();
  document.querySelector('.application-review').requestSubmit();
  return true;
})()
"@
    Invoke-JavaScript $candidateForm | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "submitted application"
    $candidateSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
    Save-Screenshot "04-candidate-submitted-desktop.png"
    Set-Viewport 390 760 $true
    Invoke-Cdp "Page.reload" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "candidate phone submission"
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed candidate phone sidebar" 10
    Save-Screenshot "05-candidate-submitted-phone.png"

    $recruiterSessionJson = $recruiterSession | ConvertTo-Json -Compress
    Set-Viewport 1200 800 $false
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session', $recruiterSessionJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.chat-shell') !== null" "restored recruiter workspace"
    $jobChatIndex = Invoke-JavaScript @"
(async () => {
  const session = JSON.parse(sessionStorage.getItem('job-talk-session'));
  const headers = { Authorization: 'Bearer ' + session.access_token };
  const chats = await fetch('http://localhost:8000/api/chats', { headers }).then(response => response.json());
  const details = await Promise.all(chats.map(chat => fetch('http://localhost:8000/api/chats/' + chat.id, { headers }).then(response => response.json())));
  return details.findIndex(chat => chat.job_post?.id === $jobId);
})()
"@
    if ($jobChatIndex -lt 0) { throw "Created recruiter chat was not found" }
    Invoke-JavaScript "document.querySelectorAll('.chat-row')[$jobChatIndex].click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.candidate-card') !== null" "candidate comparison"
    Save-Screenshot "06-recruiter-comparison-desktop.png"
    Set-Viewport 390 760 $true
    Wait-JavaScript "document.querySelector('.candidate-card') !== null" "phone candidate comparison"
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed recruiter phone sidebar" 10
    Save-Screenshot "07-recruiter-comparison-phone.png"
    Invoke-JavaScript "window.confirm = () => true; document.querySelector('.close-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('Recruitment closed')" "closed recruitment"
    if (Invoke-JavaScript "document.querySelector('.publish-bar') !== null") { throw "Closed recruitment still offers publication" }
    Save-Screenshot "08-recruitment-closed-phone.png"
    $closedStatus = Invoke-JavaScript "fetch('http://localhost:8000/api/public/jobs/$jobId').then(response => response.status)"
    if ($closedStatus -ne 404) { throw "Closed job is still publicly available" }

    $candidateSessionJson = $candidateSession | ConvertTo-Json -Compress
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session', $candidateSessionJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar') !== null" "restored candidate submission"
    Invoke-JavaScript "window.confirm = () => true; [...document.querySelectorAll('.submitted-bar button')].find(button => button.textContent.includes('Delete')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-choice') !== null" "candidate data deletion"
    Save-Screenshot "09-candidate-deleted-phone.png"
    $candidateToken = (ConvertFrom-Json $candidateSession).access_token
    $candidateTokenJson = $candidateToken | ConvertTo-Json -Compress
    $deletedStatus = Invoke-JavaScript "fetch('http://localhost:8000/api/auth/me', { headers: { Authorization: 'Bearer ' + $candidateTokenJson } }).then(response => response.status)"
    if ($deletedStatus -ne 401) { throw "Deleted candidate session is still valid" }

    Invoke-JavaScript "[...document.querySelectorAll('.entry-choice')].find(button => button.textContent.includes('looking for work')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelectorAll('.entry-job').length === 2" "two available entry jobs"
    if (-not (Invoke-JavaScript "document.querySelector('.login-card h2')?.textContent === 'Available jobs'")) { throw "Entry cards were not labelled available jobs" }
    Invoke-JavaScript "[...document.querySelectorAll('button')].find(button => button.textContent.includes('Find a different job')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.discovery-empty') !== null" "fresh discovery chat"
    Set-InputAndSubmit "textarea[aria-label='Conversation message']" "I have three years of welding and forklift experience in Cape Town. I repaired gates and operated a forklift in a workshop."
    Wait-JavaScript "document.querySelector('.job-card button')?.textContent.includes('Apply to this job') && !document.querySelector('.typing')" "real job suggestions" 45
    Invoke-JavaScript "document.querySelector('.job-card button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.application-summary') !== null && document.querySelector('.job-card button')?.textContent.includes('Review application')" "selected job with carried answers"
    Set-Viewport 1200 800 $false
    Save-Screenshot "10-discovery-selected-desktop.png"

    Write-Output "Local check passed: create/publish, preserve failed send, candidate summary/correction/gap, consent/submit, compare, close/delete, and discover/select a real job. Desktop and phone screenshots captured; actual LLM quality is verified separately."
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if ($script:socket) { $script:socket.Dispose() }
    if ($edge -and -not $edge.HasExited) { Stop-Process -Id $edge.Id -Force }
}
