# Run through local-signoff.ps1 -VacancyOnly with the configured local owner.
# Uses that script's authenticated browser and CDP helpers. All data is fictional.
$ownerSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
$ownerHeaders = @{ Authorization = 'Bearer ' + ($ownerSession | ConvertFrom-Json).access_token }
$vacancyGuestHeaders = $null
$vacancyJobId = $null
$stamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$sourceUrl = "https://example.com/jobtalk-check/$stamp"
$sourceText = "Job title: Curated Check Welder; Role description: Repair workshop gates and frames; Skills: Welding is required; Tools: Welding equipment is required; Experience: two years of welding experience; Work arrangement: on-site; Location: Cape Town; Working hours: weekdays; Start availability: immediately; No degree needed"

try {
    Wait-JavaScript "document.querySelector('.admin-nav') !== null" "approved owner navigation"
    Invoke-JavaScript "document.querySelector('.new-chat').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#curated-vacancy') !== null" "owner vacancy option"
    Invoke-JavaScript "document.querySelector('#curated-vacancy').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('#source-text') !== null" "source form"
    $sourceValues = @{ '#source-url' = $sourceUrl; '#source-employer' = 'Fictional Workshop'; '#source-text' = $sourceText } | ConvertTo-Json -Compress
    Invoke-JavaScript @"
(() => {
  for (const [selector, value] of Object.entries($sourceValues)) {
    const input = document.querySelector(selector);
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  document.querySelector('[data-template-id=generic-role]').click();
  return true;
})()
"@ | Out-Null
    Wait-JavaScript "document.querySelector('.source-original')?.textContent.includes('Curated Check Welder')" "saved source draft"
    $savedChats = Invoke-RestMethod -Uri 'http://localhost:8000/api/chats' -Headers $ownerHeaders
    $draftId = $savedChats[0].id
    $draftBefore = Invoke-RestMethod -Uri "http://localhost:8000/api/chats/$draftId" -Headers $ownerHeaders
    $vacancyJobId = $draftBefore.job_post.id
    Save-Screenshot 'vacancy-draft-desktop.png'

    # Ordinary restart, preserving all named volumes and environment settings.
    docker compose -f dev.docker-compose.yaml restart backend postgres | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Local restart failed' }
    Wait-JavaScript "fetch('http://localhost:8000/api/ready').then(r => r.ok).catch(() => false)" "database after restart" 55
    $draftAfter = Invoke-RestMethod -Uri "http://localhost:8000/api/chats/$draftId" -Headers $ownerHeaders
    if ($draftAfter.job_draft.source.original_text -ne $sourceText) { throw 'Draft source did not survive restart' }
    Invoke-JavaScript "[...document.querySelectorAll('button')].find(b => b.textContent.includes('Fill draft from pasted text')).click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.publish-bar') !== null && !document.querySelector('.typing')" "reviewable vacancy criteria" 50
    Invoke-JavaScript "document.querySelector('.publish-bar button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('Job published')" "published curated vacancy"
    $published = Invoke-RestMethod -Uri "http://localhost:8000/api/public/jobs/$vacancyJobId"
    if ($published.source.url -ne $sourceUrl -or $published.source.PSObject.Properties.Name -contains 'original_text') { throw 'Public source metadata is incorrect' }

    # Exercise the actual candidate screen and its separate consent wording.
    Invoke-JavaScript "sessionStorage.removeItem('job-talk-session'); location.href='/?job=$vacancyJobId'; true" | Out-Null
    Wait-JavaScript "document.querySelector('.entry-job .source-label') !== null" "public source label"
    Invoke-JavaScript "document.querySelector('.entry-job').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.source-notice')?.textContent.includes('Job Talk operator')" "candidate recipient notice"
    $guestSession = Invoke-JavaScript "sessionStorage.getItem('job-talk-session')"
    $vacancyGuestHeaders = @{ Authorization = 'Bearer ' + ($guestSession | ConvertFrom-Json).access_token }
    Wait-JavaScript "document.querySelector('.job-card button') !== null" "candidate review button"
    Invoke-JavaScript "document.querySelector('.job-card button').click(); true" | Out-Null
    Wait-JavaScript "document.querySelector('.application-review .consent-check')?.textContent.includes('permission separately')" "operator-only submission consent"
    Invoke-JavaScript @'
(async () => {
  for (const [selector, value] of Object.entries({ '#candidate-name': 'Fictional Vacancy Candidate', '#candidate-location': 'Cape Town', '#candidate-contact': 'vacancy-check@example.com' })) {
    const input = document.querySelector(selector);
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  document.querySelector('.application-review .consent-check input').click();
  document.querySelector('.application-review').requestSubmit();
  return true;
})()
'@ | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('not been sent to the advertised employer')" "curated interest submitted"
    Set-Viewport 390 760 $true
    Invoke-Cdp 'Page.reload' | Out-Null
    Wait-JavaScript "document.querySelector('.submitted-bar')?.textContent.includes('not been sent to the advertised employer')" "restored candidate phone submission"
    Wait-JavaScript "document.querySelector('.sidebar')?.getBoundingClientRect().right <= 1" "closed candidate phone sidebar"
    if (Invoke-JavaScript "document.querySelector('.source-notice').getBoundingClientRect().right > innerWidth || document.documentElement.scrollWidth > innerWidth") { throw 'Candidate source notice overflows phone viewport' }
    Save-Screenshot 'vacancy-candidate-phone.png'
    $applicationsBefore = Invoke-RestMethod -Uri "http://localhost:8000/api/applications?job_id=$vacancyJobId" -Headers $ownerHeaders
    docker compose -f dev.docker-compose.yaml restart backend postgres | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Local restart failed' }
    Wait-JavaScript "fetch('http://localhost:8000/api/ready').then(r => r.ok).catch(() => false)" "saved applications after restart" 55
    $applicationsAfter = Invoke-RestMethod -Uri "http://localhost:8000/api/applications?job_id=$vacancyJobId" -Headers $ownerHeaders
    if (($applicationsBefore | ConvertTo-Json -Depth 25 -Compress) -ne ($applicationsAfter | ConvertTo-Json -Depth 25 -Compress)) { throw 'Submitted snapshot changed across restart' }
    $afterJob = Invoke-RestMethod -Uri "http://localhost:8000/api/public/jobs/$vacancyJobId"
    if (($published | ConvertTo-Json -Depth 25 -Compress) -ne ($afterJob | ConvertTo-Json -Depth 25 -Compress)) { throw 'Published criteria changed across restart' }

    $ownerSessionJson = $ownerSession | ConvertTo-Json -Compress
    Invoke-JavaScript "sessionStorage.setItem('job-talk-session', $ownerSessionJson); location.href='/'; true" | Out-Null
    Wait-JavaScript "document.querySelector('#admin-job') !== null" "owner jobs after restart"
    Invoke-JavaScript "(() => { const select = document.querySelector('#admin-job'); select.value = '$vacancyJobId'; select.dispatchEvent(new Event('change', { bubbles: true })); return true; })()" | Out-Null
    Wait-JavaScript "document.querySelector('.interest-summary')?.textContent.includes('1 applications') && document.querySelector('.candidate-comparison')?.textContent.includes('Fictional Vacancy Candidate')" "counts and private submitted snapshot"
    if (Invoke-JavaScript "document.querySelector('.interest-summary').textContent.includes('Fictional Vacancy Candidate') || document.querySelector('.interest-summary').textContent.includes('vacancy-check@example.com')") { throw 'Aggregate summary contains identifying data' }
    Save-Screenshot 'vacancy-owner-phone.png'
    Set-Viewport 1200 800 $false
    Save-Screenshot 'vacancy-owner-desktop.png'
    Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/jobs/$vacancyJobId/close" -Headers $ownerHeaders | Out-Null
    $closedApplications = Invoke-RestMethod -Uri "http://localhost:8000/api/applications?job_id=$vacancyJobId" -Headers $ownerHeaders
    if ($closedApplications.Count -ne 1) { throw 'Closing discarded the submitted application' }
    Write-Output 'Manual vacancy check passed: source entry, guided extraction/review/publish, candidate disclosure/consent, aggregate and private comparison, two database/backend restarts and closed-job snapshot preservation. Actual LLM language acceptance remains separate.'
    Write-Output "Screenshots: $OutputDirectory"
} finally {
    if ($vacancyJobId) {
        try { Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/jobs/$vacancyJobId/close" -Headers $ownerHeaders | Out-Null } catch {}
    }
    if ($vacancyGuestHeaders) {
        Invoke-RestMethod -Method Delete -Uri 'http://localhost:8000/api/account' -Headers $vacancyGuestHeaders | Out-Null
    }
}
